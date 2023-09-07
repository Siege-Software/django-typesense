import concurrent.futures
import logging
import os

from django.db.models import QuerySet
from django.core.paginator import Paginator

from typesense.exceptions import ObjectNotFound

from django_typesense.typesense_client import client

logger = logging.getLogger(__name__)


def update_batch(
    collection_name: str, documents_queryset: QuerySet, batch_no: int
) -> None:
    """
    Helper function that updates a batch of documents using the Typesense API.
    """
    documents = [document.get_typesense_dict() for document in documents_queryset]

    if not len(documents):
        logger.warning(
            f"Skipping updating the collection {collection_name} with an empty list"
        )
        return

    try:
        responses = client.collections[collection_name].documents.import_(
            documents, {"action": "upsert"}
        )
        created = False
    except ObjectNotFound:
        documents_queryset.model.create_typesense_collection()
        responses = client.collections[collection_name].documents.import_(
            documents, {"action": "upsert"}
        )
        created = True

    # responses is a list with a response for each document in documents
    failure_responses = [response for response in responses if not response["success"]]

    if failure_responses:
        raise Exception(
            f"An Error occurred during the bulk update: {failure_responses}"
        )

    if created:
        logger.debug(
            f"Batch {batch_no} Created and Updated with {len(documents)} records ✓"
        )
    else:
        logger.debug(f"Batch {batch_no} Updated with {len(documents)} records ✓")


def bulk_update_typesense_records(
    records_queryset: QuerySet, collection_name: str = None
) -> None:
    """
    This method updates Typesense records for both objs .update() calls from Typesense mixin subclasses.
    This function should be called on every model update statement for data consistency

    Parameters:
        records_queryset (QuerySet): the QuerySet should be from a Typesense mixin subclass
        collection_name (str): The collection name

    Returns:
        None
    """
    from django_typesense.mixins import TypesenseQuerySet

    if not isinstance(records_queryset, TypesenseQuerySet):
        logger.error(
            f"The objs for {records_queryset.model.__name__} does not use TypesenseQuerySet "
            f"as it's manager. Please update the model manager for the class to use Typesense."
        )
        return

    if not records_queryset.ordered:
        try:
            records_queryset = records_queryset.order_by("id")
        except Exception:
            raise Exception(
                "Pagination may yield inconsistent results with an unordered object_list. "
                "Please provide an ordered objs"
            )

    if not collection_name:
        collection_name = records_queryset.model.__name__.lower()

    batch_size = 500
    paginator = Paginator(records_queryset, batch_size)
    threads = os.cpu_count()

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for page_no in paginator.page_range:
            documents_queryset = paginator.page(page_no).object_list
            logger.debug(
                f"Updating batch {page_no} of {paginator.num_pages} batches of size {len(documents_queryset)}"
            )
            future = executor.submit(
                update_batch, collection_name, documents_queryset, page_no
            )
            futures.append(future)

        for future in concurrent.futures.as_completed(futures):
            future.result()


def bulk_delete_typesense_records(document_ids: list, collection_name: str) -> None:
    """
    This method deletes Typesense records for objs .delete() calls from Typesense mixin subclasses

    Parameters:
        document_ids (list): the list of document IDs to be deleted
        collection_name (str): The collection name for the documents, for delete the collection name is required

    Returns:
        None

    """
    try:
        client.collections[collection_name].documents.delete(
            {"filter_by": f"id:{document_ids}"}
        )
    except Exception as e:
        logger.error(f"Could not delete the documents IDs {document_ids}\nError: {e}")


def typesense_search(collection_name, **kwargs):
    if not collection_name:
        return

    search_parameters = {}

    for key, value in kwargs.items():
        search_parameters.update({key: value})

    return client.collections[collection_name].documents.search(search_parameters)
