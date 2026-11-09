"""Увімкнути show_in_top_menu для групи «Топ товарів» (якщо однозначно знайдена)."""

from django.db import migrations
from django.db.models import Q

TOP_TOVARIV_SLUGS = ('top-tovariv', 'top-tovari', 'top')
TOP_TOVARIV_NAME = 'Топ товарів'
_NAME_FIELD_CANDIDATES = ('name', 'name_uk', 'name_en', 'name_ru')


def _name_fields(model):
    existing = {field.name for field in model._meta.fields}
    return [name for name in _NAME_FIELD_CANDIDATES if name in existing]


def enable_top_tovariv_top_menu(apps, schema_editor):
    ProductGroup = apps.get_model('products', 'ProductGroup')
    by_slug = ProductGroup.objects.filter(slug__in=TOP_TOVARIV_SLUGS)
    count = by_slug.count()
    if count == 1:
        by_slug.update(show_in_top_menu=True)
        return
    if count > 1:
        return

    name_q = Q()
    for field_name in _name_fields(ProductGroup):
        name_q |= Q(**{f'{field_name}__iexact': TOP_TOVARIV_NAME})
    if not name_q:
        return

    by_name = ProductGroup.objects.filter(name_q)
    if by_name.count() == 1:
        by_name.update(show_in_top_menu=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0028_productgroup_show_in_top_menu'),
    ]

    operations = [
        migrations.RunPython(enable_top_tovariv_top_menu, noop_reverse),
    ]
