"""Safe data migration: trim spaces/NBSP around product names (all locales)."""

from django.db import migrations


def _normalize(value):
    if not value:
        return value
    text = str(value).replace('\xa0', ' ').replace('\u202f', ' ').replace('\u2007', ' ')
    text = ' '.join(text.split())
    return text.strip()


_NAME_FIELDS = ('name', 'name_uk', 'name_en', 'name_ru')


def trim_product_names(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for product in Product.objects.all().iterator():
        updates = {}
        for field in _NAME_FIELDS:
            if not hasattr(product, field):
                continue
            old = getattr(product, field)
            if not isinstance(old, str) or not old:
                continue
            new = _normalize(old)
            if new != old:
                updates[field] = new
        if updates:
            Product.objects.filter(pk=product.pk).update(**updates)


def noop_reverse(apps, schema_editor):
    """Trimming is irreversible without originals; keep reverse as no-op."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0019_alter_product_order_info_alter_product_order_info_en_and_more'),
    ]

    operations = [
        migrations.RunPython(trim_product_names, noop_reverse),
    ]
