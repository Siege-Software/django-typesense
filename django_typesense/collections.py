from typing import Optional, List, Iterable, Any

from django.db import models
from django.db.models import QuerySet
from typesense.exceptions import ObjectNotFound

from django_typesense.fields import TypesenseField, TypesenseCharField
from django_typesense.typesense_client import client


class TypesenseCollection:

    class Meta:
        model: Optional[models.Model]
        schema_name: Optional[str]
        default_sorting_field: Optional[str]
        token_separators: Optional[list]
        symbols_to_index: Optional[list]
        query_by_fields: str

    def __init__(self, obj: Optional[object, QuerySet, Iterable] = None, many: bool = False, data: list = None):
        assert any([obj, data]), "Either `obj` or `data` must be provided"
        assert not all([obj, data]), "`obj` and `data` cannot be provided together"

        if obj:
            if many:
                self.data = list(map(self._get_object_data, obj))
            else:
                self.data = [self._get_object_data(obj)]
        else:
            self.data = data

    @property
    def validated_data(self):
        # TODO: Validate self.data against schema fields
        _validated_data = []

        for obj in self.data:
            for key, value in obj:
                field = self.get_field(key)
                _validated_data[key] = field.to_python(value)

        return _validated_data

    def __str__(self):
        return f"{self.schema_name} TypesenseCollection"

    @property
    def sortable_fields(self):
        return [field.name for field in self.fields if field.sort]

    @property
    def fields(self):
        return self.get_fields()

    @property
    def schema_name(self):
        return self.Meta.schema_name or self.Meta.model.__name__.lower()

    def get_field(self, name):
        return self.fields[name]

    def get_fields(self):
        fields = {}

        for k, v in dir(self):
            if not issubclass(v, TypesenseField):
                continue

            v._name = k
            v._value = v._value or k
            fields[k] = v

        # Auto adds id if absent
        if not fields.get('id'):
            _id = TypesenseCharField(sort=True, value='pk')
            _id._name = 'id'
            fields['id'] = _id

        return fields

    @property
    def schema_fields(self):
        fields = [field.attrs for field in self.fields.values()]
        return fields

    def _get_object_data(self, obj):
        _data = {}
        for field in self.get_fields():
            _data[field.name] = field.value(obj)
        return _data

    @property
    def schema(self):
        return {
            "name": self.schema_name,
            "fields": self.schema_fields,
            "default_sorting_field": self.Meta.default_sorting_field,
            "symbols_to_index": self.Meta.symbols_to_index,
            "token_separators": self.Meta.token_separators
        }

    def create_typesense_collection(self):
        """
        Create a new typesense collection on the typesense server
        """
        client.collections.create(self.schema)

    def drop_typesense_collection(self):
        """
        Drops a typesense collection from the typesense server
        """
        client.collections[self.schema_name].delete()

    def retrieve_typesense_collection(self):
        return client.collections[self.schema_name].retrieve()

    def delete(self):
        delete_params = {
            "filter_by": f"id:{[obj['id'] for obj in self.data]}"
        }

        try:
            client.collections[self.schema_name].documents.delete(delete_params)
        except ObjectNotFound:
            pass

    def update(self):
        try:
            client.collections[self.schema_name].documents.import_(self.data, {"action": "upsert"})
        except ObjectNotFound:
            self.create_typesense_collection()
            client.collections[self.schema_name].documents.import_(self.data, {"action": "upsert"})
