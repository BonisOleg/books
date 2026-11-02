"""Меню категорій без ліміту кількості."""
from __future__ import annotations

import re

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from products.models import Category

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'header-menu-tests',
    }
}


def _block(html, pattern):
    match = re.search(pattern, html, re.S)
    return match.group(1) if match else ''


@override_settings(CACHES=LOC_MEM)
class NavCategoryMenuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.expected = []
        for index in range(1, 16):
            slug = f'menu-cat-{index:02d}'
            Category.objects.create(
                name=f'Яблуко {16 - index:02d}',
                slug=slug,
                order=index,
                is_active=True,
            )
            cls.expected.append(slug)
        Category.objects.create(
            name='Прихована категорія',
            slug='menu-hidden',
            order=0,
            is_active=False,
        )
        parent = Category.objects.get(slug='menu-cat-01')
        Category.objects.create(
            name='Підкатегорія меню',
            slug='menu-child',
            parent=parent,
            order=0,
            is_active=True,
        )

    def test_menu_and_catalog_show_every_active_root_in_order(self):
        home = self.client.get('/').content.decode()
        mega_slugs = re.findall(
            r'/catalog/([^"/]+)/',
            _block(home, r'class="megamenu__grid">(.*?)</div>'),
        )
        mobile_slugs = re.findall(
            r'/catalog/([^"/]+)/',
            _block(home, r'id="mobile-menu"(.*?)</nav>'),
        )
        self.assertEqual(mega_slugs, self.expected)
        self.assertEqual(mobile_slugs, self.expected)
        self.assertGreater(len(mega_slugs), 12)
        self.assertNotIn('menu-hidden', home)
        self.assertNotIn('menu-child', mega_slugs)

        catalog = self.client.get('/catalog/').content.decode()
        grid_slugs = re.findall(
            r'/catalog/([^"/]+)/',
            _block(catalog, r'class="categories-grid">(.*?)<div class="catalog-toolbar"'),
        )
        self.assertEqual(grid_slugs, self.expected)
        self.assertNotIn('menu-hidden', catalog)

    def test_category_queries_have_no_limit(self):
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        category_sql = [
            query['sql'] for query in captured.captured_queries
            if 'products_category' in query['sql'].lower()
        ]
        self.assertTrue(category_sql)
        for sql in category_sql:
            self.assertNotIn('LIMIT', sql.upper())
