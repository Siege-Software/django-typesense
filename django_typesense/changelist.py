from datetime import datetime

from django import forms
from django.contrib import messages
from django.contrib.admin import (
    BooleanFieldListFilter, AllValuesFieldListFilter, ChoicesFieldListFilter, RelatedFieldListFilter
)
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import (
    IS_POPUP_VAR,
    TO_FIELD_VAR,
    IncorrectLookupParameters,
)
from django.contrib.admin.views.main import ChangeList
from django.core.paginator import InvalidPage
from django.db import models
from django.db.models import OrderBy
from django.utils.translation import gettext
from django.utils.dateparse import parse_datetime

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
        search_help_text
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
        self.search_fields = search_fields
        self.list_select_related = list_select_related
        self.list_per_page = list_per_page
        self.list_max_show_all = list_max_show_all
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
            full_result_count = self.root_results['found']
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

    def get_ordering(self, request):
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
        collection = self.model.get_collection()
        fields = collection.fields

        for param in ordering:
            if param.startswith('-'):
                _, field_name = param.split('-')
                order = 'desc'
            else:
                field_name = param
                order = 'asc'

            # Temporarily left out: Could not find a field named `id` in the schema for sorting
            if field_name in ['pk', 'id']:
                # sort_dict['id'] = order
                continue

            if not fields.get(field_name):
                continue

            if not fields[field_name].sort:
                continue

            sort_dict[field_name] = order

        sort_by = ','.join([f'{key}:{value}' for key, value in sort_dict.items()])
        return sort_by

    def get_date_filters(self, filter_spec):
        date_filters_dict = {}
        lookup_to_operator = {'gte':'>=', 'gt': '>', 'lte': '<=', 'lt': '<'}

        if hasattr(filter_spec, 'used_parameters'):
            max_timestamp, min_timestamp = None, None
            for key, value in filter_spec.used_parameters.items():
                if not value:
                    continue
                field_name = filter_spec.field.attname
                _, lookup = key.rsplit('__', maxsplit=1)
                if lookup == 'isnull':
                    # Null search is not supported in typesense
                    continue

                datetime_object = parse_datetime(value)
                timestamp = int(datetime.combine(datetime_object, datetime.min.time()).timestamp())

                if lookup in ['gte', 'gt']:
                    min_timestamp = timestamp
                else:
                    max_timestamp = timestamp

            if max_timestamp and min_timestamp:
                date_filters_dict[field_name] = f'[{min_timestamp}..{max_timestamp}]'
            elif max_timestamp or min_timestamp:
                date_filters_dict[field_name] = f'{lookup_to_operator[lookup]}{timestamp}'

        return date_filters_dict

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
        text_filters = (AllValuesFieldListFilter, ChoicesFieldListFilter)
        datetime_fields = (models.fields.DateTimeField, models.fields.DateField, models.fields.TimeField)

        for filter_spec in self.filter_specs:
            if isinstance(filter_spec, BooleanFieldListFilter):
                boolean_map = {'0': 'false', '1': 'true'}
                lookup_value = filter_spec.lookup_val
                if lookup_value:
                    filters_dict[filter_spec.field_path] = boolean_map[lookup_value]

            elif isinstance(filter_spec, text_filters):
                lookup_value = filter_spec.lookup_val
                if lookup_value:
                    filters_dict[filter_spec.field_path] = lookup_value

            elif isinstance(filter_spec, RelatedFieldListFilter):
                lookup_value = filter_spec.lookup_val
                typesense_field = f"{filter_spec.field_path}_id"

                if lookup_value:
                    filters_dict[typesense_field] = lookup_value

            else:
                if hasattr(filter_spec, 'filter_by'):
                    # ALL CUSTOM FILTERS
                    filters_dict.update(filter_spec.filter_by)

                if hasattr(filter_spec, 'field'):
                    if isinstance(filter_spec.field, datetime_fields):
                        date_filters = self.get_date_filters(filter_spec)
                        filters_dict.update(date_filters)

        filter_by = ' && '.join([f'{key}:{value}' for key, value in filters_dict.items()])

        # Set ordering.
        ordering = self.get_ordering(request)
        sort_by = self.get_sort_by(ordering)

        # Apply django_typesense search results
        query = self.query or "*"
        results = self.model_admin.get_typesense_search_results(
            query,
            self.page_num,
            filter_by=filter_by,
            sort_by=sort_by
        )

        # Set query string for clearing all filters.
        self.clear_all_filters_qs = self.get_query_string(
            new_params=remaining_lookup_params,
            remove=self.get_filters_params(),
        )

        return results
