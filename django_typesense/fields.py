import json
from decimal import Decimal
from datetime import datetime, date, time
from typing import Optional
from operator import attrgetter

from django_typesense.utils import get_unix_timestamp

TYPESENSE_SCHEMA_ATTRS = [
    "name",
    "_field_type",
    "sort",
    "index",
    "optional",
    "facet",
    "infix",
    "locale",
    "stem",
]


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
        locale: str = "",
        stem: bool = False,
    ):
        self._value = value
        self._name = None
        self.sort = self._sort if sort is None else sort
        self.index = index
        self.optional = optional
        self.facet = facet
        self.infix = infix
        self.locale = locale
        self.stem = stem

    def __str__(self):
        return f"{self.name}"

    @property
    def field_type(self):
        return self._field_type

    @property
    def name(self):
        return self._name

    @property
    def attrs(self):
        _attrs = {k: getattr(self, k) for k in TYPESENSE_SCHEMA_ATTRS}
        _attrs["type"] = _attrs.pop("_field_type")
        return _attrs

    def value(self, obj):
        try:
            __value = attrgetter(self._value)(obj)
        except AttributeError as er:
            if self.optional:
                __value = None
            else:
                raise er

        if callable(__value):
            return __value()

        return __value

    def to_python(self, value):
        return value


class TypesenseCharField(TypesenseField):
    _field_type = "string"

    def value(self, obj):
        __value = super().value(obj)
        if isinstance(__value, str):
            return __value
        if __value is None:
            return ""
        return str(__value)


class TypesenseIntegerMixin(TypesenseField):
    def value(self, obj):
        _value = super().value(obj)

        if _value is None:
            return None
        try:
            return int(_value)
        except (TypeError, ValueError) as e:
            raise e.__class__(
                f"Field '{self.name}' expected a number but got {_value}.",
            ) from e


class TypesenseSmallIntegerField(TypesenseIntegerMixin):
    _field_type = "int32"
    _sort = True


class TypesenseBigIntegerField(TypesenseIntegerMixin):
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


class TypesenseDateTimeFieldBase(TypesenseField):
    _field_type = "int64"
    _sort = True

    def value(self, obj):
        _value = super().value(obj)

        if _value is None:
            return None

        if isinstance(_value, int):
            return _value

        _value = get_unix_timestamp(_value)

        return _value


class TypesenseDateField(TypesenseDateTimeFieldBase):
    def to_python(self, value):
        return date.fromtimestamp(value)


class TypesenseDateTimeField(TypesenseDateTimeFieldBase):
    def to_python(self, value):
        return datetime.fromtimestamp(value)


class TypesenseTimeField(TypesenseDateTimeFieldBase):
    def to_python(self, value):
        return datetime.fromtimestamp(value).time()


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


TYPESENSE_DATETIME_FIELDS = [
    TypesenseDateTimeField,
    TypesenseDateField,
    TypesenseTimeField,
]
