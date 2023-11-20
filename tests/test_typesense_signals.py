from datetime import date, timedelta

from django.test import TestCase

from tests.models import Artist, Genre, Library, Song
from tests.utils import get_document


class TestTypeSenseSignals(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name="genre1")
        self.artist = Artist.objects.create(name="artist1")
        self.song = Song.objects.create(
            title="New Song",
            genre=self.genre,
            release_date=date.today(),
            description="New song description",
            duration=timedelta(minutes=3, seconds=35),
        )

    def test_post_save_typesense_models(self):
        schema_name = self.song.collection_class.schema_name
        song_document = get_document(schema_name, self.song.pk)

        self.assertIsNotNone(song_document)
        self.assertEqual(song_document["title"], self.song.title)
        self.assertEqual(song_document["genre_id"], self.song.genre.pk)
        self.assertEqual(song_document["genre_name"], self.song.genre.name)
        self.assertEqual(
            song_document["release_date"], self.song.release_date_timestamp
        )
        self.assertEqual(song_document["number_of_views"], self.song.number_of_views)
        self.assertEqual(
            song_document["number_of_comments"], self.song.number_of_comments
        )

    def test_pre_delete_typesense_models(self):
        schema_name = self.song.collection_class.schema_name
        song_pk = self.song.pk

        song_document = get_document(schema_name, song_pk)
        self.assertIsNotNone(song_document)

        self.genre.delete()
        self.assertFalse(Song.objects.filter(pk=song_pk).exists())
        song_document = get_document(schema_name, song_pk)
        self.assertIsNone(song_document)

    def test_m2m_changed_typesense_models(self):
        schema_name = self.song.collection_class.schema_name

        song_document = get_document(schema_name, self.song.pk)
        self.assertIsNotNone(song_document)
        self.assertCountEqual(song_document["artist_names"], self.song.artist_names())

        self.song.artists.add(self.artist)
        song_document = get_document(schema_name, self.song.pk)
        self.assertIsNotNone(song_document)
        self.assertCountEqual(song_document["artist_names"], self.song.artist_names())

        artist_2 = Artist.objects.create(name="artist2")
        artist_2.song_set.add(self.song)
        song_document = get_document(schema_name, self.song.pk)
        self.assertIsNotNone(song_document)
        self.assertCountEqual(song_document["artist_names"], self.song.artist_names())

        library = Library.objects.create(name="new album")
        library.songs.add(self.song)

        song_document = get_document(schema_name, self.song.pk)
        self.assertIsNotNone(song_document)
        self.assertCountEqual(song_document["library_ids"], self.song.library_ids)

        self.song.libraries.remove(library)
        song_document = get_document(schema_name, self.song.pk)
        self.assertIsNotNone(song_document)
        self.assertCountEqual(song_document["library_ids"], self.song.library_ids)
