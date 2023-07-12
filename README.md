# Setting up model

# 1. Update the model to inherit from the Typesense model mixin

```
from apps.search.models import TypeSenseMixin, TypesenseUpdateDeleteQuerySetManager

class MyModelManager(models.Manager):
    """Manager for class :class:`.models.MyModelName`
    """
    field1 = models...
    field2 = models...
    field3 = models...
    date_created = models...
    
    typesense_fields = [
        {
            "name": "field1", "type": "string",
        },
        {
            "name": "field2", "type": "string"
        },
        {
            "name": "field3", "type": "string"
        },
        {
            "name": "date_created", "type": "int64"
        }
    ]

    typesense_default_sorting_field = 'date_created'
    query_by_fields = ','.join(
        [
            'field1', 'field2', 'date_created'
        ]
    )

    def get_typesense_dict(self):
        """Create a data structure that can be serialized as JSON for Typesense fields.

        Normalize the structure if required.

        Returns:
            dict: JSON-serializable data structure
        """

        typesense_dict = {
            'id': str(self.id),
            'field1': self.field1,
            'field2': self.field2,
            'field3': self.field3,
             'date_created': self.date_created.timestamp()
        }

        return typesense_dict

    def get_queryset(self):
        """
        Get an optimized queryset.

        Returns:
            django.db.models.query.QuerySet: Queryset with instances of \
            :class:`.models.Work`
        """
        return TypesenseUpdateDeleteQuerySetManager(
            self.model, using=self._db
        )


class MyModelName(TypeSenseMixin)
    ...
    
    objects = MyModelManager()
```

`TypesenseUpdateDeleteQuerySetManager` is required to automatically index model changes on create, update and delete

# 2. Admin Setup
To update a model admin to display and search from the model Typesense collection, the admin class should inherit from the TypesenseSearchAdminMixin

```
from apps.search.admin import TypesenseSearchAdminMixin

class MyModelAdmin(TypesenseSearchAdminMixin)

    #  typesense_list_fields lists the fields that will be displayed in admin
    typesense_list_fields = [
        'field1', 'field2', 'field3', 'date_creatd'
    ]
    typesense_list_date_fields = ['date_created']
    
    def search_typesense(self, request, **kwargs):

    user = request.user
    sort_by = 'date_created:desc'
    template_name = 'admin/work/change_list.html'

    query_by_fields = [
        {
            'admin_field': 'field1',
            'typesense_field': 'field1'
        },
        {
            'admin_field': 'field2',
            'typesense_field': 'field2',
            'boolean': True
        },
        {
            'admin_field': 'is_x',
            'typesense_field': 'is_x',
            'reverse_field': 'is_y',  #  Reverse field is used to negate another field based on another field
            'boolean': True
        }
    ]

    filter_by_query = self.get_query_by_string(request, query_by_fields)

    return super().search_typesense(request, template_name=template_name, sort_by=sort_by, filter_by=filter_by_query)

```

# 3. Bulk indexing typesense collections
To update or delete collection documents in bulk

```
from apps.search.methods import bulk_delete_typsense_records, bulk_update_typsense_records
from .models import MyModel
from apps.search.settings.typesense_client import client

model_qs = Model.objects.all().order_by('date_created')  # querysets should be ordered
bulk_update_typesense_records(model_qs)  # for bulk document indexing
bulk_delete_typsense_records(model_qs)  # for bulk document deletiom
```

