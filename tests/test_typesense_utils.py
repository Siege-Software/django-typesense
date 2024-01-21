from datetime import date, datetime, time
from unittest import mock

from django.db.utils import OperationalError
from django.test import TestCase
from typesense.exceptions import TypesenseClientError

from django_typesense.exceptions import BatchUpdateError, UnorderedQuerySetError
from django_typesense.utils import (
    bulk_delete_typesense_records,
    bulk_update_typesense_records,
    get_unix_timestamp,
    typesense_search,
    update_batch,
)

from tests.collections import SongCollection
from tests.factories import ArtistFactory, SongFactory
from tests.models import Artist, Song
from tests.utils import get_document


class TestUpdateBatch(TestCase):
    def setUp(self):
        self.song_count = 10
        SongFactory.create_batch(size=self.song_count)

    def test_update_batch(self):
        songa = Song.objects.all()
        self.assertEqual(songa.count(), self.song_count)

        with self.assertLogs(level="DEBUG") as logs:
            batch_number = 1
            update_batch(songa, SongCollection, batch_number)
            self.assertEqual(
                logs.output[-1],
                f"DEBUG:django_typesense.utils:Batch {batch_number} Updated with {self.song_count} records ✓",
            )

    @mock.patch(
        "tests.collections.SongCollection.update", return_value=[{"success": False}]
    )
    def test_update_batch_with_error(self, _):
        songs = Song.objects.all()
        self.assertEqual(songs.count(), self.song_count)

        with self.assertRaises(BatchUpdateError):
            update_batch(songs, SongCollection, 1)


class TestBulkUpdateTypesenseRecords(TestCase):
    def setUp(self):
        self.unordered_queryset_message = (
            "Pagination may yield inconsistent results with an unordered object_list. "
            "Please provide an ordered objects"
        )
        self.song_count = 10
        SongFactory.create_batch(size=self.song_count)

    def test_bulk_update_typesense_records(self):
        songs = Song.objects.all().order_by("pk")

        # This exception is thrown because the tests are running
        # against SQLite which doesn't support a high level of concurrency.
        # https://docs.djangoproject.com/en/4.2/ref/databases/#database-is-locked-errors
        with self.assertRaises(OperationalError):
            bulk_update_typesense_records(songs, batch_size=200, num_threads=2)

    def test_bulk_update_typesense_records_invalid_type(self):
        ArtistFactory.create_batch(size=20)
        artists = Artist.objects.all().order_by("pk")

        with self.assertLogs(level="ERROR") as logs:
            bulk_update_typesense_records(artists, batch_size=200, num_threads=2)
            expected_log = (
                f"The objects for {artists.model.__name__} does not use TypesenseQuerySet "
                "as it's manager. Please update the model manager for the class to use Typesense."
            )
            last_log_message = logs[-1][0].replace("ERROR:django_typesense.utils:", "")
            self.assertEqual(last_log_message, expected_log)

    @mock.patch("django.db.models.QuerySet.order_by", side_effect=TypeError)
    def test_bulk_update_typesense_records_unordered_queryset(self, _):
        songs = Song.objects.all()

        with self.assertRaises(UnorderedQuerySetError):
            bulk_update_typesense_records(songs, batch_size=200, num_threads=2)


class TestBulkDeleteTypesenseRecords(TestCase):
    def setUp(self):
        self.schema_name = Song.collection_class.schema_name
        SongFactory.create_batch(size=20)

    def test_bulk_delete_typesense_records(self):
        songs = Song.objects.all().order_by("pk")
        first_ten_songs = songs[:10]

        song_ids = []
        for song in first_ten_songs:
            song_document = get_document(self.schema_name, song.pk)
            self.assertIsNotNone(song_document)
            self.assertEqual(song_document["title"], song.title)
            song_ids.append(song.pk)

        bulk_delete_typesense_records(song_ids, self.schema_name)

        for song in songs:
            song_document = get_document(self.schema_name, song.pk)
            if song.pk in song_ids:
                self.assertIsNone(song_document)
            else:
                self.assertIsNotNone(song_document)
                self.assertEqual(song_document["title"], song.title)

    @mock.patch(
        "typesense.documents.Documents.delete", side_effect=TypesenseClientError
    )
    def test_bulk_delete_typesense_records_exception_raised(self, _):
        songs = Song.objects.all().order_by("pk")
        first_ten_songs = songs[:10]

        song_ids = []
        for song in first_ten_songs:
            song_document = get_document(self.schema_name, song.pk)
            self.assertIsNotNone(song_document)
            self.assertEqual(song_document["title"], song.title)
            song_ids.append(song.pk)

        with self.assertLogs(level="ERROR") as logs:
            bulk_delete_typesense_records(song_ids, self.schema_name)
            last_log = logs[-1][0].replace("ERROR:django_typesense.utils:", "")
            expected_log_message = (
                f"Could not delete the documents IDs {song_ids}\nError: "
            )
            self.assertEqual(last_log, expected_log_message)

        for song in songs:
            song_document = get_document(self.schema_name, song.pk)
            self.assertIsNotNone(song_document)
            self.assertEqual(song_document["title"], song.title)


class TestTypesenseSearch(TestCase):
    def setUp(self):
        self.collection_name = Song.collection_class.schema_name
        self.query_fields = Song.collection_class.query_by_fields
        SongFactory.create_batch(size=20)

    def test_typesense_search(self):
        data = {"q": "song", "query_by": self.query_fields}
        results = typesense_search(self.collection_name, **data)
        self.assertIsNotNone(results)
        self.assertEqual(results["found"], 20)

    # def test_typesense_search_invalid_parameters(self):
    #     data = {"q": "song", "query_by": self.query_fields}
    #     results = typesense_search("", **data)
    #     self.assertIsNone(results)
    #
    #     data = {"q": "song"}
    #     results = typesense_search(self.collection_name, **data)
    #     self.assertIsNone(results)
    #
    #     data = {"q": "song", "query_by": self.query_fields}
    #     results = typesense_search("invalid_collection", **data)
    #     self.assertIsNone(results)


class TestGetUnixTimestamp(TestCase):
    def test_get_unix_timestamp_datetime(self):
        now = datetime(year=2023, month=11, day=23, hour=16, minute=20, second=00)
        now_timestamp = get_unix_timestamp(now)
        self.assertTrue(isinstance(now_timestamp, int))
        self.assertEqual(now_timestamp, now.timestamp())

    def test_get_unix_timestamp_date(self):
        today = date(year=2023, month=11, day=23)
        today_timestamp = get_unix_timestamp(today)
        self.assertTrue(isinstance(today_timestamp, int))
        self.assertEqual(
            today_timestamp, datetime.combine(today, datetime.min.time()).timestamp()
        )

    def test_get_unix_timestamp_time(self):
        now = time(hour=16, minute=20, second=00)
        now_timestamp = get_unix_timestamp(now)
        self.assertTrue(isinstance(now_timestamp, int))
        self.assertEqual(
            now_timestamp, datetime.combine(datetime.today(), now).timestamp()
        )

    def test_get_unix_timestamp_invalid_type(self):
        invalid_datetime = "2023-11-23 16:20:00"
        with self.assertRaises(TypeError):
            get_unix_timestamp(invalid_datetime)
