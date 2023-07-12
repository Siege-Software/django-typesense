import typesense

from django.conf import settings

client = typesense.Client(settings.TYPESENSE)
