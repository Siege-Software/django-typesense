from django.test import TestCase

from django_typesense.mixins import TypesenseManager

from tests.factories import ArtistFactory, GenreFactory, SongFactory
from tests.models import Song
from tests.utils import get_document


class TestTypeSenseMixin(TestCase):
    def setUp(self):
        self.genre = GenreFactory()
        self.artist = ArtistFactory()
        self.song = SongFactory(genre=self.genre, artists=[self.artist])

    def test_get_collection_class(self):
        collection_class = Song.get_collection_class()
        self.assertEqual(collection_class.__name__, "SongCollection")

    def test_typesense_manager(self):
        self.assertIsInstance(Song.objects, TypesenseManager)

    def test_update_collection(self):
        schema_name = self.song.collection_class.schema_name
        song_document = get_document(schema_name, self.song.pk)
        self.assertEqual(song_document["genre_name"], self.song.genre.name)

        genre_name = "Dancehall"
        self.genre.name = genre_name
        self.genre.save(update_fields=["name"])

        song_document = get_document(schema_name, self.song.pk)
        self.assertNotEqual(song_document["genre_name"], self.song.genre.name)
        self.assertEqual(self.song.genre.name, genre_name)

        Song.objects.get_queryset().update()
        song_document = get_document(schema_name, self.song.pk)
        self.assertEqual(song_document["genre_name"], genre_name)
        self.assertEqual(song_document["genre_name"], self.song.genre.name)

    def test_delete_collection(self):
        schema_name = self.song.collection_class.schema_name
        song_document = get_document(schema_name, self.song.pk)
        self.assertEqual(song_document["title"], self.song.title)

        Song.objects.get_queryset().delete()

        song_document = get_document(schema_name, self.song.pk)
        self.assertIsNone(song_document)
