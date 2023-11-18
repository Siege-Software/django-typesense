from django.db.models.signals import m2m_changed, post_save, pre_delete
from django.dispatch import receiver

from django_typesense.mixins import TypesenseModelMixin


@receiver(post_save)
def post_save_typesense_models(sender, instance, **kwargs):
    if not issubclass(sender, TypesenseModelMixin):
        return

    update_fields = kwargs['update_fields']
    sender.get_collection(instance, update_fields=update_fields).update()


@receiver(pre_delete)
def pre_delete_typesense_models(sender, instance, **kwargs):
    if not issubclass(sender, TypesenseModelMixin):
        return

    sender.get_collection(instance).delete()


@receiver(m2m_changed)
def m2m_changed_typesense_models(instance, model, action, reverse, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        if reverse and issubclass(model, TypesenseModelMixin):
            pk_set = list(kwargs.get("pk_set"))
            obj = model.objects.filter(pk__in=pk_set)
            model.get_collection(obj=obj, many=True).update()
        else:
            if isinstance(instance, TypesenseModelMixin):
                instance_class = instance.__class__
                instance_class.get_collection(instance).update()
