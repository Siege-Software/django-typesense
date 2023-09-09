import copy

from django.core.paginator import Paginator
from django.utils.functional import cached_property


class TypesenseSearchPaginator(Paginator):
    def __init__(
        self, object_list, per_page, orphans=0, allow_empty_first_page=True, model=None
    ):
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self.model = model
        self.collection_class = self.model.get_collection_class()
        self.results = self.prepare_results()

    def prepare_results(self):
        """
        Do whatever is required to present the values correctly in the admin.
        """
        documents = (hit['document'] for hit in self.object_list["hits"])
        collection = self.model.get_collection(data=documents)
        model_field_names = set((local_field.name for local_field in self.model._meta.local_fields))
        results = []

        for _data in collection.validated_data:
            data = copy.deepcopy(_data)
            properties = {}

            for field_name in collection.fields.keys():
                if field_name not in model_field_names:
                    properties[field_name] = data.pop(field_name)

            result_instance = self.model(**data)
            for key, value in properties.items():
                try:
                    setattr(result_instance, key, value)
                except AttributeError:
                    # non-data descriptors
                    result_instance.__dict__[key] = value

            results.append(result_instance)

        return results

    def page(self, number):
        """Return a Page object for the given 1-based page number."""
        return self._get_page(self.results, number, self)

    @cached_property
    def count(self):
        """Return the total number of objects, across all pages."""
        return self.object_list["found"]
