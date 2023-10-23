from datetime import date, timedelta

from django.test import TestCase
from typesense import exceptions

from django_typesense.typesense_client import client

from tests.models import Artist, Genre, Song


class TestTypeSenseMixin(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name="artist1")
        self.genre = Genre.objects.create(name="genre1")
        self.song = Song.objects.create(
            title="New Song",
            genre=self.genre,
            release_date=date.today(),
            description="New song description",
            duration=timedelta(minutes=3, seconds=35),
        )
        self.song.artists.add(self.artist.pk)

    def get_document(self, schema_name, document_id):
        try:
            return client.collections[schema_name].documents[document_id].retrieve()
        except exceptions.ObjectNotFound:
            return None

    def test_get_typesense_schema_name(self):
        """
        Test that the get_typesense_schema_name() method returns the correct schema name.
        """
        self.assertEqual(self.song.collection_class.schema_name, "songcollection")

    def test_get_typesense_fields(self):
        """
        Test that the get_typesense_fields() method returns a list of fields.
        """
        schema_fields = [
            "id",
            "title",
            "genre_name",
            "genre_id",
            "release_date",
            "artist_names",
            "number_of_comments",
            "number_of_views",
        ]
        song_schema_fields = self.song.collection_class.get_fields().keys()
        self.assertCountEqual(song_schema_fields, schema_fields)

    def test_get_typesense_dict(self):
        """
        Test that the get_typesense_dict() method returns a dictionary of typesense document data.
        """
        schema_name = self.song.collection_class.schema_name
        song_document = self.get_document(schema_name, self.song.pk)

        self.assertEqual(song_document["title"], self.song.title)
        self.assertEqual(
            song_document["release_date"], self.song.release_date_timestamp
        )
        self.assertEqual(song_document["genre_id"], self.song.genre.pk)
        self.assertEqual(song_document["genre_name"], self.song.genre.name)
        self.assertEqual(
            song_document["number_of_comments"], self.song.number_of_comments
        )
        self.assertEqual(song_document["number_of_views"], self.song.number_of_views)

    def test_upsert_typesense_document(self):
        """
        Test that the upsert_typesense_document() method upserts a document to TypeSense.
        """
        schema_name = self.song.collection_class.schema_name
        song_document = self.get_document(schema_name, self.song.pk)

        self.assertEqual(song_document["title"], self.song.title)
        self.song.title = "New Title"
        self.song.save(update_fields=["title"])

        song_document = self.get_document(schema_name, self.song.pk)
        self.assertEqual(song_document["title"], "New Title")

    def test_delete_typesense_document(self):
        """
        Test that the delete_typesense_document() method deletes a document from TypeSense.
        """
        schema_name = self.song.collection_class.schema_name
        document_id = self.song.pk
        song_document = self.get_document(schema_name, document_id)

        self.assertEqual(song_document["title"], self.song.title)

        self.song.delete()
        song_document = self.get_document(schema_name, document_id)
        self.assertIsNone(song_document)
