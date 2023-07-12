import datetime
import logging
import math
import operator
from functools import reduce

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.options import csrf_protect_m, IncorrectLookupParameters
from django.contrib.admin.utils import lookup_needs_distinct, model_ngettext
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.core.paginator import Paginator
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.forms import formset_factory, forms
from django.utils.translation import ugettext_lazy as _
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.shortcuts import render
from django.template.response import SimpleTemplateResponse, TemplateResponse
from django.urls import path
from django.utils.text import smart_split, unescape_string_literal
from django.utils.translation import ngettext

from search.forms import SearchForm
from search.methods import typesense_search
from search.constants import TYPESENSE_PAGE_SIZE, BOOLEAN_TRUES
from search.paginator import TypesenseSearchPaginator

logger = logging.getLogger(__name__)


class TypesenseSearchAdminMixin(admin.ModelAdmin):
    # TODO: Sorting should work with ModelAdmin.ordering
    # TODO: Filtering should work with ModelAdmin.list_filter
    # TODO: Querying should work with ModelAdmin.search_fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.typesense_root_change_list_template = self.change_list_template or "admin/change_list.html"
        # self.change_list_template = 'admin/search/change_list.html'

    @property
    def media(self):
        super_media = super().media
        return forms.Media(
            js=super_media._js + ["admin/js/search-typesense.js"],
            css=super_media._css,
        )

    def get_results(self, request):
        # This is like ModelAdmin.get_queryset(
        return typesense_search(
            collection_name=self.model.get_typesense_schema_name(), q="*"
        )

    def get_changelist(self, request, **kwargs):
        """
        Return the ChangeList class for use on the changelist page.
        """
        from search.changelist import TypesenseChangeList

        return TypesenseChangeList

    def get_paginator(
        self, request, results, per_page, orphans=0, allow_empty_first_page=True
    ):
        return TypesenseSearchPaginator(
            results, per_page, orphans, allow_empty_first_page, self.model
        )

    def get_typesense_search_results(self, request, results, search_term):
        """
        Return a tuple containing a queryset to implement the search
        and a boolean indicating if the results may contain duplicates.
        """
        results = typesense_search(
            collection_name=self.model.get_typesense_schema_name(),
            q=search_term or "*",
            query_by=self.model.query_by_fields,
            per_page=self.list_per_page,
            page=1,
        )
        return results

    def search_typesense(self, request, **kwargs):
        get_data = request.GET.copy()
        search_term = get_data.pop("search_query", [])
        search_term = search_term[0] if search_term else ""
        order_by_list = get_data.pop("order_by", [])
        sorting_order_by_list = get_data.pop("sort_asc", [])
        order_by = ", ".join(order_by_list) if order_by_list else ""

        if order_by:
            sort_asc = sorting_order_by_list[0] == "True"
            order_by = f"{order_by}: asc" if sort_asc else f"{order_by}: desc"

        if request.POST:
            search_term = request.POST.get("post_search_term") or search_term
        page = get_data.pop("page", 1)
        page = int(page[0]) if isinstance(page, list) else page

        for field in self.get_search_date_fields():  # clean instant search dates
            if get_data.get(field):
                get_data[field] = get_data[field].replace("+", " ")

        request.GET = get_data
        query_by = self.model.query_by_fields
        filter_by = kwargs.get("filter_by", "")

        if not query_by:
            logger.error(
                f"Query by fields are required for Typesense search for model {self.model}"
            )

        context = get_context(request)
        context.update(**self.admin_site.each_context(request))

        results = typesense_search(
            collection_name=self.model.get_typesense_schema_name(),
            q=search_term or "*",
            query_by=query_by,
            per_page=self.list_per_page,
            page=page[0] if isinstance(page, list) else page,
            filter_by=filter_by,
            sort_by=order_by,
        )

        search_results = [row["document"] for row in results["hits"]]
        context["results"] = search_results

        html = render_to_string(
            template_name="admin/search/typesense-search-results-partial.html",
            context=context,
        )

        data_dict = {"html_from_view": html}
        return JsonResponse(data=data_dict, safe=False)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "search_typesense",
                self.admin_site.admin_view(self.search_typesense),
                name="search_typesense",
            ),
        ]
        return my_urls + urls

    def get_list_display_fields(self):
        return [
            {"display_field": field.replace("_", " ").title(), "field": field}
            for field in self.typesense_list_fields
        ]

    @staticmethod
    def update_filter_by_query(filter_by_query: str, field: str, value: any) -> str:
        if not filter_by_query:
            return f"{field}: {value}"

        return f"{filter_by_query} && {field}: {value}"

    def get_query_by_string(self, request, query_by_fields: []) -> str:
        filter_by_query = self.get_query_by_date_string(request)

        for field in query_by_fields:
            admin_field = field.get("admin_field", "")
            if request.GET.get(admin_field):
                if not field.get("boolean", False):
                    filter_by_query = self.update_filter_by_query(
                        filter_by_query=filter_by_query,
                        field=field["typesense_field"],
                        value=request.GET.get(admin_field),
                    )
                else:
                    value = (
                        "true"
                        if request.GET.get(admin_field) in BOOLEAN_TRUES
                        else "false"
                    )
                    filter_by_query = self.update_filter_by_query(
                        filter_by_query=filter_by_query,
                        field=field["typesense_field"],
                        value=value,
                    )

                    if field.get("reverse_field"):
                        filter_by_query = self.update_filter_by_query(
                            filter_by_query=filter_by_query,
                            field=field.get("reverse_field"),
                            value="false",
                        )

        return filter_by_query

    def get_query_by_date_string(self, request) -> str:
        filter_by_query = ""
        search_fields = []
        for field in self.get_search_date_fields():
            if request.GET.get(field):
                delimiters = [
                    "__range__gte",
                    "__range__gte",
                    "__range__lte",
                    "__range__lt",
                ]

                # Done this to fix .strip() which was stripping any character that is contained in the strip string
                typesense_field = ""
                for delimiter in delimiters:
                    if field.endswith(delimiter):
                        typesense_field = field.replace(delimiter, "")

                search_fields.append(typesense_field)
                datetime_str = request.GET.get(field).replace("+", " ").strip()

                try:
                    date = datetime.datetime.strptime(datetime_str, "%Y-%m-%d")
                except ValueError:
                    date = None

                if date and field.endswith("gte"):
                    filter_by_query = self.update_filter_by_query(
                        filter_by_query,
                        value=f">={date.timestamp()}",
                        field=typesense_field,
                    )
                elif date and field.endswith("gt"):
                    filter_by_query = self.update_filter_by_query(
                        filter_by_query,
                        value=f">{date.timestamp()}",
                        field=typesense_field,
                    )
                elif date and field.endswith("lt"):
                    filter_by_query = self.update_filter_by_query(
                        filter_by_query,
                        value=f"<{date.timestamp()}",
                        field=typesense_field,
                    )
                elif date and field.endswith("lte"):
                    filter_by_query = self.update_filter_by_query(
                        filter_by_query,
                        value=f"<={date.timestamp()}",
                        field=typesense_field,
                    )

        return filter_by_query

    def get_typesense_form(self, results):
        formset = formset_factory(SearchForm, extra=0)

        formset = formset(
            initial=results,
            form_kwargs={"fields": self.typesense_list_fields, "model": self.model},
        )
        return formset

    def get_search_date_fields(self):
        search_fields = []
        [
            search_fields.extend(
                [
                    f"{field}__range__gte",
                    f"{field}__range__gt",
                    f"{field}__range__lte",
                    f"{field}__range__lt",
                ]
            )
            for field in self.typesense_list_date_fields
        ]
        return search_fields
