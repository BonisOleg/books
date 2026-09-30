import logging

from django.db.models.signals import post_save

from products.search import refresh_search_index, source_fields

logger = logging.getLogger(__name__)


def on_product_save(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw:
        return
    if update_fields is not None and source_fields().isdisjoint(update_fields):
        return
    try:
        refresh_search_index(instance)
    except Exception:
        logger.exception('Індекс пошуку не оновлено для товару %s', instance.pk)


def connect_product_search():
    from products.models import Product
    post_save.connect(
        on_product_save,
        sender=Product,
        dispatch_uid='products-search-index',
    )
