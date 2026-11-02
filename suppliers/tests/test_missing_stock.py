from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from suppliers.models import Supplier, SupplierSyncRun
from suppliers.services import sync_supplier

from .utils import feed_bytes, make_product, make_supplier


class SupplierDefaultTests(TestCase):
    def test_price_rule_defaults_to_as_is_and_zero_markup(self):
        price = Supplier._meta.get_field('price_rule')
        markup = Supplier._meta.get_field('markup_percent')
        self.assertEqual(price.default, 'as_is')
        self.assertEqual(markup.default, Decimal('0.00'))
        supplier = Supplier.objects.create(
            name='Типовий',
            feed_url='https://example.com/feed.xml',
        )
        supplier.refresh_from_db()
        self.assertEqual(supplier.price_rule, 'as_is')
        self.assertEqual(supplier.markup_percent, Decimal('0.00'))

    def test_mark_missing_out_of_stock_defaults_to_true(self):
        flag = Supplier._meta.get_field('mark_missing_out_of_stock')
        self.assertIs(flag.default, True)
        supplier = make_supplier()
        supplier.refresh_from_db()
        self.assertTrue(supplier.mark_missing_out_of_stock)


class MissingStockDryRunTests(TestCase):
    def test_dry_run_counts_only_safe_missing_codes_and_does_not_write(self):
        missing = make_product(
            name='Зникне', slug='gone', sku='GONE',
            sku_manufacturer='NO-FEED', price=Decimal('10.00'),
            stock_status='in_stock',
        )
        already = make_product(
            name='Вже немає', slug='gone-out', sku='GONE-OUT',
            sku_manufacturer='ALREADY-OUT', stock_status='out',
            price=Decimal('10.00'),
        )
        blank = make_product(
            name='Без коду', slug='gone-blank', sku='GONE-BLANK',
            sku_manufacturer='', price=Decimal('10.00'),
            stock_status='in_stock',
        )
        spaces = make_product(
            name='Самі пробіли', slug='gone-spaces', sku='GONE-SP',
            sku_manufacturer='   ', price=Decimal('10.00'),
            stock_status='in_stock',
        )
        dup_a = make_product(
            name='Дубль А', slug='gone-dup-a', sku='GONE-DUP-A',
            sku_manufacturer='DUP', stock_status='in_stock',
            price=Decimal('10.00'),
        )
        dup_b = make_product(
            name='Дубль Б', slug='gone-dup-b', sku='GONE-DUP-B',
            sku_manufacturer='dup', stock_status='in_stock',
            price=Decimal('11.00'),
        )
        in_feed = make_product(
            name='У фіді', slug='gone-in', sku='GONE-IN',
            sku_manufacturer='KEEP', price=Decimal('3.00'),
            stock_status='in_stock',
        )
        feed_dup = make_product(
            name='Конфлікт фіду', slug='gone-feed-dup', sku='GONE-FD',
            sku_manufacturer='ZZ', stock_status='in_stock',
            price=Decimal('8.00'),
        )
        supplier = make_supplier()
        with CaptureQueriesContext(connection) as ctx:
            run = sync_supplier(supplier, dry_run=True, source=feed_bytes([
                {'id': 'KEEP', 'price': '9 UAH', 'title': 'Лишається'},
                {'id': 'ZZ', 'price': '30 UAH', 'title': 'Дубль фіду'},
                {'id': 'zz', 'price': '31 UAH', 'title': 'Дубль фіду 2'},
            ]))
        for product, stock in (
            (missing, 'in_stock'),
            (already, 'out'),
            (blank, 'in_stock'),
            (spaces, 'in_stock'),
            (dup_a, 'in_stock'),
            (dup_b, 'in_stock'),
            (in_feed, 'in_stock'),
            (feed_dup, 'in_stock'),
        ):
            product.refresh_from_db()
            self.assertEqual(product.stock_status, stock)
        self.assertEqual(in_feed.price, Decimal('3.00'))
        self.assertEqual(feed_dup.price, Decimal('8.00'))
        self.assertEqual(dup_a.price, Decimal('10.00'))
        self.assertEqual(dup_b.price, Decimal('11.00'))
        self.assertEqual(run.status, SupplierSyncRun.Status.OK)
        self.assertTrue(run.dry_run)
        self.assertEqual(run.marked_out, 1)
        self.assertIn('Стане «Немає в наявності»: 1', run.report)
        self.assertIn('- Зникне | NO-FEED', run.report)
        self.assertNotIn('- Вже немає | ALREADY-OUT', run.report)
        self.assertNotIn('- Дубль А | DUP', run.report)
        self.assertNotIn('- Дубль Б | dup', run.report)
        self.assertNotIn('- Конфлікт фіду | ZZ', run.report)
        self.assertNotIn('Без коду', run.report)
        self.assertEqual(run.report_json['mark_out_examples'], [
            {'name': 'Зникне', 'code': 'NO-FEED'},
        ])
        sql = ' '.join(query['sql'] for query in ctx.captured_queries)
        self.assertNotIn('UPDATE "products_product"', sql)
        self.assertNotIn('UPDATE products_product', sql)

    def test_apply_marks_missing_manufacturer_sku_and_skips_conflicts(self):
        missing = make_product(
            name='Зникне', slug='apply-gone', sku='APPLY-GONE',
            sku_manufacturer='NO-FEED', price=Decimal('10.00'),
            stock_status='in_stock',
        )
        blank = make_product(
            name='Без коду', slug='apply-blank', sku='APPLY-BLANK',
            sku_manufacturer='', price=Decimal('10.00'),
            stock_status='in_stock',
        )
        already = make_product(
            name='Вже немає', slug='apply-out', sku='APPLY-OUT',
            sku_manufacturer='ALREADY-OUT', stock_status='out',
            price=Decimal('10.00'),
        )
        dup_a = make_product(
            name='Дубль А', slug='apply-dup-a', sku='APPLY-DUP-A',
            sku_manufacturer='DUP', stock_status='in_stock',
            price=Decimal('10.00'),
        )
        dup_b = make_product(
            name='Дубль Б', slug='apply-dup-b', sku='APPLY-DUP-B',
            sku_manufacturer='dup', stock_status='in_stock',
            price=Decimal('11.00'),
        )
        feed_dup = make_product(
            name='Конфлікт фіду', slug='apply-feed-dup', sku='APPLY-FD',
            sku_manufacturer='ZZ', stock_status='in_stock',
            price=Decimal('8.00'),
        )
        run = sync_supplier(make_supplier(), source=feed_bytes([
            {'id': 'OTHER', 'price': '5 UAH', 'title': 'Інший'},
            {'id': 'ZZ', 'price': '30 UAH', 'title': 'Дубль'},
            {'id': 'zz', 'price': '31 UAH', 'title': 'Дубль 2'},
        ]))
        missing.refresh_from_db()
        blank.refresh_from_db()
        already.refresh_from_db()
        dup_a.refresh_from_db()
        dup_b.refresh_from_db()
        feed_dup.refresh_from_db()
        self.assertEqual(run.status, SupplierSyncRun.Status.OK)
        self.assertEqual(missing.stock_status, 'out')
        self.assertEqual(blank.stock_status, 'in_stock')
        self.assertEqual(already.stock_status, 'out')
        self.assertEqual(dup_a.stock_status, 'in_stock')
        self.assertEqual(dup_b.stock_status, 'in_stock')
        self.assertEqual(feed_dup.stock_status, 'in_stock')
        self.assertEqual(feed_dup.price, Decimal('8.00'))
        self.assertEqual(run.marked_out, 1)
        self.assertIn('Позначено «Немає в наявності»: 1', run.report)
