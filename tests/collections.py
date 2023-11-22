from django_typesense import fields
from django_typesense.collections import TypesenseCollection


class SongCollection(TypesenseCollection):
    query_by_fields = "title,artist_names,genre_name"

    title = fields.TypesenseCharField()
    genre_name = fields.TypesenseCharField(value="genre.name")
    genre_id = fields.TypesenseSmallIntegerField()
    release_date = fields.TypesenseDateField(optional=True)
    artist_names = fields.TypesenseArrayField(
        base_field=fields.TypesenseCharField(), value="artist_names"
    )
    number_of_comments = fields.TypesenseSmallIntegerField(index=False, optional=True)
    number_of_views = fields.TypesenseSmallIntegerField(index=False, optional=True)
    library_ids = fields.TypesenseArrayField(
        base_field=fields.TypesenseSmallIntegerField(), value="library_ids"
    )
