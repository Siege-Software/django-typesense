import logging

from django.contrib import admin
from django.forms import forms
from django_typesense.methods import typesense_search
from django_typesense.paginator import TypesenseSearchPaginator

logger = logging.getLogger(__name__)


BOOLEAN_TRUES = ["y", "Y", "yes", "1", 1, True, "True", "true"]


class TypesenseSearchAdminMixin(admin.ModelAdmin):

    @property
    def media(self):
        super_media = super().media
        return forms.Media(
            js=super_media._js + ["admin/js/django_typesense-typesense.js"],
            css=super_media._css,
        )

    def get_sortable_by(self, request):
        sortable_fields = super().get_sortable_by(request)
        # Remove fields that sort has not been enabled in typesense schema
        def is_sortable(values):
            default_sortable_data_types = {'int32', 'int64', 'float', 'bool'}
            if values['type'] in default_sortable_data_types:
                return values.get('sort', True)

            return values.get('sort', False)

        typesense_sortable_fields = {key for key, values in self.model.typesense_fields.items() if is_sortable(values)}
        return set(sortable_fields).intersection(typesense_sortable_fields)

    def get_results(self, request):
        # This is like ModelAdmin.get_queryset(
        return typesense_search(
            collection_name=self.model.get_typesense_schema_name(), q="*"
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
        Return a tuple containing a queryset to implement the django_typesense
        and a boolean indicating if the results may contain duplicates.
        """
        results = typesense_search(
            collection_name=self.model.get_typesense_schema_name(),
            q=search_term or "*",
            query_by=self.model.query_by_fields,
            page=page_num,
            per_page=self.list_per_page,
            filter_by=filter_by,
            sort_by=sort_by
        )
        return results
