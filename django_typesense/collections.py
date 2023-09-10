import copy
from typing import Optional, List, Iterable, Any, Union, Dict

from django.db import models
from django.db.models import QuerySet
from django.utils.functional import cached_property, classproperty
from typesense.exceptions import ObjectNotFound

from django_typesense.fields import TypesenseField, TypesenseCharField
from django_typesense.typesense_client import client

_COLLECTION_META_OPTIONS = {
    'schema_name', 'default_sorting_field', 'token_separators', 'symbols_to_index', 'query_by_fields'
}


class TypesenseCollectionMeta(type):

    def __new__(cls, name, bases, namespace):
        namespace['schema_name'] = namespace.get('schema_name') or name.lower()
        return super().__new__(cls, name, bases, namespace)


class TypesenseCollection(metaclass=TypesenseCollectionMeta):

    query_by_fields: str = ''
    schema_name: Optional[str] = ''
    default_sorting_field: Optional[str] = ''
    token_separators: Optional[list] = []
    symbols_to_index: Optional[list] = []

    def __init__(self, obj: Union[object, QuerySet, Iterable] = None, many: bool = False, data: list = None):
        assert self.query_by_fields, "`query_by_fields` must be specified in the collection definition"
        assert not all([obj, data]), "`obj` and `data` cannot be provided together"

        self.schema_name = self.schema_name or self.__class__.__name__.lower()
        self._meta = self._get_metadata()
        self.fields = self.get_fields()

        # TODO: Make self.data a cached_property
        if data:
            self.data = data
        elif obj:
            if many:
                self.data = list(map(self._get_object_data, obj))
            else:
                self.data = [self._get_object_data(obj)]

    def get_fields(self) -> Dict[str, TypesenseField]:
        fields = {}

        for attr in dir(self):
            attr_value = getattr(self, attr, None)
            if not isinstance(attr_value, TypesenseField):
                continue

            attr_value._name = attr
            attr_value._value = attr_value._value or attr
            fields[attr] = attr_value

        # Auto adds id if absent
        if not fields.get('id'):
            _id = TypesenseCharField(sort=True, value='pk')
            _id._name = 'id'
            fields['id'] = _id

        return fields

    @classmethod
    def _get_metadata(cls):
        defined_meta_options = _COLLECTION_META_OPTIONS.intersection(set(dir(cls)))
        return {meta_option: getattr(cls, meta_option) for meta_option in defined_meta_options}

    @cached_property
    def validated_data(self):
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

    @property
    def sortable_fields(self):
        return [field.name for field in self.fields.values() if field.sort]

    def get_field(self, name):
        return self.fields[name]

    @cached_property
    def schema_fields(self):
        return [field.attrs for field in self.fields.values()]

    def _get_object_data(self, obj):
        return {field.name: field.value(obj) for field in self.fields.values()}

    @cached_property
    def schema(self):
        return {
            "name": self.schema_name,
            "fields": self.schema_fields,
            "default_sorting_field": self._meta['default_sorting_field'],
            "symbols_to_index": self._meta['symbols_to_index'],
            "token_separators": self._meta['token_separators']
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
            return client.collections[self.schema_name].documents.delete(delete_params)
        except ObjectNotFound:
            pass

    def update(self):
        try:
            return client.collections[self.schema_name].documents.import_(self.data, {"action": "upsert"})
        except ObjectNotFound:
            self.create_typesense_collection()
            return client.collections[self.schema_name].documents.import_(self.data, {"action": "upsert"})
