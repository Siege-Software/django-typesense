# django typesense

[![Build](https://github.com/Siege-Software/django-typesense/workflows/build/badge.svg?branch=main)](https://github.com/Siege-Software/django-typesense/actions?workflow=CI)
[![codecov](https://codecov.io/gh/Siege-Software/django-typesense/branch/main/graph/badge.svg?token=S4W0E84821)](https://codecov.io/gh/Siege-Software/django-typesense)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![PyPI download month](https://img.shields.io/pypi/dm/django-typesense.svg)
[![PyPI version](https://badge.fury.io/py/django-typesense.svg)](https://pypi.python.org/pypi/django-typesense/)
![Python versions](https://img.shields.io/badge/python-%3E%3D3.8-brightgreen)
![Django Versions](https://img.shields.io/badge/django-%3E%3D3.2-brightgreen)
[![PyPI License](https://img.shields.io/pypi/l/django-typesense.svg)](https://pypi.org/project/django-typesense/)


## What is it?
Faster Django Admin powered by [Typesense](https://typesense.org/)

## Quick Start Guide
### Installation
`pip install django-typesense`

or install directly from github to test the most recent version

`pip install git+https://github.com/Siege-Software/django-typesense.git`

Add `django_typesense` to the list of installed apps.

Follow this [guide](https://typesense.org/docs/guide/install-typesense.html#option-1-typesense-cloud) to install and run typesense

### Create Collections
Throughout this guide, we’ll refer to the following models, which comprise a song catalogue application:

```
from django.db import models


class Genre(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Artist(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Song(models.Model):
    title = models.CharField(max_length=100)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    release_date = models.DateField(blank=True, null=True)
    artists = models.ManyToManyField(Artist)
    number_of_comments = models.IntegerField(default=0)
    number_of_views = models.IntegerField(default=0)
    duration = models.DurationField()
    description = models.TextField()

    def __str__(self):
        return self.title
     
    @property
    def release_date_timestamp(self):
        # read https://typesense.org/docs/0.25.0/api/collections.html#indexing-dates
        return self.release_date.timestamp() if self.release_date else self.release_date
      
    def artist_names(self):
        return list(self.artists.all().values_list('name', flat=True))
        
```

For such an application, you might be interested in improving the search and load times on the song records list view.

```
from django_typesense.collections import TypesenseCollection
from django_typesense import fields


class SongCollection(TypesenseCollection):
    # At least one of the indexed fields has to be provided as one of the `query_by_fields`. Must be a CharField
    query_by_fields = 'title,artist_names,genre_name'
    
    title = fields.TypesenseCharField()
    genre_name = fields.TypesenseCharField(value='genre.name')
    genre_id = fields.TypesenseSmallIntegerField()
    release_date = fields.TypesenseDateField(value='release_date_timestamp', optional=True)
    artist_names = fields.TypesenseArrayField(base_field=fields.TypesenseCharField(), value='artist_names')
    number_of_comments = fields.SmallIntegerField(index=False, optional=True)
    number_of_views = fields.SmallIntegerField(index=False, optional=True)
    duration = fields.DurationField()
```

It's okay to store fields that you don't intend to search but to display on the admin. Such fields should be marked as un-indexed e.g:

    number_of_views = fields.SmallIntegerField(index=False, optional=True)

Update the song model as follows:
```
from django_typesense.mixins import TypesenseModelMixin

class Song(TypesenseModelMixin):
    ...
    collection_class = SongCollection
    ...
```

The `TypesenseModelMixin` provides a Manager that overrides the `update` and `delete` methods of the Queryset.
If your model has a custom manager, make sure the custom manager inherits `django_typesense.mixin.TypesenseManager`

How the value of a field is retrieved from a model instance:
1. The collection field name is called as a property of the model instance
2. If `value` is provided, it will be called as a property or method of the model instance

Where the collections live is totally dependent on you but we recommend having a `collections.py` file
in the django app where the model you are creating a collection for is.

> [!NOTE]  
> We recommend displaying data from ForeignKey or OneToOne fields as string attributes using the display decorator to
> avoid triggering database queries that will negatively affect performance 
> [Issue #16](https://github.com/Siege-Software/django-typesense/issues/16).

Instead of this in the admin:
```
@admin.display('Genre')
def genre_name(self, obj):
    return obj.genre.name
```

Do this:

```
@admin.display('Genre')
def genre_name(self, obj):
    # genre_name is field in the Collection. You can also store the object url as html
    return obj.genre_name
```

### Update Collection Schema
To add or remove fields to a collection's schema in place, update your collection then run:
    `python manage.py updatecollections`. Consider adding this to your CI/CD pipeline.

This also updates the [synonyms](#synonyms)


### How updates are made to Typesense
1. Signals -
`django-typesense` listens to signal events (`post_save`, `pre_delete`, `m2m_changed`) to update typesense records. 
If [`update_fields`](https://docs.djangoproject.com/en/4.2/ref/models/instances/#specifying-which-fields-to-save)
were provided in the save method, only these fields will be updated in typesense.

2. Update query -
`django-typesense` overrides Django's `QuerySet.update` to make updates to typesense on the specified fields

3. Manual -
You can also update typesense records manually e.g after doing a `bulk_create`
```
objs = Song.objects.bulk_create(
    [
      Song(title="Watch What I Do"),
      Song(title="Midnight City"),
   ]
)
collection = SongCollection(objs, many=True)
collection.update()
```

### Admin Integration
To make a model admin display and search from the model's Typesense collection, the admin class should
inherit `TypesenseSearchAdminMixin`. This also adds Live Search to your admin changelist view.

```
from django_typesense.admin import TypesenseSearchAdminMixin

@admin.register(Song)
class SongAdmin(TypesenseSearchAdminMixin):
    ...
    list_display = ['title', 'genre_name', 'release_date', 'number_of_views', 'duration']
    
    @admin.display(description='Genre')
    def genre_name(self, obj):
        return obj.genre.name
    ...

```

### Indexing
For the initial setup, you will need to index in bulk. Bulk updating is multi-threaded. Depending on your system specs, you should set the `batch_size` keyword argument.

```
from django_typesense.utils import bulk_delete_typsense_records, bulk_update_typsense_records

model_qs = Song.objects.all().order_by('id')  # querysets should be ordered
bulk_update_typesense_records(model_qs, batch_size=1024)
```

### Custom Admin Filters
To make use of custom admin filters, define a `filter_by` property in the filter definition.
Define boolean typesense field `has_views` that gets it's value from a model property. This is example is not necessarily practical but for demo purposes.

```
# models.py
class Song(models.Model):
    ...
    @property
    def has_views(self):
        return self.number_of_views > 0
    ...

# collections.py
class SongCollection(TypesenseCollection):
    ...
    has_views = fields.TypesenseBooleanField()
    ...
```

```
class HasViewsFilter(admin.SimpleListFilter):
    title = _('Has Views')
    parameter_name = 'has_views'

    def lookups(self, request, model_admin):
        return (
            ('all', 'All'),
            ('True', 'Yes'),
            ('False', 'No')
        )

    def queryset(self, request, queryset):
        # This is used by the default django admin
        if self.value() == 'True':
            return queryset.filter(number_of_views__gt=0)
        elif self.value() == 'False':
            return queryset.filter(number_of_views=0)
            
        return queryset

    @property
    def filter_by(self):
        # This is used by typesense
        if self.value() == 'True':
            return {"has_views": "=true"}
        elif self.value() == 'False':
            return {"has_views": "!=false"}

        return {}
```

Note that simple lookups like the one above are done by default (hence no need to define `filter_by`) if 
the `parameter_name` is a field in the collection

### Synonyms
The [synonyms](https://typesense.org/docs/0.25.1/api/synonyms.html) feature allows you to define search terms that 
should be considered equivalent. Synonyms should be defined with classes that inherit from `Synonym`

```
from django_typesense.collections import Synonym

# say you need users searching the genre hip-hop to get results if they use the search term rap

class HipHopSynonym(Synonym):
    name = 'hip-hop-synonyms'
    synonyms = ['hip-hop', 'rap']
 
# Update the collection to include the synonym
class SongCollection(TypesenseCollection):
    ...
    synonyms = [HipHopSynonym]
    ...
    
```
To update the collection with any changes made to synonyms run `python manage.py updatecollections`


