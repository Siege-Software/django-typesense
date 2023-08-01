import warnings

from django.core.paginator import Paginator, UnorderedObjectListWarning
from django.utils.functional import cached_property


class TypesenseSearchPaginator(Paginator):
    def __init__(
        self, object_list, per_page, orphans=0, allow_empty_first_page=True, model=None
    ):
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self.model = model

    def page(self, number):
        """Return a Page object for the given 1-based page number."""
        # CREATE UNSAVED MODEL INSTANCES
        # TODO: Make sure no action like .save(), .delete() are used/attempted on them
        object_list = [
            self.model(**result["document"])
            for result in self.object_list["hits"]
        ]
        return self._get_page(object_list, number, self)

    @cached_property
    def count(self):
        """Return the total number of objects, across all pages."""
        return self.object_list["found"]
