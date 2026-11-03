"""SEO категорій dityachi-knigi та bibliya.

H1 на сторінці категорії — category.name (шаблон category_detail).
<title> додає один суфікс «| OFION» через with_site_suffix, тому meta_title
його не містить. Описи спираються на факти з шаблонів: інтернет-магазин OFION,
доставка Новою Поштою, оплата LiqPay / Monobank / накладений платіж.
"""
from django.db import migrations

KIDS_SLUG = 'dityachi-knigi'
BIBLE_SLUG = 'bibliya'

KIDS_NAME = 'Дитячі книги'
KIDS_META_TITLE = 'Дитячі книги'
KIDS_META_DESCRIPTION = (
    'Дитячі книги: розділ каталогу інтернет-магазину OFION. '
    'Доставка здійснюється Новою Поштою по всій Україні. '
    'Оплата: LiqPay, Monobank, накладений платіж.'
)
BIBLE_META_DESCRIPTION = (
    'Біблія в каталозі інтернет-магазину OFION: видання Біблії. '
    'Доставка здійснюється Новою Поштою по всій Україні. '
    'Оплата: LiqPay, Monobank, накладений платіж.'
)

_KIDS_VALUES = {
    'name': KIDS_NAME,
    'name_uk': KIDS_NAME,
    'meta_title': KIDS_META_TITLE,
    'meta_title_uk': KIDS_META_TITLE,
    'meta_description': KIDS_META_DESCRIPTION,
    'meta_description_uk': KIDS_META_DESCRIPTION,
}
_BIBLE_VALUES = {
    'meta_description': BIBLE_META_DESCRIPTION,
    'meta_description_uk': BIBLE_META_DESCRIPTION,
}


def _update_by_slug(model, slug, values):
    names = {field.name for field in model._meta.concrete_fields}
    payload = {key: value for key, value in values.items() if key in names}
    if not payload:
        return 0
    qs = model.objects.filter(slug=slug)
    rewrite = getattr(qs, 'rewrite', None)
    if callable(rewrite):
        qs = rewrite(False)
    return qs.update(**payload)


def set_kids_and_bible_seo(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    _update_by_slug(Category, KIDS_SLUG, _KIDS_VALUES)
    _update_by_slug(Category, BIBLE_SLUG, _BIBLE_VALUES)


def noop_reverse(apps, schema_editor):
    """Попередні тексти в репозиторії не збережені — відкат нічого не змінює."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0024_merge_20261102_1752'),
    ]

    operations = [
        migrations.RunPython(set_kids_and_bible_seo, noop_reverse),
    ]
