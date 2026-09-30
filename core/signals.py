import logging

from django.conf import settings
from django.db.models.signals import post_save

from core.imaging.sources import IMAGE_FIELDS
from core.imaging.variants import field_local_path, process_stored_file

logger = logging.getLogger(__name__)

_FIELDS = {
    (app_label, model_name): field_names
    for app_label, model_name, field_names in IMAGE_FIELDS
}


def _on_save(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or not getattr(settings, 'IMAGE_VARIANTS_AUTO', True):
        return
    field_names = _FIELDS.get((sender._meta.app_label, sender.__name__))
    if not field_names:
        return
    for field_name in field_names:
        if update_fields is not None and field_name not in update_fields:
            continue
        path = field_local_path(getattr(instance, field_name, None))
        if path is None:
            continue
        try:
            process_stored_file(path)
        except Exception:
            logger.exception('Варіанти зображення не зібрано: %s.%s', sender.__name__, field_name)


def connect_image_signals():
    from django.apps import apps

    for app_label, model_name, _field_names in IMAGE_FIELDS:
        model = apps.get_model(app_label, model_name)
        post_save.connect(
            _on_save,
            sender=model,
            dispatch_uid=f'image-variants-{app_label}.{model_name}',
        )
