"""SEO-правки: суфікс, дитячі/біблія/книги, noindex порожніх категорій."""
from __future__ import annotations

import html as html_lib
import importlib
import re

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.sitemaps import CategorySitemap
from products.attribute_filters import (
    category_has_visible_products,
    category_listing_products,
)
from products.management.commands.move_bible_products import SLUGS_MOVE_TO_BIBLE
from products.models import Category, Product

_migration = importlib.import_module('products.migrations.0026_category_seo_fixes')
apply_category_seo = _migration.apply_category_seo
BIBLE_META_DESCRIPTION = _migration.BIBLE_META_DESCRIPTION
KIDS_DESCRIPTION_HTML = _migration.KIDS_DESCRIPTION_HTML
KIDS_META_DESCRIPTION = _migration.KIDS_META_DESCRIPTION
KIDS_META_TITLE = _migration.KIDS_META_TITLE
KIDS_NAME = _migration.KIDS_NAME
SHORT_META_DESCRIPTION = _migration.SHORT_META_DESCRIPTION

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'ofion-seo-fixes',
    }
}

KEEP_SLUG = (
    'podarunkova-bibliya-u-perekazi-dlya-ditej-u-shkiryanij-paliturci-z-kartinoyu-na-metali'
)
ESSAY = '<p>Старий довгий текст. Оберіть подарункову Біблію в OFION.</p>'
BIBLE_BEFORE = '<p>Короткий попередній опис категорії Біблія.</p>'


def _title_of(html: str) -> str:
    match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
    return re.sub(r'\s+', ' ', match.group(1)).strip() if match else ''


def _h1_texts(html: str) -> list[str]:
    found = re.findall(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    return [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', item)).strip() for item in found]


def _meta_desc(html: str) -> str:
    match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html,
        re.I | re.S,
    )
    return html_lib.unescape(match.group(1)) if match else ''


def _robots(html: str) -> str:
    match = re.search(
        r'<meta\s+name=["\']robots["\']\s+content=["\'](.*?)["\']',
        html,
        re.I | re.S,
    )
    return match.group(1) if match else ''


def _product(name, slug, sku, **extra):
    defaults = {
        'description': '<p>Опис</p>',
        'price': '10.00',
        'is_active': True,
    }
    defaults.update(extra)
    return Product.objects.create(name=name, slug=slug, sku=sku, **defaults)


def _stored(slug):
    return (
        Category.objects.rewrite(False)
        .values(
            'name', 'name_uk', 'name_en',
            'meta_title', 'meta_title_uk',
            'meta_description', 'meta_description_uk',
            'description', 'description_uk',
        )
        .get(slug=slug)
    )


@override_settings(CACHES=LOC_MEM, SITE_DOMAIN='example.test', SITE_PROTOCOL='https')
class CategoryContentMigrationTests(TestCase):
    def setUp(self):
        from core.models import SiteSettings
        SiteSettings.objects.create(site_name='OFION')
        self.kids = Category.objects.create(
            name='Дитячі книги',
            name_uk='Дитячі книги',
            name_en='Children',
            slug='dityachi-knigi',
            description=ESSAY,
            meta_title='Дитячі книги',
            is_active=True,
            order=5,
            google_product_category='784',
        )
        self.bible = Category.objects.create(
            name='Біблія',
            name_uk='Біблія',
            slug='bibliya',
            description=BIBLE_BEFORE,
            meta_description='старий meta',
            is_active=True,
        )
        self.keep = _product(
            'Подарункова «Біблія у переказі для дітей»',
            KEEP_SLUG,
            'KEEP-1',
        )
        self.keep.categories.add(self.kids)
        self.moved = _product(
            'Євангеліє подарункова книга в шкірі',
            SLUGS_MOVE_TO_BIBLE[2],
            'MOVE-1',
        )
        self.moved.categories.add(self.kids)
        self.extra = _product('Казка', 'kazka-zalyshayetsya', 'MOVE-EXTRA')
        self.extra.categories.add(self.kids)

    def test_kids_bible_titles_descriptions_and_product_move(self):
        apply_category_seo(apps, None)
        apply_category_seo(apps, None)

        kids_html = self.client.get(
            reverse('products:category', kwargs={'slug': 'dityachi-knigi'}),
        ).content.decode()
        bible_html = self.client.get(
            reverse('products:category', kwargs={'slug': 'bibliya'}),
        ).content.decode()

        self.assertEqual(
            _title_of(kids_html),
            f'{KIDS_META_TITLE} | OFION',
        )
        self.assertEqual(_title_of(kids_html).count('| OFION'), 1)
        self.assertEqual(_h1_texts(kids_html), [KIDS_NAME])
        self.assertEqual(_meta_desc(kids_html), KIDS_META_DESCRIPTION)
        self.assertGreaterEqual(len(KIDS_META_DESCRIPTION), 140)
        self.assertLessEqual(len(KIDS_META_DESCRIPTION), 160)
        self.assertIn('<h2>Біблія у переказі для дітей</h2>', kids_html)
        self.assertIn('<h2>Коли подарувати</h2>', kids_html)
        self.assertEqual(_h1_texts(kids_html).__len__(), 1)

        self.assertEqual(_meta_desc(bible_html), BIBLE_META_DESCRIPTION)
        self.assertEqual(len(BIBLE_META_DESCRIPTION), 163)
        self.assertIn(BIBLE_BEFORE, bible_html)
        self.assertIn(ESSAY, bible_html)
        self.assertEqual(bible_html.count(ESSAY), 1)
        self.assertEqual(bible_html.count(BIBLE_BEFORE), 1)

        kids = _stored('dityachi-knigi')
        self.assertEqual(kids['name'], KIDS_NAME)
        self.assertEqual(kids['name_uk'], KIDS_NAME)
        self.assertEqual(kids['name_en'], 'Children')
        self.assertEqual(kids['meta_title'], KIDS_META_TITLE)
        self.assertEqual(kids['meta_title_uk'], KIDS_META_TITLE)
        self.assertEqual(kids['meta_description'], KIDS_META_DESCRIPTION)
        self.assertEqual(kids['meta_description_uk'], KIDS_META_DESCRIPTION)
        self.assertEqual(kids['description'], KIDS_DESCRIPTION_HTML)
        self.assertEqual(kids['description_uk'], KIDS_DESCRIPTION_HTML)

        bible = _stored('bibliya')
        self.assertEqual(bible['meta_description'], BIBLE_META_DESCRIPTION)
        self.assertEqual(bible['meta_description_uk'], BIBLE_META_DESCRIPTION)
        self.assertIn(BIBLE_BEFORE, bible['description'])
        self.assertIn(ESSAY, bible['description'])
        self.assertEqual(bible['description'], bible['description_uk'])
        self.assertEqual(bible['description'].count(ESSAY), 1)

        self.assertTrue(self.keep.categories.filter(slug='dityachi-knigi').exists())
        self.assertFalse(self.keep.categories.filter(slug='bibliya').exists())
        self.assertTrue(self.moved.categories.filter(slug='bibliya').exists())
        self.assertFalse(self.moved.categories.filter(slug='dityachi-knigi').exists())
        self.assertTrue(self.extra.categories.filter(slug='dityachi-knigi').exists())
        self.assertEqual(
            self.moved.categories.filter(slug='bibliya').count(),
            1,
        )

    def test_missing_slug_is_skipped(self):
        result_logs = []
        from products.management.commands.move_bible_products import move_slugs_to_bible
        outcome = move_slugs_to_bible(
            [SLUGS_MOVE_TO_BIBLE[2], 'nemaye-takogo-tovaru'],
            apply=True,
            log=result_logs.append,
        )
        self.assertIn(SLUGS_MOVE_TO_BIBLE[2], outcome['moved'])
        self.assertIn('nemaye-takogo-tovaru', outcome['skipped'])
        self.assertTrue(Category.objects.filter(slug='bibliya').exists())

    def test_slug_command_dry_run_then_apply_is_idempotent(self):
        slug = SLUGS_MOVE_TO_BIBLE[0]
        product = _product('Репринт Євангелія', slug, 'MOVE-DRY')
        product.categories.add(self.kids)
        call_command('move_bible_products', '--dry-run', '--slugs', slug, 'missing-slug')
        self.assertTrue(product.categories.filter(slug='dityachi-knigi').exists())
        self.assertFalse(product.categories.filter(slug='bibliya').exists())
        call_command('move_bible_products', '--apply', '--slugs', f'{slug},missing-slug')
        call_command('move_bible_products', '--apply', '--bible-slugs')
        product.refresh_from_db()
        self.assertEqual(
            list(product.categories.values_list('slug', flat=True)),
            ['bibliya'],
        )
        self.assertEqual(Category.objects.filter(slug='bibliya').count(), 1)

    def test_knigi_title_and_h1(self):
        Category.objects.create(
            name='Колекція книг',
            name_uk='Колекція книг',
            name_en='Book collection',
            slug='knigi',
            meta_title=(
                'Подарункові книги купити | Елітні книги в шкірі, '
                'VIP подарунки — OFION'
            ),
            meta_title_uk=(
                'Подарункові книги купити | Елітні книги в шкірі, '
                'VIP подарунки — OFION | OFION'
            ),
            is_active=True,
        )
        _product('Книга', 'kniga-v-knigi', 'KNIGI-1').categories.add(
            Category.objects.get(slug='knigi'),
        )
        apply_category_seo(apps, None)
        html = self.client.get(
            reverse('products:category', kwargs={'slug': 'knigi'}),
        ).content.decode()
        title = _title_of(html)
        self.assertEqual(
            title,
            'Подарункові книги купити | Елітні книги в шкірі, VIP подарунки | OFION',
        )
        self.assertEqual(title.count('OFION'), 1)
        self.assertNotIn('— OFION', title)
        self.assertEqual(_h1_texts(html), ['Подарункові книги'])
        stored = _stored('knigi')
        self.assertEqual(stored['name'], 'Подарункові книги')
        self.assertEqual(stored['name_uk'], 'Подарункові книги')
        self.assertEqual(stored['name_en'], 'Book collection')
        self.assertNotIn('OFION', stored['meta_title_uk'])

    def test_short_meta_descriptions_lengths(self):
        for slug, text in SHORT_META_DESCRIPTION.items():
            self.assertGreaterEqual(len(text), 140, slug)
            self.assertLessEqual(len(text), 160, slug)
            Category.objects.create(
                name=slug,
                slug=slug,
                meta_description='довгий старий текст ' * 20,
                is_active=True,
            )
        apply_category_seo(apps, None)
        for slug, text in SHORT_META_DESCRIPTION.items():
            stored = _stored(slug)
            self.assertEqual(stored['meta_description'], text)
            self.assertEqual(stored['meta_description_uk'], text)
            html = self.client.get(
                reverse('products:category', kwargs={'slug': slug}),
            ).content.decode()
            self.assertEqual(_meta_desc(html), text)


@override_settings(CACHES=LOC_MEM, SITE_DOMAIN='example.test', SITE_PROTOCOL='https')
class EmptyCategoryIndexTests(TestCase):
    def setUp(self):
        from core.models import SiteSettings
        SiteSettings.objects.create(site_name='OFION')
        self.empty = Category.objects.create(
            name='Коран', slug='koran', is_active=True,
        )

    def _page(self, slug):
        return self.client.get(
            reverse('products:category', kwargs={'slug': slug}),
        ).content.decode()

    def _sitemap_ids(self):
        return {item.pk for item in CategorySitemap().items()}

    def test_empty_is_noindex_and_returns_when_product_appears(self):
        html = self._page('koran')
        self.assertEqual(_robots(html), 'noindex,follow')
        self.assertNotIn(self.empty.pk, self._sitemap_ids())
        self.assertNotIn('/catalog/koran/', self.client.get('/sitemap.xml').content.decode())

        product = _product('Видання', 'koran-vydannya', 'KORAN-1', stock_status='out')
        product.categories.add(self.empty)
        html = self._page('koran')
        self.assertEqual(_robots(html), 'index, follow')
        self.assertIn(self.empty.pk, self._sitemap_ids())
        self.assertIn('/catalog/koran/', self.client.get('/sitemap.xml').content.decode())
        self.assertTrue(category_listing_products(self.empty).filter(pk=product.pk).exists())

        product.is_active = False
        product.save(update_fields=['is_active'])
        self.assertEqual(_robots(self._page('koran')), 'noindex,follow')
        self.assertNotIn(self.empty.pk, self._sitemap_ids())

    def test_descendant_product_indexes_ancestors_until_removed(self):
        child = Category.objects.create(
            name='Дитина', slug='koran-child', parent=self.empty, is_active=True,
        )
        grand = Category.objects.create(
            name='Онук', slug='koran-grand', parent=child, is_active=True,
        )
        hidden = Category.objects.create(
            name='Прихована', slug='koran-hidden', parent=self.empty, is_active=False,
        )
        self.assertFalse(category_has_visible_products(self.empty))
        self.assertEqual(_robots(self._page('koran')), 'noindex,follow')

        hidden_product = _product('Схований', 'koran-hidden-item', 'KORAN-H')
        hidden_product.categories.add(hidden)
        self.assertFalse(category_has_visible_products(self.empty))
        self.assertNotIn(self.empty.pk, self._sitemap_ids())

        product = _product('В онуці', 'koran-grand-item', 'KORAN-G')
        product.categories.add(grand)
        self.assertFalse(category_listing_products(self.empty).filter(pk=product.pk).exists())
        self.assertTrue(category_has_visible_products(self.empty))
        self.assertTrue(category_has_visible_products(child))
        self.assertEqual(_robots(self._page('koran')), 'index, follow')
        sitemap_ids = self._sitemap_ids()
        self.assertIn(self.empty.pk, sitemap_ids)
        self.assertIn(child.pk, sitemap_ids)
        self.assertIn(grand.pk, sitemap_ids)
        self.assertNotIn(hidden.pk, sitemap_ids)

        product.delete()
        self.assertEqual(_robots(self._page('koran')), 'noindex,follow')
        self.assertNotIn(self.empty.pk, self._sitemap_ids())
