import logging

from copy import deepcopy

from django.db import models

from typesense.exceptions import ObjectNotFound

from django_typesense.typesense_client import client
from django_typesense.methods import bulk_delete_typesense_records, bulk_update_typesense_records

logger = logging.getLogger(__name__)


class TypesenseUpdateDeleteQuerySetManager(models.QuerySet):
    def delete(self):
        document_ids_list = [document.id for document in self]
        collection_name = self.model.get_typesense_schema_name()
        delete_result = super().delete()

        if not issubclass(self.model, TypeSenseMixin):
            logger.error(
                f"The class {self.model.__name__} does not inherit the Typesense mixin, please setup the "
                f"Typesense indexing for the class"
            )
        else:
            bulk_delete_typesense_records(document_ids_list, collection_name)

        return delete_result

    def update(self, **kwargs):
        update_result = super().update(**kwargs)

        if not issubclass(self.model, TypeSenseMixin):
            logger.error(
                f"The class {self.model.__name__} does not inherit the Typesense mixin, please setup the "
                f"Typesense indexing for the class"
            )
        else:
            bulk_update_typesense_records(self, self.model.typesense_schema_name)

        return update_result


class TypeSenseMixin(models.Model):
    typesense_fields = []
    typesense_schema_name = None
    typesense_default_sorting_field = None
    query_by_fields = "id"

    objects = TypesenseUpdateDeleteQuerySetManager.as_manager()

    @classmethod
    def get_typesense_schema_name(cls) -> str:
        if cls.typesense_schema_name:
            return cls.typesense_schema_name
        return cls.__name__.lower()

    @classmethod
    def get_typesense_fields(cls):
        fields = deepcopy(cls.typesense_fields)

        # Auto adds the pk as Id if absent
        if not any(field["name"] == "id" for field in fields):
            fields.append({"name": "id", "type": "string", "attribute": "pk"})

        return fields

    def get_typesense_dict(self):
        return {}

    @classmethod
    def _get_typesense_schema(cls):
        schema = {
            "name": cls.get_typesense_schema_name(),
            "fields": cls.get_typesense_fields(),
        }

        if cls.typesense_default_sorting_field:
            schema["default_sorting_field"] = cls.typesense_default_sorting_field

        existing_fields = []

        for field in schema["fields"]:
            existing_fields.append(field["name"])
            if "attribute" in field:
                del field["attribute"]

        return schema

    def _get_typesense_field_value(self, field):
        if "attribute" in field:
            attribute = field["attribute"]
        else:
            attribute = field["name"]
        return getattr(self, attribute)

    @classmethod
    def create_typesense_collection(cls):
        client.collections.create(cls._get_typesense_schema())

    @classmethod
    def drop_typesense_collection(cls):
        client.collections[cls.get_typesense_schema_name()].delete()

    @classmethod
    def retrieve_typesense_collection(cls):
        return client.collections[cls.get_typesense_schema_name()].retrieve()

    def upsert_typesense_document(self):
        document_data = self.get_typesense_dict()

        document_data["id"] = str(document_data["id"])

        try:
            client.collections[self.get_typesense_schema_name()].documents.upsert(
                document_data
            )

        except ObjectNotFound:
            self.create_typesense_collection()
            client.collections[self.get_typesense_schema_name()].documents.upsert(
                document_data
            )

    def delete_typesense_document(self):
        try:
            client.collections[self.get_typesense_schema_name()].documents[
                str(self.pk)
            ].delete()
        except ObjectNotFound:
            logger.debug(
                f"Could not delete the object {self}, possibly it was already deleted or it was not indexed"
            )

    class Meta:
        abstract = True
