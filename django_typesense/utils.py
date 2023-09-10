import concurrent.futures
import logging
import os

from django.db.models import QuerySet
from django.core.paginator import Paginator

from django_typesense.collections import TypesenseCollection
from django_typesense.typesense_client import client

logger = logging.getLogger(__name__)


def update_batch(documents_queryset: QuerySet, collection_class: TypesenseCollection, batch_no: int) -> None:
    """
    Helper function that updates a batch of documents using the Typesense API.
    """
    collection = collection_class(documents_queryset, many=True)
    responses = collection.update()
    failure_responses = [response for response in responses if not response["success"]]

    if failure_responses:
        raise Exception(
            f"An Error occurred during the bulk update: {failure_responses}"
        )

    logger.debug(f"Batch {batch_no} Updated with {len(collection.data)} records ✓")


def bulk_update_typesense_records(records_queryset: QuerySet, batch_size: int = 1024) -> None:
    """
    This method updates Typesense records for both objs .update() calls from Typesense mixin subclasses.
    This function should be called on every model update statement for data consistency

    Parameters:
        records_queryset (QuerySet): the QuerySet should be from a Typesense mixin subclass
        batch_size: how many objects are indexed in a single run

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

    collection_class = records_queryset.model.collection_class
    paginator = Paginator(records_queryset, batch_size)
    threads = os.cpu_count()

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for page_no in paginator.page_range:
            documents_queryset = paginator.page(page_no).object_list
            logger.debug(f"Updating batch {page_no} of {paginator.num_pages}")
            future = executor.submit(update_batch, documents_queryset, collection_class, page_no)
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
    """
    Perform a search on the specified collection using the parameters provided.

    Args:
        collection_name: the schema name of the collection to perform the search on
        **kwargs: typesense search parameters

    Returns:
        A list of the typesense results
    """

    if not collection_name:
        return

    search_parameters = {}

    for key, value in kwargs.items():
        search_parameters.update({key: value})

    return client.collections[collection_name].documents.search(search_parameters)
