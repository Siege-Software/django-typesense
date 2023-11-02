from typesense import exceptions

from django_typesense.typesense_client import client


def get_document(schema_name, document_id):
    try:
        return client.collections[schema_name].documents[document_id].retrieve()
    except exceptions.ObjectNotFound:
        return None
