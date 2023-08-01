"""Filters used for Typesense

"""

from dateutil import parser
from datetime import datetime

from django import template


register = template.Library()


@register.filter(name="date_timestamp_to_date")
def date_timestamp_to_date(value):
    """Display ISO Date strings as dates."""

    if value:
        dt_object = datetime.fromtimestamp(value)
        return dt_object
    return "-"
