from datetime import datetime

from django.core.paginator import Paginator
from django.db import models
from django.utils.functional import cached_property


class TypesenseSearchPaginator(Paginator):
    def __init__(
        self, object_list, per_page, orphans=0, allow_empty_first_page=True, model=None
    ):
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self.model = model
        self.results = []
        self.mofify_results()

    def mofify_results(self):
        """
        Do whatever is required to present the values correctly in the admin

        Returns:
            A list of model instances
        """

        model_field_names = set((local_field.name for local_field in self.model._meta.local_fields))
        fields_to_remove = set(self.model.typesense_fields.keys()).difference(model_field_names)
        date_fields = (models.fields.DateTimeField, models.fields.DateField, models.fields.TimeField)

        def get_result(hit):
            result = {}
            for key, value in hit['document'].items():
                if key in fields_to_remove:
                    continue
                if isinstance(self.model._meta.get_field(key), date_fields) and value:
                    value = datetime.fromtimestamp(value)

                result.update({key:value})

                # TODO: set foreignkeys
            return result

        self.results = list(map(get_result, self.object_list["hits"]))

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
