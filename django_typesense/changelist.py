import logging

from django import forms
from django.contrib import messages
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import (
    IS_POPUP_VAR,
    TO_FIELD_VAR,
    IncorrectLookupParameters,
)
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.core.paginator import InvalidPage
from django.db.models import OrderBy, OuterRef, Exists
from django.utils.translation import gettext
from django.utils.dateparse import parse_datetime

from django_typesense.fields import TYPESENSE_DATETIME_FIELDS
from django_typesense.utils import get_unix_timestamp

# Changelist settings
ALL_VAR = "all"
ORDER_VAR = "o"
ORDER_TYPE_VAR = "ot"
PAGE_VAR = "p"
SEARCH_VAR = "q"
ERROR_FLAG = "e"

IGNORED_PARAMS = (
    ALL_VAR,
    ORDER_VAR,
    ORDER_TYPE_VAR,
    SEARCH_VAR,
    IS_POPUP_VAR,
    TO_FIELD_VAR,
)

logger = logging.getLogger(__name__)


class ChangeListSearchForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate "fields" dynamically because SEARCH_VAR is a variable:
        self.fields = {
            SEARCH_VAR: forms.CharField(required=False, strip=False),
        }


class TypesenseChangeList(ChangeList):
    search_form_class = ChangeListSearchForm

    def __init__(
        self,
        request,
        model,
        list_display,
        list_display_links,
        list_filter,
        date_hierarchy,
        search_fields,
        list_select_related,
        list_per_page,
        list_max_show_all,
        list_editable,
        model_admin,
        sortable_by,
        search_help_text,
    ):
        self.model = model
        self.opts = model._meta
        self.lookup_opts = self.opts
        self.root_queryset = model_admin.get_queryset(request)

        # TYPESENSE
        self.root_results = model_admin.get_results(request)

        self.list_display = list_display
        self.list_display_links = list_display_links
        self.list_filter = list_filter
        self.has_filters = None
        self.has_active_filters = None
        self.clear_all_filters_qs = None
        self.date_hierarchy = date_hierarchy
        self.search_fields = model_admin.get_typesense_search_fields(request)
        self.list_select_related = list_select_related
        self.list_per_page = min(list_per_page, 250)  # Typesense Max hits per page
        self.list_max_show_all = min(
            list_max_show_all, 250
        )  # Typesense Max hits per page
        self.model_admin = model_admin
        self.preserved_filters = model_admin.get_preserved_filters(request)
        self.sortable_by = sortable_by
        self.search_help_text = search_help_text

        # Get django_typesense parameters from the query string.
        _search_form = self.search_form_class(request.GET)
        if not _search_form.is_valid():
            for error in _search_form.errors.values():
                messages.error(request, ", ".join(error))
        self.query = _search_form.cleaned_data.get(SEARCH_VAR) or ""
        try:
            self.page_num = int(request.GET.get(PAGE_VAR, 1))
        except ValueError:
            self.page_num = 1
        self.show_all = ALL_VAR in request.GET
        self.is_popup = IS_POPUP_VAR in request.GET
        to_field = request.GET.get(TO_FIELD_VAR)
        if to_field and not model_admin.to_field_allowed(request, to_field):
            raise DisallowedModelAdminToField(
                "The field %s cannot be referenced." % to_field
            )
        self.to_field = to_field
        self.params = dict(request.GET.items())
        if PAGE_VAR in self.params:
            del self.params[PAGE_VAR]
        if ERROR_FLAG in self.params:
            del self.params[ERROR_FLAG]

        if self.is_popup:
            self.list_editable = ()
        else:
            self.list_editable = list_editable

        # TYPESENSE
        self.results = self.get_typesense_results(request)
        self.get_results(request)

        if self.is_popup:
            title = gettext("Select %s")
        elif self.model_admin.has_change_permission(request):
            title = gettext("Select %s to change")
        else:
            title = gettext("Select %s to view")
        self.title = title % self.opts.verbose_name
        self.pk_attname = self.lookup_opts.pk.attname

    def get_results(self, request):
        paginator = self.model_admin.get_paginator(
            request, self.results, self.list_per_page
        )
        # Get the number of objects, with admin filters applied.
        result_count = paginator.count

        # Get the total number of objects, with no admin filters applied.
        if self.model_admin.show_full_result_count:
            full_result_count = self.root_results["found"]
        else:
            full_result_count = None
        can_show_all = result_count <= self.list_max_show_all
        multi_page = result_count > self.list_per_page

        # Get the list of objects to display on this page.
        if (self.show_all and can_show_all) or not multi_page:
            # Reuse values defined in paginator
            result_list = paginator.results
        else:
            try:
                result_list = paginator.page(self.page_num).object_list
            except InvalidPage:
                raise IncorrectLookupParameters

        self.result_count = result_count
        self.show_full_result_count = self.model_admin.show_full_result_count
        # Admin actions are shown if there is at least one entry
        # or if entries are not counted because show_full_result_count is disabled
        self.show_admin_actions = not self.show_full_result_count or bool(
            full_result_count
        )
        self.full_result_count = full_result_count
        self.result_list = result_list
        self.can_show_all = can_show_all
        self.multi_page = multi_page
        self.paginator = paginator

    def get_typesense_ordering(self, request):
        """
        Return the list of ordering fields for the change list.
        First check the get_ordering() method in model admin, then check
        the object's default ordering. Then, any manually-specified ordering
        from the query string overrides anything. Finally, a deterministic
        order is guaranteed by calling _get_deterministic_ordering() with the
        constructed ordering.
        """
        params = self.params
        ordering = list(
            self.model_admin.get_ordering(request) or self._get_default_ordering()
        )
        if ORDER_VAR in params:
            # Clear ordering and used params
            ordering = []
            order_params = params[ORDER_VAR].split(".")
            for p in order_params:
                try:
                    _, pfx, idx = p.rpartition("-")
                    field_name = self.list_display[int(idx)]
                    order_field = self.get_ordering_field(field_name)
                    if not order_field:
                        continue  # No 'admin_order_field', skip it
                    if isinstance(order_field, OrderBy):
                        if pfx == "-":
                            order_field = order_field.copy()
                            order_field.reverse_ordering()
                        ordering.append(order_field)
                    elif hasattr(order_field, "resolve_expression"):
                        # order_field is an expression.
                        ordering.append(
                            order_field.desc() if pfx == "-" else order_field.asc()
                        )
                    # reverse order if order_field has already "-" as prefix
                    elif order_field.startswith("-") and pfx == "-":
                        ordering.append(order_field[1:])
                    else:
                        ordering.append(pfx + order_field)
                except (IndexError, ValueError):
                    continue  # Invalid ordering specified, skip it.

        return self._get_deterministic_ordering(ordering)

    def get_sort_by(self, ordering):
        sort_dict = {}
        fields = self.model.collection_class.get_fields()

        for param in ordering:
            if param.startswith("-"):
                _, field_name = param.split("-")
                order = "desc"
            else:
                field_name = param
                order = "asc"

            # Temporarily left out: Could not find a field named `id` in the schema for sorting
            if field_name in ["pk", "id"]:
                # sort_dict['id'] = order
                continue

            if not fields.get(field_name):
                continue

            if not fields[field_name].sort:
                continue

            sort_dict[field_name] = order

        sort_by = ",".join([f"{key}:{value}" for key, value in sort_dict.items()])
        return sort_by

    def get_search_filters(self, field_name: str, used_parameters: dict):
        search_filters_dict = {}
        if not used_parameters:
            return search_filters_dict

        lookup_to_operator = {
            "gte": ">=",
            "gt": ">",
            "lte": "<=",
            "lt": "<",
            "iexact": "=",
            "exact": "=",
        }
        max_val, min_val, lookup, value = None, None, None, None

        try:
            field = self.model.collection_class.get_field(field_name)
        except KeyError as er:
            logger.debug(
                f"Searching `{field_name}` with parameters `{used_parameters}` produced error: {er}"
            )
            return search_filters_dict

        for key, value in used_parameters.items():
            if value is None or value == "":
                continue

            try:
                _, lookup = key.rsplit("__", maxsplit=1)
            except ValueError:
                lookup = ""

            lookup = lookup or "exact"
            if lookup == "isnull":
                # Null search is not supported in typesense
                continue

            if isinstance(field, tuple(TYPESENSE_DATETIME_FIELDS)):
                datetime_object = parse_datetime(value)
                value = get_unix_timestamp(datetime_object)

            if str(value).isdigit():
                if lookup in ["gte", "gt"]:
                    min_val = value
                if lookup in ["lte", "lt"]:
                    max_val = value

        if max_val and min_val:
            search_filters_dict[field_name] = f"[{min_val}..{max_val}]"
            value = None
        elif max_val or min_val:
            search_filters_dict[
                field_name
            ] = f"{lookup_to_operator[lookup]}{min_val or max_val}"
            value = None

        if value is not None and lookup is not None:
            if field.field_type == "string":
                search_filters_dict[
                    field_name
                ] = f":{lookup_to_operator[lookup]}{value}"
            elif field.field_type == "bool":
                if isinstance(value, str):
                    value = value.lower()

                boolean_map = {
                    0: "false",
                    1: "true",
                    "0": "false",
                    "1": "true",
                    "false": "false",
                    "true": "true",
                    "no": "false",
                    "yes": "true",
                    "n": "false",
                    "y": "true",
                    False: "false",
                    True: "true",
                }
                search_filters_dict[field_name] = boolean_map[value]
            else:
                search_filters_dict[field_name] = f"{lookup_to_operator[lookup]}{value}"

        return search_filters_dict

    def get_typesense_results(self, request):
        """
        This should do what Changelist.get_queryset does

        Args:
            request:

        Returns:
            Typesense Search Results in dictionary
        """

        # First, we collect all the declared list filters.
        (
            self.filter_specs,
            self.has_filters,
            remaining_lookup_params,
            filters_may_have_duplicates,
            self.has_active_filters,
        ) = self.get_filters(request)

        # we let every list filter modify the objs to its liking.
        filters_dict = {}

        for filter_spec in self.filter_specs:
            if hasattr(filter_spec, "filter_by"):
                # all custom filters with filter_by defined
                filters_dict.update(filter_spec.filter_by)
                continue

            if hasattr(filter_spec, "field"):
                used_parameters = getattr(filter_spec, "used_parameters")
                search_filters = self.get_search_filters(
                    filter_spec.field.attname, used_parameters
                )
                filters_dict.update(search_filters)
            else:
                # custom filters where filter_by is not defined
                used_parameters = getattr(filter_spec, "used_parameters")
                remaining_lookup_params.update(used_parameters)

        for k, v in remaining_lookup_params.items():
            try:
                field_name, _ = k.split("__", maxsplit=1)
            except ValueError:
                field_name = k
                k = f"{k}__exact"

            search_filters = self.get_search_filters(field_name, {k: v})
            filters_dict.update(search_filters)

        filter_by = " && ".join(
            [f"{key}:{value}" for key, value in filters_dict.items()]
        )

        # Set ordering.
        ordering = self.get_typesense_ordering(request)
        sort_by = self.get_sort_by(ordering)

        # Apply django_typesense search results
        query = self.query or "*"
        results = self.model_admin.get_typesense_search_results(
            request,
            query,
            self.page_num,
            filter_by=filter_by,
            sort_by=sort_by,
        )

        # Set query string for clearing all filters.
        self.clear_all_filters_qs = self.get_query_string(
            new_params=remaining_lookup_params,
            remove=self.get_filters_params(),
        )

        return results

    def get_queryset(self, request):
        # this is needed for admin actions that call cl.get_queryset
        # exporting is the currently possible way of getting records from typesense without pagination
        # Typesense team will work on a flag to disable pagination, until then, we need a way to get this to work.
        # Problem happens when django finds fields only present on typesense in its filter i.e IncorrectLookupParameters
        # First, we collect all the declared list filters.
        (
            self.filter_specs,
            self.has_filters,
            remaining_lookup_params,
            filters_may_have_duplicates,
            self.has_active_filters,
        ) = self.get_filters(request)
        # Then, we let every list filter modify the queryset to its liking.
        qs = self.root_queryset

        for filter_spec in self.filter_specs:
            new_qs = filter_spec.queryset(request, qs)
            if new_qs is not None:
                qs = new_qs

        for param, value in remaining_lookup_params.items():
            try:
                # Finally, we apply the remaining lookup parameters from the query
                # string (i.e. those that haven't already been processed by the
                # filters).
                qs = qs.filter(**{param: value})
            except (SuspiciousOperation, ImproperlyConfigured):
                # Allow certain types of errors to be re-raised as-is so that the
                # caller can treat them in a special way.
                raise
            except Exception as e:
                # Every other error is caught with a naked except, because we don't
                # have any other way of validating lookup parameters. They might be
                # invalid if the keyword arguments are incorrect, or if the values
                # are not in the correct type, so we might get FieldError,
                # ValueError, ValidationError, or ?.

                # for django-typesense, possibly means k only available in typesense
                new_lookup_params = self.model.collection_class.get_django_lookup(param, value, e)
                qs = qs.filter(**new_lookup_params)

        # Apply search results
        qs, search_may_have_duplicates = self.model_admin.get_search_results(
            request,
            qs,
            self.query,
        )

        # Set query string for clearing all filters.
        self.clear_all_filters_qs = self.get_query_string(
            new_params=remaining_lookup_params,
            remove=self.get_filters_params(),
        )
        # Remove duplicates from results, if necessary
        if filters_may_have_duplicates | search_may_have_duplicates:
            qs = qs.filter(pk=OuterRef("pk"))
            qs = self.root_queryset.filter(Exists(qs))

        # Set ordering.
        ordering = self.get_ordering(request, qs)
        qs = qs.order_by(*ordering)

        if not qs.query.select_related:
            qs = self.apply_select_related(qs)

        return qs
