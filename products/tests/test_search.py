from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Product

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'search-tests',
    }
}


def make_product(**kwargs):
    defaults = {
        'name': 'Товар',
        'slug': 'tovar',
        'sku': 'SKU-1',
        'description': '<p>Опис</p>',
        'price': '100.00',
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


@override_settings(CACHES=LOC_MEM)
class SearchTests(TestCase):
    def test_cyrillic_quotes_and_case(self):
        product = make_product(
            name='Насіння томатів «Черрі»',
            slug='cherry',
            sku='SEED-001',
        )
        for query in ('черрі', 'ЧЕРРІ', '«Черрі»'):
            response = self.client.get(reverse('products:search'), {'q': query})
            self.assertContains(response, product.slug)

    def test_uk_ru_fold(self):
        product = make_product(name='Ікра', slug='ikra', sku='IKRA-1')
        response = self.client.get(reverse('products:search'), {'q': 'икра'})
        self.assertContains(response, product.slug)

    def test_english_name_found_on_uk_site(self):
        product = make_product(name='Блокнот', slug='notebook', sku='NB-1')
        product.name_en = 'Leather notebook'
        product.save()
        response = self.client.get(reverse('products:search'), {'q': 'notebook'})
        self.assertContains(response, product.slug)

    def test_sku_and_manufacturer(self):
        product = make_product(
            name='Альбом',
            slug='album',
            sku='ALB-77',
            manufacturer='Penguin',
        )
        by_sku = self.client.get(reverse('products:search'), {'q': 'ALB-77'})
        by_brand = self.client.get(reverse('products:search'), {'q': 'penguin'})
        self.assertContains(by_sku, product.slug)
        self.assertContains(by_brand, product.slug)

    def test_supplier_sku_is_not_public(self):
        product = make_product(
            name='Звичайна книга',
            slug='plain-book',
            sku='BOOK-1',
            sku_manufacturer='SUP-999-SECRET',
        )
        response = self.client.get(reverse('products:search'), {'q': 'SUP-999-SECRET'})
        self.assertNotContains(response, product.slug)
        product.refresh_from_db()
        self.assertNotIn('sup-999-secret', product.search_text)

    def test_tokens_are_independent_of_order(self):
        product = make_product(name='Фентезійна книга', slug='fantasy', sku='FAN-1')
        response = self.client.get(reverse('products:search'), {'q': 'книга фентезі'})
        self.assertContains(response, product.slug)

    def test_inactive_hidden(self):
        product = make_product(name='Прихована', slug='inactive-item', sku='HID-1', is_active=False)
        response = self.client.get(reverse('products:search'), {'q': 'Прихована'})
        self.assertNotContains(response, product.slug)

    def test_short_query_does_not_dump_catalog(self):
        make_product(name='Видимий', slug='shown-item', sku='VIS-1')
        response = self.client.get(reverse('products:search'), {'q': 'а'})
        self.assertContains(response, 'Введіть щонайменше 2 символи')
        self.assertNotContains(response, 'shown-item')

    def test_exact_sku_ranks_above_description(self):
        exact = make_product(name='Інше', slug='exact-sku', sku='ABC123', price='100.00')
        mentioned = make_product(
            name='Інше два',
            slug='mentioned',
            sku='ZZZ999',
            description='<p>згадка ABC123 у тексті</p>',
            price='10.00',
        )
        response = self.client.get(reverse('products:search'), {'q': 'ABC123'})
        html = response.content.decode()
        self.assertLess(html.index(exact.slug), html.index(mentioned.slug))

    def test_price_sort_overrides_rank(self):
        expensive = make_product(name='Альфа', slug='expensive', sku='ABC123', price='100.00')
        cheap = make_product(
            name='Бета',
            slug='cheap',
            sku='ZZZ999',
            description='<p>ABC123</p>',
            price='10.00',
        )
        response = self.client.get(reverse('products:search'), {'q': 'ABC123', 'sort': 'price_asc'})
        html = response.content.decode()
        self.assertLess(html.index(cheap.slug), html.index(expensive.slug))

    def test_pagination_keeps_query(self):
        for index in range(25):
            make_product(name=f'Спільне {index}', slug=f'shared-{index}', sku=f'SH-{index}')
        response = self.client.get(reverse('products:search'), {'q': 'спільне', 'page': 2})
        self.assertEqual(response.content.decode().count('class="product-card"'), 1)
        self.assertContains(response, 'q=')
        self.assertContains(response, 'page=1')

    def test_sort_link_keeps_query(self):
        make_product(name='Спільне', slug='shared', sku='SH-1')
        response = self.client.get(reverse('products:search'), {'q': 'спільне'})
        self.assertContains(response, 'sort=price_asc')
        self.assertContains(response, 'q=')

    def test_suggest_limits_to_eight(self):
        for index in range(10):
            make_product(name=f'Підказка {index}', slug=f'hint-{index}', sku=f'HINT-{index}')
        response = self.client.get(reverse('products:search_suggest'), {'q': 'підказка'})
        self.assertEqual(response.content.decode().count('role="option"'), 8)
        self.assertContains(response, 'Показати всі результати')

    def test_suggest_rate_limit(self):
        last = None
        for _ in range(61):
            last = self.client.get(reverse('products:search_suggest'), {'q': 'аб'})
        self.assertEqual(last.status_code, 429)

    def test_rebuild_command(self):
        product = make_product(name='Відновлення', slug='rebuild', sku='RB-1')
        Product.objects.filter(pk=product.pk).update(search_text='', search_name='')
        call_command('rebuild_search_text')
        product.refresh_from_db()
        self.assertIn('видновлення', product.search_text)

    def test_catalog_ignores_q(self):
        first = make_product(name='Перший', slug='first', sku='C-1')
        second = make_product(name='Другий', slug='second', sku='C-2')
        response = self.client.get(reverse('products:catalog'), {'q': 'Перший'})
        self.assertContains(response, first.slug)
        self.assertContains(response, second.slug)
