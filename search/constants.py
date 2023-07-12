from django.conf import settings


TYPESENSE_PAGE_SIZE = (
    settings.TYPESENSE_PAGE_SIZE if hasattr(settings, "TYPESENSE_PAGE_SIZE") else 25
)
BOOLEAN_TRUES = ["y", "Y", "yes", "1", 1, True, "True", "true"]
