"""Зірки рейтингу зі схвалених відгуків без N+1 і AggregateRating у JSON-LD."""
import json
from pathlib import Path

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import SiteSettings
from core.seo import get_home_json_ld
from products.models import Category, Product
from products.schema import get_product_schema
from promotions.models import UpsellGroup
from reviews.models import Review

ROOT = Path(__file__).resolve().parents[2]


def _product(sku, name, **extra):
    defaults = {
        'name': name,
        'slug': sku.lower(),
        'sku': sku,
        'description': 'Опис',
        'price': '100.00',
        'is_active': True,
    }
    defaults.update(extra)
    return Product.objects.create(**defaults)


def _review(product, rating, approved=True):
    return Review.objects.create(
        product=product,
        author_name='Тест',
        rating=rating,
        text='Текст відгуку',
        is_approved=approved,
    )


def _queries(url, params=None):
    client = Client()
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url, params or {})
        response.content
    return len(ctx.captured_queries), response


class RatingAggregateTests(TestCase):
    def test_середнє_лише_зі_схвалених(self):
        product = _product('RT-AVG', 'Книга із оцінкою')
        _review(product, 5, True)
        _review(product, 3, True)
        _review(product, 1, False)
        row = Product.objects.with_rating().get(pk=product.pk)
        self.assertEqual(row.rating_count, 2)
        self.assertEqual(round(row.rating_avg, 2), 4.0)

    def test_дві_категорії_не_подвоюють_кількість(self):
        parent = Category.objects.create(name='Батько', slug='rt-parent', is_active=True)
        first = Category.objects.create(
            name='Одна', slug='rt-one', parent=parent, is_active=True,
        )
        second = Category.objects.create(
            name='Дві', slug='rt-two', parent=parent, is_active=True,
        )
        product = _product('RT-CAT', 'Товар у двох категоріях')
        product.categories.add(first, second)
        _review(product, 5, True)
        _review(product, 3, True)
        _review(product, 2, False)
        row = (
            Product.objects.filter(categories__id__in=[first.id, second.id])
            .with_rating()
            .distinct()
            .get(pk=product.pk)
        )
        self.assertEqual(row.rating_count, 2)
        self.assertEqual(round(row.rating_avg, 2), 4.0)

        response = self.client.get(reverse('products:category', kwargs={'slug': parent.slug}))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count('class="rating"'), 1)
        self.assertIn('(2)', html)
        self.assertNotIn('(4)', html)

    def test_запит_рейтингу_один_незалежно_від_кількості(self):
        _product('RT-Q1', 'Перший')
        _review(Product.objects.get(sku='RT-Q1'), 5, True)
        with self.assertNumQueries(1):
            rows = list(Product.objects.filter(sku__startswith='RT-Q').with_rating())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].rating_count, 1)

        for index in range(2, 5):
            product = _product(f'RT-Q{index}', f'Товар {index}')
            _review(product, 4, True)
            _review(product, 2, False)
        with self.assertNumQueries(1):
            rows = list(Product.objects.filter(sku__startswith='RT-Q').with_rating())
        self.assertEqual(len(rows), 4)
        self.assertEqual({row.rating_count for row in rows}, {1})

    def test_json_ld_лише_коли_є_схвалені_і_без_зайвого_запиту(self):
        empty = _product('RT-EMPTY', 'Без відгуків')
        hidden = _product('RT-HIDDEN', 'Лише на модерації')
        _review(hidden, 5, False)
        rated = _product('RT-JSON', 'Зі схваленим')
        _review(rated, 5, True)
        _review(rated, 3, True)
        _review(rated, 1, False)

        self.assertIsNone(get_product_schema(empty, None).get('aggregateRating'))
        self.assertIsNone(get_product_schema(hidden, None).get('aggregateRating'))

        annotated = Product.objects.with_rating().get(pk=rated.pk)
        with CaptureQueriesContext(connection) as ctx:
            schema = get_product_schema(annotated, None)
        review_sql = [
            query['sql'] for query in ctx.captured_queries
            if 'reviews_review' in query['sql']
        ]
        self.assertEqual(review_sql, [])
        self.assertEqual(schema['aggregateRating']['ratingValue'], '4.0')
        self.assertEqual(schema['aggregateRating']['reviewCount'], '2')
        self.assertEqual(schema['aggregateRating']['bestRating'], '5')
        self.assertEqual(schema['aggregateRating']['worstRating'], '1')
        self.assertEqual(schema['@type'], 'Product')
        self.assertIn('offers', schema)

    def test_головна_json_ld_без_aggregate_rating(self):
        site = SiteSettings.objects.create(site_name='OFION', email='a@b.c')
        payload = json.dumps(get_home_json_ld(site, None), ensure_ascii=False)
        self.assertIn('Organization', payload)
        self.assertIn('WebSite', payload)
        self.assertNotIn('AggregateRating', payload)


class RatingPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name='Каталог рейтингу', slug='rt-catalog', is_active=True,
        )
        cls.plain = _product('RT-PLAIN', 'Товар без відгуків')
        cls.plain.categories.add(cls.category)
        cls.rated = _product('RT-SHOW', 'зорярейтинг альбом')
        cls.rated.categories.add(cls.category)
        _review(cls.rated, 5, True)
        _review(cls.rated, 3, True)
        _review(cls.rated, 1, False)
        cls.extra = _product('RT-EXTRA', 'Схожий зорярейтинг')
        cls.extra.categories.add(cls.category)
        _review(cls.extra, 4, True)
        group = UpsellGroup.objects.create(
            name='До подарунку', trigger_product=cls.rated, is_active=True,
        )
        group.suggested_products.add(cls.extra)

    def test_зірки_на_картках_і_сторінці_і_немає_без_відгуків(self):
        catalog = self.client.get(reverse('products:catalog')).content.decode()
        self.assertEqual(catalog.count('class="rating"'), 2)
        self.assertIn('зорярейтинг альбом', catalog)
        self.assertIn('Товар без відгуків', catalog)
        self.assertRegex(
            catalog,
            r'aria-label="Середня оцінка 4[.,]0 з 5, кількість відгуків: 2"',
        )
        self.assertIn('--rating-pct: 80%', catalog)
        self.assertIn('var(--color-accent)', (ROOT / 'static/css/product-card.css').read_text())

        home = self.client.get(reverse('core:home')).content.decode()
        self.assertIn('class="rating"', home)
        self.assertNotIn('AggregateRating', home)

        search = self.client.get(
            reverse('products:search'), {'q': 'зорярейтинг'},
        ).content.decode()
        self.assertEqual(search.count('class="rating"'), 2)

        detail = self.client.get(
            reverse('products:detail', kwargs={'slug': self.rated.slug}),
        ).content.decode()
        self.assertIn('"@type": "AggregateRating"', detail)
        self.assertIn('"ratingValue": "4.0"', detail)
        self.assertIn('"reviewCount": "2"', detail)
        self.assertRegex(
            detail,
            r'aria-label="Середня оцінка 4[.,]0 з 5, кількість відгуків: 2"',
        )
        self.assertIn('Схожий зорярейтинг', detail)
        self.assertIn('Додай до подарунку', detail)

        plain = self.client.get(
            reverse('products:detail', kwargs={'slug': self.plain.slug}),
        ).content.decode()
        info_end = plain.find('product-info__actions')
        self.assertNotIn('class="rating"', plain[:info_end])
        self.assertNotIn('AggregateRating', plain)

        gift = self.client.get(reverse('promotions:gift_picker_results')).content.decode()
        self.assertEqual(gift.count('class="rating"'), 2)
        self.assertIn('Товар без відгуків', gift)

        loner = _product('RT-LONER', 'Окремий товар')
        self.client.get(reverse('products:detail', kwargs={'slug': self.rated.slug}))
        loner_html = self.client.get(
            reverse('products:detail', kwargs={'slug': loner.slug}),
        ).content.decode()
        self.assertIn('Ви переглядали', loner_html)
        self.assertEqual(loner_html.count('class="rating"'), 1)
        self.assertNotIn('AggregateRating', loner_html)

        rows = list(self.rated.upsell_triggers.first().suggested_products.with_rating())
        self.assertEqual(rows[0].rating_count, 1)

    def test_кількість_запитів_списків_не_залежить_від_кількості_товарів(self):
        category = Category.objects.create(name='Стабільні', slug='rt-stable', is_active=True)
        token = 'стабільнийрейтинг'

        def add_products(start, amount):
            created = []
            for index in range(start, start + amount):
                product = _product(f'RT-N{index}', f'{token} {index}')
                product.categories.add(category)
                _review(product, 5, True)
                _review(product, 4, True)
                _review(product, 1, False)
                created.append(product)
            return created

        anchor = _product('RT-ANCHOR', 'Якір сторінки')
        anchor.categories.add(category)
        add_products(1, 1)

        urls = {
            'catalog': (reverse('products:catalog'), {}),
            'home': (reverse('core:home'), {}),
            'search': (reverse('products:search'), {'q': token}),
            'category': (reverse('products:category', kwargs={'slug': category.slug}), {}),
            'detail': (reverse('products:detail', kwargs={'slug': anchor.slug}), {}),
        }
        before = {name: _queries(url, params)[0] for name, (url, params) in urls.items()}
        add_products(2, 3)
        after = {name: _queries(url, params)[0] for name, (url, params) in urls.items()}
        self.assertEqual(before, after)

        catalog = _queries(reverse('products:catalog'))[1].content.decode()
        self.assertIn('class="rating"', catalog)
        self.assertIn('(2)', catalog)
