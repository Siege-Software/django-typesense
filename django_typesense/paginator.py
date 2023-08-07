from django.core.paginator import Paginator
from django.utils.functional import cached_property


class TypesenseSearchPaginator(Paginator):
    def __init__(
        self, object_list, per_page, orphans=0, allow_empty_first_page=True, model=None
    ):
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self.model = model

        model_field_names = set((local_field.name for local_field in self.model._meta.local_fields))
        typesense_field_names = [field['name'] for field in self.model.typesense_fields]
        fields_to_remove = set(typesense_field_names).difference(model_field_names)
        self.results = [result["document"] for result in self.object_list["hits"]]

        # Remove values that are not model fields
        [result.pop(key) for result in self.results for key in fields_to_remove]

    def page(self, number):
        """Return a Page object for the given 1-based page number."""
        # CREATE UNSAVED MODEL INSTANCES
        # TODO: Make sure no action like .save(), .delete() are used/attempted on them
        return self._get_page(
            [self.model(**result) for result in self.results], number, self
        )

    @cached_property
    def count(self):
        """Return the total number of objects, across all pages."""
        return self.object_list["found"]
