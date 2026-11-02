"""SEO regression tests for title, H1, alts, pagination, meta, JSON-LD, sitemap."""
from __future__ import annotations

import re
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import SiteSettings
from core.seo import (
    build_product_meta_description,
    demote_h1_html,
    normalize_product_name,
    truncate_at_word,
    with_site_suffix,
)
from products.models import Category, Product, ProductAttribute, ProductImage

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'seo-tests',
    }
}


def _png(name='t.png', size=(40, 40), color=(10, 20, 30)):
    if Image is None:
        return SimpleUploadedFile(name, b'fake', content_type='image/png')
    buf = BytesIO()
    Image.new('RGB', size, color).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def _title_of(html: str) -> str:
    m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def _count_h1(html: str) -> int:
    return len(re.findall(r'<h1\b', html, re.I))


def _ofion_count(title: str) -> int:
    return len(re.findall(r'OFION', title, re.I))


def _meta_desc(html: str) -> str:
    m = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html,
        re.I | re.S,
    )
    return m.group(1) if m else ''


def _canonical(html: str) -> str:
    m = re.search(
        r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']',
        html,
        re.I,
    )
    return m.group(1) if m else ''


@override_settings(CACHES=LOC_MEM, SITE_DOMAIN='example.test', SITE_PROTOCOL='https')
class SeoHelpersTests(TestCase):
    def test_with_site_suffix_idempotent(self):
        self.assertEqual(with_site_suffix('Ікони'), 'Ікони | OFION')
        self.assertEqual(with_site_suffix('Ікони | OFION'), 'Ікони | OFION')
        self.assertEqual(with_site_suffix('Ікони | OFION | OFION'), 'Ікони | OFION')
        self.assertEqual(
            with_site_suffix('Ікони | OFION — сторінка 2'),
            'Ікони — сторінка 2 | OFION',
        )
        self.assertEqual(with_site_suffix(''), 'OFION')

    def test_demote_h1(self):
        html = demote_h1_html('<h1>SEO</h1><p>x</p>')
        self.assertIn('<h2 class="seo-h2">SEO</h2>', html)
        self.assertNotIn('<h1', html.lower())

    def test_truncate_at_word(self):
        text = 'один два три чотири пʼять'
        self.assertEqual(truncate_at_word(text, 12), 'один два')
        self.assertLessEqual(len(truncate_at_word('a' * 200, 160)), 160)

    def test_normalize_product_name(self):
        self.assertEqual(normalize_product_name('  \xa0Біблія\xa0  '), 'Біблія')

    def test_product_meta_description_auto_and_custom(self):
        cat = Category.objects.create(name='Книги', slug='knygy-seo')
        p = Product.objects.create(
            name='Елітна Біблія',
            slug='elitna-bibliya-seo',
            sku='SEO-1',
            description='Опис',
            price='100.00',
        )
        p.categories.add(cat)
        ProductAttribute.objects.create(product=p, name='Обкладинка', value='шкіра')
        auto = build_product_meta_description(p)
        self.assertLessEqual(len(auto), 160)
        self.assertIn('Елітна Біблія', auto)
        self.assertIn('купити в OFION', auto)
        self.assertIn('Доставка по Україні', auto)

        p.meta_description = 'Власний опис ' + ('слово ' * 40)
        p.save()
        custom = build_product_meta_description(p)
        self.assertLessEqual(len(custom), 160)
        self.assertTrue(custom.startswith('Власний опис'))


@override_settings(CACHES=LOC_MEM, SITE_DOMAIN='example.test', SITE_PROTOCOL='https')
class SeoPagesClientTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        SiteSettings.objects.create(
            site_name='OFION',
            email='shop@example.test',
            phone_1='+380501112233',
            facebook_url='https://facebook.com/ofion',
            seo_home_title='OFION – статусні подарунки',
            site_description='<h1>Про магазин</h1><p>Текст</p>',
        )
        cls.category = Category.objects.create(
            name='Ікони',
            slug='ikoni',
            meta_title='Ікони | OFION',
            meta_description='Опис категорії ікон',
            description='<h1>SEO заголовок</h1><p>Текст SEO</p>',
            is_active=True,
        )
        cls.product = Product.objects.create(
            name='Біблія подарункова з емалями',
            slug='bibliya-podarunkova-z-emalyamy',
            sku='SEO-PROD-1',
            description='<p>Опис товару</p>',
            short_description='Шкіряна обкладинка',
            meta_title='Біблія подарункова | OFION',
            order_info='<h1>Інформація для замовлення</h1><p>НП</p>',
            price='1500.00',
            is_active=True,
        )
        cls.product.categories.add(cls.category)
        ProductImage.objects.create(
            product=cls.product, image=_png('a.png'), order=0, alt_text=''
        )
        ProductImage.objects.create(
            product=cls.product, image=_png('b.png'), order=1, alt_text=''
        )
        # enough products for page=2 (paginate_by=24)
        for i in range(30):
            p = Product.objects.create(
                name=f'Товар пагінації {i}',
                slug=f'tovar-paginacii-{i}',
                sku=f'SEO-P-{i}',
                description='x',
                price='10.00',
                is_active=True,
            )
            p.categories.add(cls.category)

    def test_category_title_one_ofion_and_one_h1(self):
        url = reverse('products:category', kwargs={'slug': 'ikoni'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        title = _title_of(html)
        self.assertEqual(_ofion_count(title), 1)
        self.assertTrue(title.endswith('| OFION'))
        self.assertEqual(_count_h1(html), 1)
        self.assertIn('<h2 class="seo-h2">SEO заголовок</h2>', html)
        self.assertNotIn('<h1>SEO заголовок</h1>', html)

    def test_product_title_h1_alts_description(self):
        url = reverse(
            'products:detail',
            kwargs={'slug': 'bibliya-podarunkova-z-emalyamy'},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        title = _title_of(html)
        self.assertEqual(_ofion_count(title), 1)
        self.assertEqual(_count_h1(html), 1)
        self.assertIn('<h2 class="seo-h2">Інформація для замовлення</h2>', html)
        self.assertIn('alt="Біблія подарункова з емалями"', html)
        self.assertIn('alt="Біблія подарункова з емалями — фото 1"', html)
        self.assertIn('alt="Біблія подарункова з емалями — фото 2"', html)
        desc = _meta_desc(html)
        self.assertLessEqual(len(desc), 160)
        self.assertTrue(desc)

    def test_home_one_h1_one_ofion_json_ld(self):
        r = self.client.get(reverse('core:home'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        title = _title_of(html)
        self.assertEqual(_ofion_count(title), 1)
        self.assertEqual(_count_h1(html), 1)
        self.assertIn('"@graph"', html)
        self.assertIn('"Organization"', html)
        self.assertIn('"WebSite"', html)
        self.assertIn('<h2 class="seo-h2">Про магазин</h2>', html)

    def test_pagination_canonical_and_title(self):
        url = reverse('products:category', kwargs={'slug': 'ikoni'})
        r1 = self.client.get(url)
        html1 = r1.content.decode()
        self.assertNotIn('page=1', _canonical(html1))
        self.assertNotIn('сторінка 1', _title_of(html1))

        r2 = self.client.get(url, {'page': 2})
        html2 = r2.content.decode()
        canon = _canonical(html2)
        self.assertIn('page=2', canon)
        title = _title_of(html2)
        self.assertIn('сторінка 2', title)
        self.assertTrue(title.endswith('| OFION'))
        self.assertEqual(_ofion_count(title), 1)
        desc = _meta_desc(html2)
        self.assertIn('сторінка 2', desc)

    def test_sitemap_home_priority(self):
        r = self.client.get('/sitemap.xml')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('<priority>1.0</priority>', body)

    def test_product_name_trim_on_save(self):
        p = Product.objects.create(
            name='\xa0 Обрізана назва  ',
            slug='obrizana-nazva-seo',
            sku='SEO-TRIM',
            description='d',
            price='1.00',
        )
        p.refresh_from_db()
        self.assertEqual(p.name, 'Обрізана назва')


@override_settings(CACHES=LOC_MEM)
class MoveBibleProductsCommandTests(TestCase):
    def setUp(self):
        self.src = Category.objects.create(name='Дитячі', slug='dityachi-knigi')
        self.dst = Category.objects.create(name='Біблія', slug='bibliya')
        self.hit = Product.objects.create(
            name='Дитяча Біблія',
            slug='dytyacha-bibliya',
            sku='BIB-1',
            description='d',
            price='1.00',
        )
        self.hit.categories.add(self.src)
        self.miss = Product.objects.create(
            name='Казка',
            slug='kazka',
            sku='BIB-2',
            description='d',
            price='1.00',
        )
        self.miss.categories.add(self.src)

    def test_dry_run_default_no_changes(self):
        call_command('move_bible_products')
        self.assertTrue(self.hit.categories.filter(slug='dityachi-knigi').exists())
        self.assertFalse(self.hit.categories.filter(slug='bibliya').exists())

    def test_apply_moves(self):
        call_command('move_bible_products', '--apply')
        self.hit.refresh_from_db()
        self.assertTrue(self.hit.categories.filter(slug='bibliya').exists())
        self.assertFalse(self.hit.categories.filter(slug='dityachi-knigi').exists())
        self.assertTrue(self.miss.categories.filter(slug='dityachi-knigi').exists())

    def test_product_url_independent_of_category(self):
        url = self.hit.get_absolute_url()
        self.assertEqual(url, '/catalog/product/dytyacha-bibliya/')
