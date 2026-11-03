"""SEO-копія категорій dityachi-knigi та bibliya після data-міграції."""
from __future__ import annotations

import importlib
import re

from django.apps import apps
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Category

_migration = importlib.import_module(
    'products.migrations.0025_category_kids_and_bible_seo',
)
BIBLE_META_DESCRIPTION = _migration.BIBLE_META_DESCRIPTION
KIDS_META_DESCRIPTION = _migration.KIDS_META_DESCRIPTION
KIDS_META_TITLE = _migration.KIDS_META_TITLE
KIDS_NAME = _migration.KIDS_NAME
noop_reverse = _migration.noop_reverse
set_kids_and_bible_seo = _migration.set_kids_and_bible_seo

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'category-seo-copy',
    }
}

SITE_DEFAULT_DESCRIPTION = (
    'OFION - інтернет-магазин елітних подарунків, книг у шкірі, '
    'статуеток та ексклюзивних товарів'
)


def _title_of(html: str) -> str:
    match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
    return re.sub(r'\s+', ' ', match.group(1)).strip() if match else ''


def _h1_texts(html: str) -> list[str]:
    found = re.findall(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    return [re.sub(r'\s+', ' ', item).strip() for item in found]


def _meta_desc(html: str) -> str:
    match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html,
        re.I | re.S,
    )
    return match.group(1) if match else ''


@override_settings(CACHES=LOC_MEM, SITE_DOMAIN='example.test', SITE_PROTOCOL='https')
class CategorySeoCopyTests(TestCase):
    def test_kids_title_h1_and_distinct_descriptions(self):
        from core.models import SiteSettings

        SiteSettings.objects.create(site_name='OFION')
        Category.objects.create(
            name='Біблія',
            name_en='Children',
            slug='dityachi-knigi',
            meta_title='Біблія | OFION',
            meta_description='Спільний старий опис категорії біблії.',
            is_active=True,
        )
        Category.objects.create(
            name='Біблія',
            name_en='Bible',
            slug='bibliya',
            meta_title='Біблія | OFION',
            meta_description='Спільний старий опис категорії біблії.',
            is_active=True,
        )

        set_kids_and_bible_seo(apps, None)

        kids = self.client.get(reverse('products:category', kwargs={'slug': 'dityachi-knigi'}))
        bible = self.client.get(reverse('products:category', kwargs={'slug': 'bibliya'}))
        self.assertEqual(kids.status_code, 200)
        self.assertEqual(bible.status_code, 200)

        kids_html = kids.content.decode()
        bible_html = bible.content.decode()
        title = _title_of(kids_html)
        self.assertEqual(title.count('| OFION'), 1)
        self.assertEqual(title, f'{KIDS_META_TITLE} | OFION')
        self.assertEqual(_h1_texts(kids_html), [KIDS_NAME])
        self.assertEqual(_h1_texts(bible_html), ['Біблія'])

        kids_desc = _meta_desc(kids_html)
        bible_desc = _meta_desc(bible_html)
        self.assertEqual(kids_desc, KIDS_META_DESCRIPTION)
        self.assertEqual(bible_desc, BIBLE_META_DESCRIPTION)
        self.assertNotEqual(kids_desc, bible_desc)
        self.assertNotEqual(kids_desc, SITE_DEFAULT_DESCRIPTION)
        self.assertNotEqual(bible_desc, SITE_DEFAULT_DESCRIPTION)
        self.assertGreaterEqual(len(kids_desc), 150)
        self.assertLessEqual(len(kids_desc), 160)
        self.assertGreaterEqual(len(bible_desc), 150)
        self.assertLessEqual(len(bible_desc), 160)

        stored = (
            Category.objects.rewrite(False)
            .values(
                'name', 'name_uk', 'name_en',
                'meta_title', 'meta_title_uk',
                'meta_description', 'meta_description_uk',
            )
            .get(slug='dityachi-knigi')
        )
        self.assertEqual(stored['name'], KIDS_NAME)
        self.assertEqual(stored['name_uk'], KIDS_NAME)
        self.assertEqual(stored['name_en'], 'Children')
        self.assertNotIn('| OFION', stored['meta_title'])
        self.assertEqual(stored['meta_title'], KIDS_META_TITLE)
        self.assertEqual(stored['meta_title_uk'], KIDS_META_TITLE)
        self.assertEqual(stored['meta_description'], KIDS_META_DESCRIPTION)
        self.assertEqual(stored['meta_description_uk'], KIDS_META_DESCRIPTION)

    def test_missing_rows_and_reverse_noop(self):
        set_kids_and_bible_seo(apps, None)
        self.assertFalse(Category.objects.filter(slug='dityachi-knigi').exists())

        Category.objects.create(
            name='Дитячі книги',
            slug='dityachi-knigi',
            meta_title=KIDS_META_TITLE,
            meta_description=KIDS_META_DESCRIPTION,
            is_active=True,
        )
        before = list(
            Category.objects.rewrite(False).values(
                'name', 'meta_title', 'meta_description',
            )
        )
        noop_reverse(apps, None)
        after = list(
            Category.objects.rewrite(False).values(
                'name', 'meta_title', 'meta_description',
            )
        )
        self.assertEqual(before, after)
