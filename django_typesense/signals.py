from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from django_typesense.mixins import TypesenseModelMixin


@receiver(post_save)
def post_save_typesense_models(sender, instance, **kwargs):
    if not issubclass(sender, TypesenseModelMixin):
        return

    sender.get_collection(instance).update()


@receiver(pre_delete)
def pre_delete_typesense_models(sender, instance, **kwargs):
    if not issubclass(sender, TypesenseModelMixin):
        return

    sender.get_collection(instance).delete()