import datetime
import logging
import math
import operator
from functools import reduce

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.options import csrf_protect_m, IncorrectLookupParameters
from django.contrib.admin.utils import lookup_spawns_duplicates, model_ngettext
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.core.paginator import Paginator
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from django.forms import formset_factory, forms
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.shortcuts import render
from django.template.response import SimpleTemplateResponse, TemplateResponse
from django.urls import path
from django.utils.text import smart_split, unescape_string_literal
from django.utils.translation import ngettext

from django_typesense.forms import SearchForm
from django_typesense.methods import typesense_search
from django_typesense.paginator import TypesenseSearchPaginator

logger = logging.getLogger(__name__)


BOOLEAN_TRUES = ["y", "Y", "yes", "1", 1, True, "True", "true"]


class TypesenseSearchAdminMixin(admin.ModelAdmin):
    # TODO: Sorting should work with ModelAdmin.ordering
    # TODO: Filtering should work with ModelAdmin.list_filter
    # TODO: Querying should work with ModelAdmin.search_fields

    @property
    def media(self):
        super_media = super().media
        return forms.Media(
            js=super_media._js + ["admin/js/django_typesense-typesense.js"],
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
        from django_typesense.changelist import TypesenseChangeList

        return TypesenseChangeList

    def get_paginator(
        self, request, results, per_page, orphans=0, allow_empty_first_page=True
    ):
        return TypesenseSearchPaginator(
            results, per_page, orphans, allow_empty_first_page, self.model
        )

    def get_typesense_search_results(self, search_term, page_num, filter_by):
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
            filter_by=filter_by
        )
        return results
