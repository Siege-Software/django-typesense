from django.contrib import admin

from django_typesense.admin import TypesenseSearchAdminMixin
from tests.models import Song

admin.site.register(Song, TypesenseSearchAdminMixin)
