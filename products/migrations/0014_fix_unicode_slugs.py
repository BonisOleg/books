"""Виправлення slug-полів Category/Product, які містять non-ASCII символи.

URL-конфіг приймає лише [-a-zA-Z0-9_]+; кириличні slug ламають reverse()
і викликають 500 на головній / меню (NoReverseMatch).
"""
import re

from django.db import migrations
from django.utils.text import slugify

ASCII_SLUG_RE = re.compile(r'^[-a-zA-Z0-9_]+$')

_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e',
    'є': 'ie', 'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i',
    'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'iu', 'я': 'ia',
    'ё': 'yo', 'ы': 'y', 'э': 'e', 'ъ': '',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'H', 'Ґ': 'G', 'Д': 'D', 'Е': 'E',
    'Є': 'Ye', 'Ж': 'Zh', 'З': 'Z', 'И': 'Y', 'І': 'I', 'Ї': 'I', 'Й': 'I',
    'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R',
    'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch',
    'Ш': 'Sh', 'Щ': 'Shch', 'Ь': '', 'Ю': 'Yu', 'Я': 'Ya',
    'Ё': 'Yo', 'Ы': 'Y', 'Э': 'E', 'Ъ': '',
    "'": '', '\u2019': '', '\u02bc': '',
}


def _transliterate(text):
    return ''.join(_TRANSLIT.get(c, c) for c in str(text))


def _ascii_slug(text, fallback, max_length):
    for candidate in (text, _transliterate(text)):
        if not candidate:
            continue
        s = slugify(candidate, allow_unicode=False)
        if s:
            return s[:max_length]
    s = slugify(_transliterate(fallback), allow_unicode=False)
    return (s or 'item')[:max_length]


def _is_ascii_slug(value):
    return bool(value) and bool(ASCII_SLUG_RE.match(value))


def _unique_slug(model, base, exclude_pk, max_length):
    slug = base
    counter = 1
    while model.objects.filter(slug=slug).exclude(pk=exclude_pk).exists():
        suffix = f'-{counter}'
        slug = f'{base[:max_length - len(suffix)]}{suffix}'
        counter += 1
    return slug


def fix_unicode_slugs(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    Product = apps.get_model('products', 'Product')

    for cat in Category.objects.all():
        if _is_ascii_slug(cat.slug):
            continue
        base = _ascii_slug(cat.name, fallback=f'cat-{cat.pk}', max_length=200)
        cat.slug = _unique_slug(Category, base, cat.pk, max_length=200)
        cat.save(update_fields=['slug'])

    for p in Product.objects.all():
        if _is_ascii_slug(p.slug):
            continue
        base = _ascii_slug(p.name, fallback=p.sku or f'p-{p.pk}', max_length=400)
        p.slug = _unique_slug(Product, base, p.pk, max_length=400)
        p.save(update_fields=['slug'])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0013_add_filter_group_option'),
    ]

    operations = [
        migrations.RunPython(fix_unicode_slugs, reverse_noop),
    ]
