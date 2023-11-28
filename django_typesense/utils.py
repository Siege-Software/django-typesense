import concurrent.futures
import logging
import os
from datetime import date, datetime, time

from django.core.exceptions import FieldError
from django.core.paginator import Paginator
from django.db.models import QuerySet
from typesense.exceptions import TypesenseClientError

from django_typesense.exceptions import BatchUpdateError, UnorderedQuerySetError

logger = logging.getLogger(__name__)


def update_batch(documents_queryset: QuerySet, collection_class, batch_no: int) -> None:
    """
    Helper function that updates a batch of documents using the Typesense API.
    """
    collection = collection_class(documents_queryset, many=True)
    responses = collection.update()
    failure_responses = [response for response in responses if not response["success"]]

    if failure_responses:
        raise BatchUpdateError(
            f"An Error occurred during the bulk update: {failure_responses}"
        )

    logger.debug(f"Batch {batch_no} Updated with {len(collection.data)} records ✓")


def bulk_update_typesense_records(
    records_queryset: QuerySet,
    batch_size: int = 1024,
    num_threads: int = os.cpu_count(),
) -> None:
    """
    This method updates Typesense records for both objs .update() calls from Typesense mixin subclasses.
    This function should be called on every model update statement for data consistency

    Parameters:
        records_queryset (QuerySet): the QuerySet should be from a Typesense mixin subclass
        batch_size: how many objects are indexed in a single run
        num_threads: the number of thread that will be used. defaults to `os.cpu_count()`

    Returns:
        None
    """

    from django_typesense.mixins import TypesenseQuerySet

    if not isinstance(records_queryset, TypesenseQuerySet):
        logger.error(
            f"The objects for {records_queryset.model.__name__} does not use TypesenseQuerySet "
            f"as it's manager. Please update the model manager for the class to use Typesense."
        )
        return

    if not records_queryset.ordered:
        try:
            records_queryset = records_queryset.order_by("pk")
        except (FieldError, TypeError):
            raise UnorderedQuerySetError(
                "Pagination may yield inconsistent results with an unordered object_list. "
                "Please provide an ordered objects."
            )

    collection_class = records_queryset.model.collection_class
    paginator = Paginator(records_queryset, batch_size)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for page_no in paginator.page_range:
            documents_queryset = paginator.page(page_no).object_list
            logger.debug(f"Updating batch {page_no} of {paginator.num_pages}")
            future = executor.submit(
                update_batch, documents_queryset, collection_class, page_no
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

    from django_typesense.typesense_client import client

    try:
        client.collections[collection_name].documents.delete(
            {"filter_by": f"id:{document_ids}"}
        )
    except TypesenseClientError as error:
        logger.error(
            f"Could not delete the documents IDs {document_ids}\nError: {error}"
        )


def typesense_search(collection_name, **kwargs):
    """
    Perform a search on the specified collection using the parameters provided.

    Args:
        collection_name: the schema name of the collection to perform the search on
        **kwargs: typesense search parameters

    Returns:
        A list of the typesense results
    """

    from django_typesense.typesense_client import client

    required_fields = ["q", "query_by"]
    if not collection_name or not all(field in kwargs for field in required_fields):
        return

    return client.collections[collection_name].documents.search(kwargs)


def get_unix_timestamp(datetime_object):
    """
    Get the unix timestamp from a datetime object with the time part set to midnight

    Args:
        datetime_object: a python date/datetime/time object

    Returns:
        An integer representing the timestamp
    """

    # isinstance can take a union type but for backwards compatibility we call it multiple times
    if isinstance(datetime_object, datetime):
        timestamp = int(datetime_object.timestamp())

    elif isinstance(datetime_object, date):
        timestamp = int(
            datetime.combine(datetime_object, datetime.min.time()).timestamp()
        )

    elif isinstance(datetime_object, time):
        timestamp = int(datetime.combine(datetime.today(), datetime_object).timestamp())

    else:
        raise Exception(
            f"Expected a date/datetime/time objects but got {datetime_object} of type {type(datetime_object)}"
        )

    return timestamp
