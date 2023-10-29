import sys

from django.core.management import BaseCommand
from django.apps import apps


class Command(BaseCommand):
    help = "Create and/or Update Typesense Collections"

    def add_arguments(self, parser):
        parser.add_argument(
            "args",
            metavar="collection_name",
            nargs="*",
            help="Specify the collection schema name(s) to create or update.",
        )

    def handle(self, *collection_names, **options):
        collections = {}
        for model_data in apps.all_models.values():
            for model in model_data.values():
                if hasattr(model, 'collection_class'):
                    collections[model.collection_class.schema_name] = model.collection_class

        collections_for_action = []
        # Make sure the collection name(s) they asked for exists
        if collection_names := set(collection_names):
            has_bad_names = False

            for collection_name in collection_names:
                try:
                    collection = collections[collection_name]
                except KeyError:
                    self.stderr.write(f"No collection exists with schema name '{collection_name}'")
                    has_bad_names = True
                else:
                    collections_for_action.append(collection)

            if has_bad_names:
                sys.exit(2)
        else:
            collections_for_action = collections.values()
        
        for collection in collections_for_action:
            collection().update_typesense_collection()
