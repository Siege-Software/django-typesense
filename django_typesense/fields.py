import json
from decimal import Decimal
from datetime import datetime, date
from typing import Optional
from operator import attrgetter


class TypesenseField:
    _attrs = None
    _field_type = None
    _sort = False

    def __init__(
        self,
        value: Optional[str] = None,
        sort: bool = None,
        index: bool = True,
        optional: bool = False,
        facet: bool = False,
        infix: bool = False,
        locale: str = ''
    ):
        self._value = value
        self._name = None
        self.sort = self._sort if sort is None else sort
        self.index = index
        self.optional = optional
        self.facet = facet
        self.infix = infix
        self.locale = locale

    def __str__(self):
        return f"{self}: {self.name}"

    @property
    def name(self):
        return self._name

    @property
    def attrs(self):
        return {
            'name': self.name,
            'type': self._field_type,
            'sort': self.sort,
            'index': self.index,
            'optional': self.optional,
            'facet': self.facet,
            'infix': self.infix,
            'locale': self.locale
        }

    def value(self, obj):
        __value = attrgetter(self._value)(obj)
        if callable(__value):
            return __value()

        return __value

    def to_python(self, value):
        return value


class TypesenseCharField(TypesenseField):
    _field_type = "string"

    def value(self, obj):
        __value = super().value(obj)
        return str(__value) if __value else __value


class TypesenseSmallIntegerField(TypesenseField):
    _field_type = "int32"
    _sort = True


class TypesenseBigIntegerField(TypesenseField):
    _field_type = "int64"
    _sort = True


class TypesenseFloatField(TypesenseField):
    _field_type = "float"
    _sort = True


class TypesenseDecimalField(TypesenseField):
    """
    String type is preferred over float
    """
    _field_type = "string"
    _sort = True

    def value(self, obj):
        __value = super().value(obj)
        return str(__value)

    def to_python(self, value):
        return Decimal(value)


class TypesenseBooleanField(TypesenseField):
    _field_type = "bool"
    _sort = True


class TypesenseDateField(TypesenseBigIntegerField):
    def to_python(self, value):
        return date.fromtimestamp(value)


class TypesenseDateTimeField(TypesenseBigIntegerField):
    def to_python(self, value):
        return datetime.fromtimestamp(value)


class TypesenseJSONField(TypesenseField):
    """
    `string` is preferred over `object`
    """
    _field_type = "string"

    def value(self, obj):
        __value = super().value(obj)
        return json.dumps(__value, default=str)

    def to_python(self, value):
        return json.loads(value)


class TypesenseArrayField(TypesenseField):
    def __init__(self, base_field: TypesenseField, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_field = base_field
        self._field_type = f"{self.base_field._field_type}[]"

    def to_python(self, value):
        return list(map(self.base_field.to_python, value))
