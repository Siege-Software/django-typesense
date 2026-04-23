from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from django_typesense.admin import TypesenseSearchAdminMixin
from django_typesense.paginator import TypesenseSearchPaginator


class DummyCollection:
    fields = {"id": None}

    def __init__(self, data):
        self.validated_data = list(data)


class DummyModel:
    _meta = SimpleNamespace(local_fields=[SimpleNamespace(name="id")])

    @classmethod
    def get_collection_class(cls):
        return DummyCollection

    @classmethod
    def get_collection(cls, data):
        return DummyCollection(data)

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestTypesenseSearchPaginator(TestCase):
    def test_page_does_not_slice_pre_paginated_results(self):
        object_list = {
            "found": 500,
            "hits": [{"document": {"id": index}} for index in range(250, 500)],
        }
        paginator = TypesenseSearchPaginator(object_list, per_page=250, model=DummyModel)

        page = paginator.page(2)

        self.assertEqual(len(page.object_list), 250)
        self.assertEqual(page.object_list[0].id, 250)
        self.assertEqual(page.object_list[-1].id, 499)


class TestTypesenseSearchAdminPagination(TestCase):
    @mock.patch("django_typesense.admin.typesense_search", return_value={"found": 0, "hits": []})
    def test_get_typesense_search_results_caps_per_page(self, mocked_typesense_search):
        fake_admin = SimpleNamespace(
            model=SimpleNamespace(
                collection_class=SimpleNamespace(
                    schema_name="songs",
                    query_by_fields="title",
                )
            ),
            list_per_page=500,
        )

        TypesenseSearchAdminMixin.get_typesense_search_results(
            fake_admin,
            request=None,
            search_term="song",
            page_num=2,
            list_per_page=500,
        )

        mocked_typesense_search.assert_called_once()
        _, kwargs = mocked_typesense_search.call_args
        self.assertEqual(kwargs["page"], 2)
        self.assertEqual(kwargs["per_page"], 250)
