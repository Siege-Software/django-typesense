from django.core.paginator import Paginator
from django.utils.functional import cached_property


class TypesenseModel(object):
    def __init__(self, _data, _metadata):
        for key in _data:
            setattr(self, key, _data[key])
        self._meta = _metadata

    @property
    def pk(self):
        return getattr(self, 'id')


class TypesenseSearchPaginator(Paginator):
    def __init__(
        self, object_list, per_page, orphans=0, allow_empty_first_page=True, model=None
    ):
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self.model = model
        self.results = self.prepare_results()

    def prepare_results(self):
        """
        Do whatever is required to present the values correctly in the admin.
        """
        documents = (hit['document'] for hit in self.object_list["hits"])
        data_list = self.model.get_collection(data=documents).validated_data
        metadata = self.model._meta
        return [TypesenseModel(data, metadata) for data in data_list]

    def page(self, number):
        """Return a Page object for the given 1-based page number."""
        return self._get_page(self.results, number, self)

    @cached_property
    def count(self):
        """Return the total number of objects, across all pages."""
        return self.object_list["found"]
