import json
from http import HTTPStatus

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from django_typesense.admin import TypesenseSearchAdminMixin, TypesenseSearchPaginator
from django_typesense.mixins import TypesenseQuerySet

from .factories import SongFactory
from .models import Song

User = get_user_model()


class TestTypesenseSearchAdminMixin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.url = reverse(
            f"admin:{Song._meta.app_label}_{Song._meta.model_name}_changelist"
        )

        self.songs_count = 10
        SongFactory.create_batch(size=self.songs_count)

    def _create_user(self, username, email, is_superuser=True):
        user = User.objects.create(username=username, email=email, password="password")
        if is_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])

        return user

    def _create_mock_request(self, url, user, request_type="GET", headers={}, data={}):
        if request_type == "GET":
            request = self.factory.get(url, data, **headers)

        if request_type == "POST":
            request = self.factory.post(url, data, **headers)

        request.user = user
        return request

    def test_model_admin_changelist_view(self):
        model_admin = TypesenseSearchAdminMixin(Song, self.site)

        admin_user = self._create_user("admin", "admin@email.com")
        request = self._create_mock_request(self.url, admin_user)

        response = model_admin.changelist_view(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response.render()
        self.assertIn(f"{self.songs_count} songs", str(response.content))

        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        request = self._create_mock_request(self.url, admin_user, headers=headers)

        response = model_admin.changelist_view(request)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        response_data = json.loads(response.content)
        self.assertCountEqual(response_data.keys(), ["html"])
        self.assertIn(f"{self.songs_count} songs", response_data["html"])

    def test_get_paginator(self):
        model_admin = TypesenseSearchAdminMixin(Song, self.site)

        admin_user = self._create_user("admin", "admin@email.com")
        request = self._create_mock_request(self.url, admin_user)

        songs = Song.objects.all().order_by("pk")
        response = model_admin.get_paginator(request, songs, self.songs_count)
        self.assertFalse(isinstance(response, TypesenseSearchPaginator))
        self.assertTrue(isinstance(response, Paginator))

    def test_get_search_results(self):
        model_admin = TypesenseSearchAdminMixin(Song, self.site)

        admin_user = self._create_user("admin", "admin@email.com")
        request = self._create_mock_request(self.url, admin_user, request_type="POST")

        songs = Song.objects.all().order_by("pk")
        query_set, may_have_duplicates = model_admin.get_search_results(
            request, songs, "*"
        )
        self.assertTrue(isinstance(query_set, TypesenseQuerySet))
        self.assertEqual(query_set.count(), self.songs_count)
        self.assertFalse(may_have_duplicates)

        request = self._create_mock_request(
            self.url, admin_user, request_type="POST", data={"action": "delete"}
        )
        query_set, may_have_duplicates = model_admin.get_search_results(
            request, songs, "*"
        )

        self.assertTrue(isinstance(query_set, TypesenseQuerySet))
        self.assertEqual(query_set.count(), self.songs_count)
        self.assertFalse(may_have_duplicates)
