from django.db.models.signals import m2m_changed, post_save, pre_delete
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


@receiver(m2m_changed)
def m2m_changed_typesense_models(instance, model, action, reverse, **kwargs):
    if not isinstance(instance, TypesenseModelMixin) and not issubclass(
        model, TypesenseModelMixin
    ):
        return  # pragma: no cover

    if action in ["post_add", "post_remove", "post_clear"]:
        if reverse:
            pk_set = list(kwargs.get("pk_set"))
            obj = model.objects.filter(pk__in=pk_set)
            model.get_collection(obj=obj, many=True).update()
        else:
            instance_class = instance.__class__
            instance_class.get_collection(instance).update()
