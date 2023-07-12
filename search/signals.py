from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from search.models import TypeSenseMixin


@receiver(post_save)
def post_save_typesense_models(sender, instance, **kwargs):
    if not issubclass(sender, TypeSenseMixin):
        return

    instance.upsert_typesense_document()


@receiver(pre_delete)
def pre_delete_typesense_models(sender, instance, **kwargs):
    if not issubclass(sender, TypeSenseMixin):
        return

    instance.delete_typesense_document()
