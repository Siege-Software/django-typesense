from django.db import models


class TypesenseQuerySet(models.QuerySet):
    def delete(self):
        assert issubclass(self.model, TypesenseModelMixin), (
            f"Model `{self.model}` must inherit `TypesenseMixin` to use the TypesenseQueryset Manager"
        )
        collection = self.model.get_collection(self, many=True)
        collection.delete()
        return super().delete()

    def update(self, **kwargs):
        assert issubclass(self.model, TypesenseModelMixin), (
            f"Model `{self.model}` must inherit `TypesenseMixin` to use the TypesenseQueryset Manager"
        )
        collection = self.model.get_collection(self, many=True)
        collection.update()
        return super().update(**kwargs)


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
        collection_class = cls.get_collection_class()
        return collection_class(*args, **kwargs)

