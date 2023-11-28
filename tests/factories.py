from datetime import date, timedelta

import factory

from tests.models import Artist, Genre, Library, Song


class ArtistFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"artist {n}")

    class Meta:
        model = Artist


class GenreFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"genre {n}")

    class Meta:
        model = Genre


class SongFactory(factory.django.DjangoModelFactory):
    title = factory.Sequence(lambda n: f"song {n}")
    genre = factory.SubFactory(GenreFactory)
    release_date = date(year=2023, month=3, day=23)
    duration = timedelta(minutes=3, seconds=35)
    description = factory.Sequence(lambda n: f"Song description {n}")

    class Meta:
        model = Song

    @factory.post_generation
    def artists(self, create, extracted, **kwargs):
        if not create:
            return

        if not extracted:
            extracted = [ArtistFactory()]
        self.artists.add(*extracted)


class LibraryFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"library {n}")

    class Meta:
        model = Library

    @factory.post_generation
    def songs(self, create, extracted, **kwargs):
        if not create:
            return

        if not extracted:
            extracted = [SongFactory()]
        self.songs.add(*extracted)
