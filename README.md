# django typesense
[![codecov](https://codecov.io/gh/Siege-Software/django-typesense/branch/main/graph/badge.svg?token=S4W0E84821)](https://codecov.io/gh/Siege-Software/django-typesense)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![PyPI download month](https://img.shields.io/pypi/dm/django-typesense.svg)
[![PyPI version](https://badge.fury.io/py/django-typesense.svg)](https://pypi.python.org/pypi/django-typesense/)
![Python versions](https://img.shields.io/badge/python-%3E%3D3.8-brightgreen)
![Django Versions](https://img.shields.io/badge/django-%3E%3D4-brightgreen)


> [!WARNING]  
> **This package is in the initial development phase. Do not use in production environment.**

## What is it?
Faster Django Admin powered by [Typesense](https://typesense.org/)

## TODOs
- Performance comparison stats

## Note on ForeignKeys and OneToOneFields
- While data from foreign keys can be indexed, displaying them on the admin will trigger database queries that will negatively affect performance.
- We recommend indexing the string representation of the foreignkey as a model property to enable display on admin.

## How to use
`pip install django-typesense`

Install directly from github to test the most recent version
```
pip install git+https://github.com/SiegeSoftware/django-typesense.git
```

Add `django_typesense` to the list of installed apps.
You will need to set up the typesense server on your machine.

### Update the model to inherit from the Typesense model mixin

```
from django_typesense.models import TypesenseModelMixin, TypesenseQuerySet

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
            "name": "field2", "type": "int64"
        },
        {
            "name": "field3", "type": "string[]"
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
        """
        Create a data structure that can be serialized as JSON for Typesense fields.

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
        return TypesenseQuerySet(
            self.model, using=self._db
        )


class MyModelName(TypesenseModelMixin)
    ...
    
    objects = MyModelManager()
```

`TypesenseQuerySet` is required to automatically index model changes on create, update and delete

### Admin Setup
To update a model admin to display and search from the model Typesense collection, the admin class should inherit from the TypesenseSearchAdminMixin

```
from django_typesense.admin import TypesenseSearchAdminMixin

class MyModelAdmin(TypesenseSearchAdminMixin):
    pass

```

### Bulk indexing typesense collections
To update or delete collection documents in bulk. Bulk updating is multi-threaded. 
You might encounter poor performance when indexing large querysets. Suggestions on how to improve are welcome.

```
from django_typesense.methods import bulk_delete_typsense_records, bulk_update_typsense_records
from .models import MyModel
from django_typesense.typesense_client import client

model_qs = Model.objects.all().order_by('date_created')  # querysets should be ordered
bulk_update_typesense_records(model_qs)  # for bulk document indexing
bulk_delete_typsense_records(model_qs)  # for bulk document deletiom
```

# Custom Admin Filters
To make use of custom admin filters, define a `filter_by` property in the filter definition.
Define boolean typesense field `has_alien` that gets it's value from a model property.

```
@property
def has_alien(self):
    # moon_aliens and mars_aliens are reverse foreign keys
    return self.moon_aliens.exists() or self.mars_aliens.exists()
```

```
class HasAlienFilter(admin.SimpleListFilter):
    title = _('Has Alien')
    parameter_name = 'has_alien'

    def lookups(self, request, model_admin):
        return (
            ('all', 'All'),
            ('True', 'Yes'),
            ('False', 'No')
        )

    def queryset(self, request, queryset):
        # This is used by the default django admin
        if self.value() == 'True':
            return queryset.filter(Q(mars_aliens__isnull=False) | Q(moon_aliens__isnull=False))
        elif self.value() == 'False':
            return queryset.filter(mars_aliens__isnull=True, moon_aliens__isnull=True)
            
        return queryset

    @property
    def filter_by(self):
        # This is used by typesense
        if self.value() == 'True':
            return {"has_alien": "=true"}
        elif self.value() == 'False':
            return {"has_alien": "!=false"}

        return {}
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
