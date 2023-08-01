# django typesense
[![codecov](https://codecov.io/gh/Siege-Software/django-typesense/branch/main/graph/badge.svg?token=S4W0E84821)](https://codecov.io/gh/Siege-Software/django-typesense)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## What is it?
TBA

Some concepts were borrowed from [django-typesense](https://github.com/jkoestinger/django-typesense)

# Setting up model

# 1. Update the model to inherit from the Typesense model mixin

```
from django_typesense.models import TypeSenseMixin, TypesenseUpdateDeleteQuerySetManager

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
from django_typesense.admin import TypesenseSearchAdminMixin

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
from django_typesense.methods import bulk_delete_typsense_records, bulk_update_typsense_records
from .models import MyModel
from django_typesense.typesense_client import client

model_qs = Model.objects.all().order_by('date_created')  # querysets should be ordered
bulk_update_typesense_records(model_qs)  # for bulk document indexing
bulk_delete_typsense_records(model_qs)  # for bulk document deletiom
```
## Release Process
Each release has its own branch, called stable/version_number and any changes will be issued from those branches. 
The main branch has the latest stable version

## Contribution
TBA

```
# clone the repo
git clone https://gitlab.com/siege-software/packages/django_typesense.git
git checkout -b <your_branch_name> stable/1.x.x

# Set up virtual environment
python3.8 -m venv venv
source venv/bin/activate

pip install -r requirements-dev.txt

# Enable automatic pre-commit hooks
pre-commit install
```

## Running Tests
```
cd tests
pytest .
```

## Building the package
```python -m build```

## Installing the package from build
``` pip install path/to/django_typesense-0.0.1.tar.gz```
