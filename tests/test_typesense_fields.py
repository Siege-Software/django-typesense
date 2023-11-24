import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase

from django_typesense import fields
from tests.collections import SongCollection
from tests.models import Artist, Genre, Song


class TestTypesenseCharField(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name="genre1")
        self.song = Song.objects.create(
            title="New Song",
            genre=self.genre,
            release_date=date.today(),
            description="New song description",
            duration=timedelta(minutes=3, seconds=35),
        )
        self.attrs = [
            attr if attr != "_field_type" else "type"
            for attr in fields.TYPESENSE_SCHEMA_ATTRS
        ]

    def test_string_representation(self):
        self.assertEqual(str(SongCollection.title), "title")

    def test_attrs(self):
        title_attrs = SongCollection.title.attrs
        self.assertCountEqual(title_attrs.keys(), self.attrs)
        self.assertEqual(title_attrs["name"], "title")
        self.assertEqual(title_attrs["type"], "string")
        self.assertEqual(title_attrs["locale"], "")
        self.assertFalse(title_attrs["sort"])
        self.assertFalse(title_attrs["optional"])
        self.assertFalse(title_attrs["facet"])
        self.assertFalse(title_attrs["infix"])
        self.assertTrue(title_attrs["index"])

    def test_field_type(self):
        self.assertEqual(SongCollection.title.field_type, "string")

    def test_value_method(self):
        title = SongCollection.title
        self.assertEqual(title.value(obj=self.song), self.song.title)

        optional_field = fields.TypesenseCharField(value="name", optional=True)
        self.assertEqual(optional_field.value(obj=self.song), "")

        with self.assertRaises(AttributeError):
            invalid_field = fields.TypesenseCharField(value="invalid_field")
            invalid_field.value(obj=self.song)

    def test_to_python_method(self):
        title = SongCollection.title.value(obj=self.song)
        self.assertEqual(SongCollection.title.to_python(value=title), self.song.title)


class TestTypesenseIntegerMixin(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name="genre1")
        self.song = Song.objects.create(
            title="New Song",
            genre=self.genre,
            release_date=date.today(),
            description="New song description",
            duration=timedelta(minutes=3, seconds=35),
        )

    def test_value_method(self):
        genre_id = SongCollection.genre_id
        self.assertEqual(genre_id.value(obj=self.song), self.genre.pk)

        views = fields.TypesenseSmallIntegerField(value="views", optional=True)
        self.assertIsNone(views.value(obj=self.song))

        self.song.views = "Wrong type"
        with self.assertRaises(ValueError):
            views.value(obj=self.song)


class TestTypesenseDecimalField(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name="genre1")
        self.song = Song.objects.create(
            title="New Song",
            genre=self.genre,
            release_date=date.today(),
            description="New song description",
            duration=timedelta(minutes=3, seconds=35),
        )

    def test_value_method(self):
        price = fields.TypesenseDecimalField(value="price", optional=True)
        self.assertEqual(price.value(obj=self.song), "None")

        self.song.price = Decimal("23.00")
        self.assertEqual(price.value(obj=self.song), "23.00")

    def test_to_python_method(self):
        price = fields.TypesenseDecimalField(value="price", optional=True)
        self.song.price = Decimal("23.00")
        price_value = price.value(obj=self.song)
        self.assertEqual(price.to_python(value=price_value), Decimal("23.00"))


class TestTypesenseDateTimeFieldBase(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name="genre1")
        self.song = Song.objects.create(
            title="New Song",
            genre=self.genre,
            release_date=date.today(),
            description="New song description",
            duration=timedelta(minutes=3, seconds=35),
        )

    def test_value_method(self):
        optional_date = fields.TypesenseDateField(value="optional_field", optional=True)
        self.assertIsNone(optional_date.value(obj=self.song))

        release_date_timestamp = fields.TypesenseDateField(
            value="release_date_timestamp"
        )
        release_date_timestamp_value = release_date_timestamp.value(obj=self.song)
        self.assertTrue(isinstance(release_date_timestamp_value, int))
        self.assertEqual(release_date_timestamp_value, self.song.release_date_timestamp)

    def test_date_field(self):
        release_date = SongCollection.release_date
        release_date_value = release_date.value(obj=self.song)
        self.assertTrue(isinstance(release_date_value, int))
        self.assertEqual(release_date_value, self.song.release_date_timestamp)

        release_date_to_python = release_date.to_python(value=release_date_value)
        self.assertTrue(isinstance(release_date_to_python, date))
        self.assertEqual(release_date_to_python, self.song.release_date)

    def test_time_field(self):
        release_time = fields.TypesenseTimeField(value="release_time")
        self.song.release_time = time(hour=13, minute=30, second=0)
        release_time_value = release_time.value(obj=self.song)

        self.assertTrue(isinstance(release_time.to_python(release_time_value), time))
        self.assertEqual(
            release_time.to_python(release_time_value), self.song.release_time
        )

    def test_datetime_field(self):
        created_at = fields.TypesenseDateTimeField(value="created_at")
        self.song.created_at = datetime(
            year=2023, month=9, day=11, hour=16, minute=20, second=0
        )
        created_at_value = created_at.value(obj=self.song)

        self.assertTrue(isinstance(created_at.to_python(created_at_value), datetime))
        self.assertEqual(
            created_at.to_python(value=created_at_value), self.song.created_at
        )


class TestTypesenseJSONField(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name="genre1")
        self.song = Song.objects.create(
            title="New Song",
            genre=self.genre,
            release_date=date.today(),
            description="New song description",
            duration=timedelta(minutes=3, seconds=35),
        )

    def test_value_method(self):
        extra_info = fields.TypesenseJSONField(value="extra_info")
        self.song.extra_info = {"producer": "DJ Something"}
        extra_info_value = extra_info.value(obj=self.song)

        self.assertTrue(isinstance(extra_info_value, str))
        self.assertEqual(extra_info_value, json.dumps(self.song.extra_info))

    def test_to_python_method(self):
        extra_info = fields.TypesenseJSONField(value="extra_info")
        self.song.extra_info = {"producer": "DJ Something"}
        extra_info_value = extra_info.value(obj=self.song)

        self.assertEqual(
            extra_info.to_python(value=extra_info_value), self.song.extra_info
        )


class TestTypesenseArrayField(TestCase):
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
        self.song.artists.add(self.artist)

    def test_to_python_method(self):
        artist_names = SongCollection.artist_names
        artist_names_value = artist_names.value(obj=self.song)

        self.assertCountEqual(
            artist_names.to_python(artist_names_value), self.song.artist_names()
        )
