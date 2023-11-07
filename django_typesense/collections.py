from __future__ import annotations

import logging
import pdb
from typing import Dict, Iterable, List, Union

from django.db.models import QuerySet
from django.utils.functional import cached_property

try:
    from django.utils.functional import classproperty
except ImportError:
    from django.utils.decorators import classproperty

from typesense.exceptions import ObjectAlreadyExists, ObjectNotFound

from django_typesense.fields import TypesenseCharField, TypesenseField
from django_typesense.typesense_client import client

logger = logging.getLogger(__name__)

_COLLECTION_META_OPTIONS = {
    "schema_name",
    "default_sorting_field",
    "token_separators",
    "symbols_to_index",
    "query_by_fields",
}
_SYNONYM_PARAMETERS = {"synonyms", "root", "locale", "symbols_to_index"}


class Synonym:
    name: str = ""
    synonyms: list[str] = None
    root: str = ""
    locale: str = ""
    symbols_to_index: list[str] = None

    @classproperty
    def data(cls):
        if not cls.name:
            raise ValueError("the name attribute must be set")

        if not cls.synonyms:
            raise ValueError("the synonyms attribute must be set")

        if cls.symbols_to_index is None:
            cls.symbols_to_index = []

        return {
            cls.name: {
                param: getattr(cls, param)
                for param in _SYNONYM_PARAMETERS
                if getattr(cls, param)
            }
        }


class TypesenseCollectionMeta(type):
    def __new__(cls, name, bases, namespace):
        namespace["schema_name"] = namespace.get("schema_name") or name.lower()
        return super().__new__(cls, name, bases, namespace)


class TypesenseCollection(metaclass=TypesenseCollectionMeta):
    query_by_fields: str = ""
    schema_name: str = ""
    default_sorting_field: str = ""
    token_separators: list = []
    symbols_to_index: list = []
    synonyms: List[Synonym] = []

    def __init__(
        self,
        obj: Union[object, QuerySet, Iterable] = None,
        many: bool = False,
        data: list = None,
    ):
        assert (
            self.query_by_fields
        ), "`query_by_fields` must be specified in the collection definition"
        assert not all([obj, data]), "`obj` and `data` cannot be provided together"

        self._meta = self._get_metadata()
        self.fields = self.get_fields()
        self._synonyms = [synonym().data for synonym in self.synonyms]

        # TODO: Make self.data a cached_property
        if data:
            self.data = data
        elif obj:
            if many:
                self.data = list(map(self._get_object_data, obj))
            else:
                self.data = [self._get_object_data(obj)]
        else:
            self.data = []

    @classmethod
    def get_fields(cls) -> Dict[str, TypesenseField]:
        """
        Returns:
            A dictionary of the fields names to the field definition for this collection
        """
        fields = {}
        # Avoid Recursion Errors
        exclude_attributes = {"sortable_fields"}

        for attr in dir(cls):
            if attr in exclude_attributes:
                continue
            attr_value = getattr(cls, attr, None)
            if not isinstance(attr_value, TypesenseField):
                continue

            attr_value._name = attr
            attr_value._value = attr_value._value or attr
            fields[attr] = attr_value

        # Auto adds id if absent
        if not fields.get("id"):
            _id = TypesenseCharField(sort=True, value="pk")
            _id._name = "id"
            fields["id"] = _id

        return fields

    @classmethod
    def _get_metadata(cls) -> dict:
        defined_meta_options = _COLLECTION_META_OPTIONS.intersection(set(dir(cls)))
        return {
            meta_option: getattr(cls, meta_option)
            for meta_option in defined_meta_options
        }

    @cached_property
    def validated_data(self) -> list:
        """
        Returns a list of the collection data with values converted into the correct Python objects
        """

        _validated_data = []

        for obj in self.data:
            data = {}
            for key, value in obj.items():
                field = self.get_field(key)
                data[key] = field.to_python(value)

            _validated_data.append(data)

        return _validated_data

    def __str__(self):
        return f"{self.schema_name} TypesenseCollection"

    @classproperty
    def sortable_fields(cls) -> list:
        """
        Returns:
            The names of sortable fields
        """
        fields = cls.get_fields()
        return [field.name for field in fields.values() if field.sort]

    @classmethod
    def get_field(cls, name) -> TypesenseField:
        """
        Get the field with the provided name from the collection

        Args:
            name: the field name

        Returns:
            A TypesenseField
        """
        fields = cls.get_fields()
        return fields[name]

    @cached_property
    def schema_fields(self) -> list:
        """
        Returns:
            A list of dictionaries with field attributes needed by typesense for schema creation
        """
        return [field.attrs for field in self.fields.values()]

    def _get_object_data(self, obj):
        return {field.name: field.value(obj) for field in self.fields.values()}

    @property
    def schema(self) -> dict:
        """
        Returns:
            The typesense schema
        """
        return {
            "name": self.schema_name,
            "fields": self.schema_fields,
            "default_sorting_field": self._meta["default_sorting_field"],
            "symbols_to_index": self._meta["symbols_to_index"],
            "token_separators": self._meta["token_separators"],
        }

    def create_typesense_collection(self):
        """
        Create a new typesense collection (schema) on the typesense server
        """
        try:
            client.collections.create(self.schema)
        except ObjectAlreadyExists:
            pass

    def update_typesense_collection(self):
        """
        Update the schema of an existing collection
        """
        try:
            current_schema = self.retrieve_typesense_collection()
        except ObjectNotFound:
            self.create_typesense_collection()
            current_schema = self.retrieve_typesense_collection()

        self.create_or_update_synonyms()

        schema_changes = {}
        field_changes = []

        # Update fields
        existing_fields = {field["name"]: field for field in current_schema["fields"]}
        schema_fields = {field["name"]: field for field in self.schema_fields}
        # The collection retrieved from typesense does not include the id field so we remove the one we added
        schema_fields.pop("id")

        dropped_fields_names = set(existing_fields.keys()).difference(
            schema_fields.keys()
        )
        field_changes.extend(
            [{"name": field_name, "drop": True} for field_name in dropped_fields_names]
        )

        for field in schema_fields.values():
            if field["name"] not in existing_fields.keys():
                field_changes.append(field)
            else:
                if field != existing_fields[field["name"]]:
                    field_changes.append({"name": field['name'], "drop": True})
                    field_changes.append(field)

        if field_changes:
            schema_changes["fields"] = field_changes

        if not schema_changes:
            logger.debug(f"No schema changes in {self.schema_name}")
            return

        return client.collections[self.schema_name].update(schema_changes)

    def drop_typesense_collection(self):
        """
        Drops a typesense collection from the typesense server
        """
        client.collections[self.schema_name].delete()

    def retrieve_typesense_collection(self):
        """
        Retrieve the details of a collection
        """
        return client.collections[self.schema_name].retrieve()

    def delete(self):
        if not self.data:
            return

        delete_params = {"filter_by": f"id:{[int(obj['id']) for obj in self.data]}"}

        try:
            return client.collections[self.schema_name].documents.delete(delete_params)
        except ObjectNotFound:
            pass

    def update(self):
        if not self.data:
            return

        try:
            return client.collections[self.schema_name].documents.import_(
                self.data, {"action": "upsert"}
            )
        except ObjectNotFound:
            self.create_typesense_collection()
            return client.collections[self.schema_name].documents.import_(
                self.data, {"action": "upsert"}
            )

    def create_or_update_synonyms(self):
        current_synonyms = {}
        for synonym in self.get_synonyms().get("synonyms", []):
            name = synonym.pop("id")
            current_synonyms[name] = synonym

        defined_synonyms = {}
        for synonym_data in self._synonyms:
            defined_synonyms.update(synonym_data)

        missing_synonyms_names = set(current_synonyms.keys()).difference(
            defined_synonyms.keys()
        )
        has_changes = False

        for synonym_name in missing_synonyms_names:
            has_changes = True
            self.delete_synonym(synonym_name)

        for synonym_name, synonym_data in defined_synonyms.items():
            if synonym_name not in current_synonyms:
                has_changes = True
                client.collections[self.schema_name].synonyms.upsert(
                    synonym_name, synonym_data
                )
            elif synonym_data != current_synonyms[synonym_name]:
                has_changes = True
                client.collections[self.schema_name].synonyms.upsert(
                    synonym_name, synonym_data
                )

        if has_changes:
            logger.debug(f"Synonyms updated in {self.schema_name}")
        else:
            logger.debug(f"No synonyms to update in {self.schema_name}")

    def get_synonyms(self) -> dict:
        """List all synonyms associated with this collection"""
        return client.collections[self.schema_name].synonyms.retrieve()

    def get_synonym(self, synonym_name) -> dict:
        """Retrieve a single synonym by name"""
        return client.collections[self.schema_name].synonyms[synonym_name].retrieve()

    def delete_synonym(self, synonym_name):
        """Delete the synonym with the given name associated with this collection"""
        return client.collections[self.schema_name].synonyms[synonym_name].delete()
