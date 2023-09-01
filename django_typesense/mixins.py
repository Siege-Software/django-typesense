from django.db import models

from django_typesense.managers import TypesenseQuerySet


class TypesenseModelMixin(models.Model):
    collection_class = None
    objects = TypesenseQuerySet.as_manager()

    class Meta:
        abstract = True

    @classmethod
    def get_collection_class(cls):
        """
        Return the class to use for the typesense collection.
        Defaults to using `self.collection_class`.
        """
        assert cls.collection_class is not None, (
            "'%s' should either include a `collection_class` attribute, "
            "or override the `get_collection_class()` method."
            % cls.__name__
        )

        return cls.collection_class

    @classmethod
    def get_collection(cls, *args, **kwargs):
        """
        Return the collection obj.
        """
        collection_class = cls.collection_class()
        return collection_class(*args, **kwargs)
