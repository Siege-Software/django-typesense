from django.db import models
from django.utils import dateformat

from django_typesense.mixins import TypesenseManager, TypesenseModelMixin
from tests.collections import SongCollection


class Genre(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Artist(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class SongManager(TypesenseManager):
    def do_something(self):
        return None


class Song(TypesenseModelMixin):
    title = models.CharField(max_length=100)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    release_date = models.DateField(blank=True, null=True)
    artists = models.ManyToManyField(Artist)
    number_of_comments = models.IntegerField(default=0)
    number_of_views = models.IntegerField(default=0)
    duration = models.DurationField()
    description = models.TextField()
    collection_class = SongCollection

    objects = SongManager()

    def __str__(self):
        return self.title

    @property
    def release_date_timestamp(self):
        return (
            int(dateformat.format(self.release_date, "U"))
            if self.release_date
            else self.release_date
        )

    def artist_names(self):
        return list(self.artists.all().values_list("name", flat=True))
