import concurrent.futures
import json
import logging
import os
from datetime import date, datetime, time
from typing import List

from django.core.exceptions import FieldError
from django.core.paginator import Paginator
from django.db.models import QuerySet
from typesense.exceptions import TypesenseClientError

from django_typesense.exceptions import BatchUpdateError, UnorderedQuerySetError

logger = logging.getLogger(__name__)


def update_batch(documents_queryset: QuerySet, collection_class, batch_no: int) -> None:
    """Updates a batch of documents using the Typesense API.

    Parameters
    ----------
    documents_queryset : QuerySet
        The Django objects QuerySet to update. It must be a `TypesenseModelMixin` subclass.
    collection_class : TypesenseCollection
        The Django Typesense collection to update.
    batch_no : int
        The batch identifier number.

    Returns
    -------
    None

    Raises
    ------
    BatchUpdateError
        Raised when an error occurs during updating typesense collection.
    """
    collection = collection_class(documents_queryset, many=True)
    responses = collection.update()
    if responses is None:
        return

    if isinstance(responses, list):
        failure_responses = [
            response for response in responses if not response["success"]
        ]

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
    """This method updates Typesense records for both objects .update() calls from
    Typesense mixin subclasses.
    This function should be called on every model update statement for data consistency.

    Parameters
    ----------
    records_queryset : QuerySet
        The Django objects QuerySet to update. It must be a `TypesenseModelMixin` subclass.
    batch_size : int
        The number of objects to be indexed in a single run. Defaults to 1024.
    num_threads : int
        The number of threads that will be used. Defaults to `os.cpu_count()`

    Returns
    -------
    None

    Raises
    ------
    UnorderedQuerySetError
        Raised when unordered queryset is ordered by `primary_key` and
        throws a `FieldError` or `TypeError`.
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
    """This method deletes Typesense records for objects .delete() calls
    from Typesense mixin subclasses.

    Parameters
    ----------
    document_ids : list
        The list of document IDs to be deleted.
    collection_name : str
        The collection name to delete the documents from.

    Returns
    -------
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

    if not collection_name:
        return

    search_parameters = {}

    for key, value in kwargs.items():
        search_parameters.update({key: value})

    return client.collections[collection_name].documents.search(search_parameters)


def get_unix_timestamp(datetime_object) -> int:
    """Get the unix timestamp from a datetime object with the time part set to midnight

    Parameters
    ----------
    datetime_object: date, datetime, time

    Returns
    -------
    timestamp : int
        Returns the datetime object timestamp.

    Raises
    ------
    TypeError
        Raised when a non datetime parameter is passed.
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
        raise TypeError(
            f"Expected a date/datetime/time objects but got {datetime_object} of type {type(datetime_object)}"
        )

    return timestamp


def export_documents(
    collection_name,
    filter_by: str = None,
    include_fields: List[str] = None,
    exclude_fields: List[str] = None,
) -> List[dict]:
    from django_typesense.typesense_client import client

    params = {}
    if filter_by is not None:
        params["filter_by"] = filter_by

    if include_fields is not None:
        params["include_fields"] = include_fields

    if exclude_fields is not None:
        params["exclude_fields"] = exclude_fields

    if not params:
        params = None

    jsonlist = (
        client.collections[collection_name].documents.export(params=params).splitlines()
    )
    return list(map(json.loads, jsonlist))
