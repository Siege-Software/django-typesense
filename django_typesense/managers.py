from django.db import models

from django_typesense.mixins import TypesenseModelMixin


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
