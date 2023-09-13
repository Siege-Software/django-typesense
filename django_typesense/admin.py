import logging

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.utils import model_ngettext
from django.contrib.auth.admin import csrf_protect_m
from django.core.exceptions import PermissionDenied
from django.db import transaction, router
from django.forms import forms
from django.http import JsonResponse, HttpResponseRedirect
from django.template.response import TemplateResponse, SimpleTemplateResponse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from django_typesense.utils import typesense_search
from django_typesense.paginator import TypesenseSearchPaginator

logger = logging.getLogger(__name__)


class TypesenseSearchAdminMixin(admin.ModelAdmin):
    @property
    def media(self):
        super_media = super().media
        return forms.Media(
            js=super_media._js + ["admin/js/search-typesense.js"],
            css=super_media._css,
        )

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        """
        The 'change list' admin view for this model.
        """
        template_response = super().changelist_view(request, extra_context)

        is_ajax = request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
        if is_ajax:
            html = template_response.render().rendered_content
            return JsonResponse(data={"html": html}, safe=False)

        return template_response

    def get_sortable_by(self, request):
        """
        Get sortable fields; these are fields that sort is defaulted or set to True.

        Args:
            request: the HttpRequest

        Returns:
            A list of field names
        """

        sortable_fields = super().get_sortable_by(request)
        return set(sortable_fields).intersection(self.model.collection_class.sortable_fields)

    def get_results(self, request):
        """
        Get all indexed data without any filtering or specific search terms. Works like `ModelAdmin.get_queryset()`

        Args:
            request: the HttpRequest

        Returns:
            A list of the typesense results
        """

        return typesense_search(
            collection_name=self.model.collection_class.schema_name, q="*"
        )

    def get_changelist(self, request, **kwargs):
        """
        Return the ChangeList class for use on the changelist page.
        """
        from django_typesense.changelist import TypesenseChangeList

        return TypesenseChangeList

    def get_paginator(
        self, request, results, per_page, orphans=0, allow_empty_first_page=True
    ):
        return TypesenseSearchPaginator(
            results, per_page, orphans, allow_empty_first_page, self.model
        )

    def get_typesense_search_results(self, search_term, page_num, filter_by, sort_by):
        """
        Get the results from typesense with the provided filtering, sorting, pagination and search parameters applied

        Args:
            search_term: The search term provided in the search form
            page_num: The requested page number
            filter_by: The filtering parameters
            sort_by: The sort parameters

        Returns:
            A list of typesense results
        """

        results = typesense_search(
            collection_name=self.model.collection_class.schema_name,
            q=search_term or "*",
            query_by=self.model.collection_class.query_by_fields,
            page=page_num,
            per_page=self.list_per_page,
            filter_by=filter_by,
            sort_by=sort_by,
        )
        return results
