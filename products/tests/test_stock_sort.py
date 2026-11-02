from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Category, Product

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'stock-sort-tests',
    }
}


def make_product(**kwargs):
    defaults = {
        'name': 'Товар',
        'slug': 'tovar',
        'sku': 'SKU-1',
        'description': 'Опис',
        'price': '100.00',
        'stock_status': 'in_stock',
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


def _order(html, *slugs):
    positions = [html.index(slug) for slug in slugs]
    return positions == sorted(positions)


@override_settings(CACHES=LOC_MEM)
class StockSortTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Книги', slug='books-stock')
        self.on_order = make_product(
            name='Під замовлення', slug='on-order', sku='ORD',
            price='200.00', stock_status='order',
        )
        self.ready = make_product(
            name='Готово', slug='ready-item', sku='RDY',
            price='80.00', stock_status='ready',
        )
        self.in_stock = make_product(
            name='В наявності', slug='in-stock', sku='IN',
            price='10.00', stock_status='in_stock',
        )
        self.out_cheap = make_product(
            name='Немає дешево', slug='out-cheap', sku='OUT1',
            price='1.00', stock_status='out',
        )
        self.out_new = make_product(
            name='Немає нове', slug='out-new', sku='OUT2',
            price='500.00', stock_status='out',
        )
        for product in (
            self.on_order, self.ready, self.in_stock, self.out_cheap, self.out_new,
        ):
            product.categories.add(self.category)

    def test_out_of_stock_is_last_for_every_catalog_sort(self):
        url = reverse('products:catalog')
        asc = self.client.get(url, {'sort': 'price_asc'}).content.decode()
        self.assertTrue(_order(asc, 'in-stock', 'ready-item', 'on-order', 'out-cheap', 'out-new'))

        desc = self.client.get(url, {'sort': 'price_desc'}).content.decode()
        self.assertTrue(_order(desc, 'on-order', 'ready-item', 'in-stock', 'out-new', 'out-cheap'))

        newest = self.client.get(url, {'sort': 'newest'}).content.decode()
        self.assertLess(newest.index('out-new'), newest.index('out-cheap'))
        self.assertLess(newest.index('on-order'), newest.index('out-new'))

    def test_category_default_and_price_keep_preorder_in_place(self):
        url = reverse('products:category', kwargs={'slug': 'books-stock'})
        default = self.client.get(url).content.decode()
        self.assertLess(default.index('on-order'), default.index('out-cheap'))
        self.assertLess(default.index('in-stock'), default.index('out-cheap'))

        desc = self.client.get(url, {'sort': 'price_desc'}).content.decode()
        self.assertTrue(_order(desc, 'on-order', 'ready-item', 'in-stock', 'out-new', 'out-cheap'))

    def test_search_puts_out_of_stock_last_even_with_better_rank(self):
        exact_out = make_product(
            name='Інше', slug='exact-out', sku='ABC999',
            price='1.00', stock_status='out',
        )
        mentioned = make_product(
            name='Згадка', slug='mentioned-in', sku='ZZZ111',
            description='<p>ABC999 у тексті</p>', price='100.00',
        )
        preorder = make_product(
            name='Замовлення ABC999', slug='preorder-hit', sku='PRE1',
            price='300.00', stock_status='order',
        )
        url = reverse('products:search')
        default = self.client.get(url, {'q': 'ABC999'}).content.decode()
        self.assertLess(default.index('preorder-hit'), default.index('exact-out'))
        self.assertLess(default.index('mentioned-in'), default.index('exact-out'))

        asc = self.client.get(url, {'q': 'ABC999', 'sort': 'price_asc'}).content.decode()
        self.assertTrue(_order(asc, 'mentioned-in', 'preorder-hit', 'exact-out'))

        desc = self.client.get(url, {'q': 'ABC999', 'sort': 'price_desc'}).content.decode()
        self.assertTrue(_order(desc, 'preorder-hit', 'mentioned-in', 'exact-out'))
