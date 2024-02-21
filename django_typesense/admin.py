import logging

from django.contrib import admin
from django.contrib.auth.admin import csrf_protect_m
from django.db.models import QuerySet
from django.forms import forms
from django.http import JsonResponse

from django_typesense.mixins import TypesenseModelMixin
from django_typesense.utils import typesense_search, export_documents
from django_typesense.paginator import TypesenseSearchPaginator

logger = logging.getLogger(__name__)


class TypesenseSearchAdminMixin(admin.ModelAdmin):
    typesense_search_fields = []

    def get_typesense_search_fields(self, request):
        """Return a sequence containing the fields to
        be searched wheneversomebody submits a search query.
        """
        return self.typesense_search_fields

    @property
    def media(self):
        super_media = super().media
        return forms.Media(
            js=super_media._js + ["admin/js/search-typesense.js"],
            css=super_media._css,
        )

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        """The 'change list' admin view for this model."""
        template_response = super().changelist_view(request, extra_context)

        is_ajax = request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
        if is_ajax:
            html = template_response.render().rendered_content
            return JsonResponse(data={"html": html}, safe=False)

        return template_response

    def get_sortable_by(self, request):
        """Get sortable fields; these are fields that sort is defaulted or set to True.

        Parameters
        ----------
        request: HttpRequest
            The current request object.

        Returns
        -------
        list
            A list of field names
        """

        sortable_fields = super().get_sortable_by(request)
        return set(sortable_fields).intersection(
            self.model.collection_class.sortable_fields
        )

    def get_results(self, request):
        """Get all indexed data without any filtering or specific
        search terms. Works like `ModelAdmin.get_queryset()`.

        Parameters
        ----------
        request: HttpRequest
            The current request object.

        Returns
        -------
        list
            A list of the typesense results
        """

        return typesense_search(
            collection_name=self.model.collection_class.schema_name,
            q="*",
            query_by=self.model.collection_class.query_by_fields,
        )

    def get_changelist(self, request, **kwargs):
        """Return the ChangeList class for use on the changelist page."""
        from django_typesense.changelist import TypesenseChangeList

        return TypesenseChangeList

    def get_paginator(
        self, request, results, per_page, orphans=0, allow_empty_first_page=True
    ):
        # fallback incase we receive a queryset.
        if isinstance(results, QuerySet):
            return super().get_paginator(
                request, results, per_page, orphans, allow_empty_first_page
            )

        return TypesenseSearchPaginator(
            results, per_page, orphans, allow_empty_first_page, self.model
        )

    def get_typesense_search_results(
        self,
        request,
        search_term: str,
        page_num: int = 1,
        filter_by: str = "",
        sort_by: str = "",
    ):
        """
        Get the results from typesense with the provided filtering,
        sorting, pagination and search parameters applied.

        Parameters
        ----------
        request: HttpRequest
            The current request object.
        search_term: str
            The search term provided in the search form.
        page_num: int
            The requested page number.
        filter_by: str
            The filtering parameters.
        sort_by: str
            The sort parameters.

        Returns
        -------
        list
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

    def get_search_results(self, request, queryset, search_term):
        if not request.POST.get("action"):
            may_have_duplicates = False
            results = self.get_typesense_search_results(request, search_term)
            ids = [result["document"]["id"] for result in results["hits"]]
            queryset = queryset.filter(id__in=ids)
        else:
            # id_dict_list = export_documents(
            #     self.model.collection_class.schema_name, include_fields=["id"]
            # )
            # queryset = queryset.filter(
            #     id__in=[id_dict["id"] for id_dict in id_dict_list]
            # )
            queryset, may_have_duplicates = super().get_search_results(
                request, queryset, search_term
            )

        return queryset, may_have_duplicates
