import io
from decimal import Decimal
from unittest.mock import patch

import requests
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from suppliers.models import SupplierSyncRun
from suppliers.services import sync_supplier

from .utils import FIXTURE, feed_bytes, make_product, make_supplier


class SyncSupplierTests(TestCase):
    def test_matches_manufacturer_sku_not_shop_sku(self):
        target = make_product(
            name='Купол',
            slug='kupol',
            sku='SHOP-1',
            sku_manufacturer='4812345001001',
            price=Decimal('10.00'),
            old_price=Decimal('999.00'),
        )
        decoy = make_product(
            name='Інший',
            slug='inshyi',
            sku='4812345001002',
            sku_manufacturer='OTHER',
            price=Decimal('10.00'),
            old_price=Decimal('50.00'),
        )
        spaced = make_product(
            name='Хрест',
            slug='hrest',
            sku='SHOP-2',
            sku_manufacturer=' 4812345001002 ',
            price=Decimal('10.00'),
            old_price=Decimal('80.00'),
        )
        supplier = make_supplier()
        run = sync_supplier(supplier, source=FIXTURE)

        target.refresh_from_db()
        decoy.refresh_from_db()
        spaced.refresh_from_db()
        self.assertEqual(run.status, SupplierSyncRun.Status.OK)
        self.assertEqual(target.price, Decimal('28630.00'))
        self.assertEqual(target.old_price, Decimal('999.00'))
        self.assertEqual(decoy.price, Decimal('10.00'))
        self.assertEqual(decoy.old_price, Decimal('50.00'))
        self.assertEqual(spaced.price, Decimal('28630.00'))
        self.assertEqual(spaced.old_price, Decimal('80.00'))
        self.assertGreaterEqual(run.matched, 2)
        self.assertIn('Купол', run.report)
        self.assertIn('10.00 → 28630.00', run.report)

    def test_casefold_match(self):
        product = make_product(
            slug='case', sku='C1', sku_manufacturer='AbC-1', price=Decimal('1.00'),
        )
        supplier = make_supplier()
        sync_supplier(supplier, source=feed_bytes([
            {'id': ' abc-1 ', 'price': '20 UAH', 'title': 'Регістр'},
        ]))
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('20.00'))

    def test_dry_run_does_not_write_products(self):
        product = make_product(
            slug='dry', sku='D1', sku_manufacturer='4812345001001', price=Decimal('10.00'),
        )
        supplier = make_supplier()
        with CaptureQueriesContext(connection) as ctx:
            run = sync_supplier(supplier, dry_run=True, source=FIXTURE)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('10.00'))
        self.assertEqual(run.status, SupplierSyncRun.Status.OK)
        self.assertTrue(run.dry_run)
        self.assertGreater(run.price_changed, 0)
        sql = ' '.join(query['sql'] for query in ctx.captured_queries)
        self.assertNotIn('UPDATE "products_product"', sql)
        self.assertNotIn('UPDATE products_product', sql)

    def test_markup_and_rounding_on_apply(self):
        product = make_product(
            slug='mark', sku='M1', sku_manufacturer='4812345001001',
            price=Decimal('1.00'), old_price=Decimal('5.00'),
        )
        supplier = make_supplier(
            price_rule='markup',
            markup_percent=Decimal('10'),
            rounding='10',
        )
        sync_supplier(supplier, source=FIXTURE)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('31490.00'))
        self.assertEqual(product.old_price, Decimal('5.00'))

    def test_update_price_off_keeps_price(self):
        product = make_product(
            slug='keep', sku='K1', sku_manufacturer='4812345001001', price=Decimal('10.00'),
        )
        supplier = make_supplier(update_price=False)
        run = sync_supplier(supplier, source=FIXTURE)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('10.00'))
        self.assertEqual(run.price_changed, 0)
        self.assertGreater(run.matched, 0)

    def test_missing_out_of_stock_only_with_flag(self):
        in_feed = make_product(
            name='У фіді', slug='in-feed', sku='IN',
            sku_manufacturer='4812345001003', price=Decimal('10.00'),
        )
        missing = make_product(
            name='Немає у фіді', slug='missing', sku='MISS',
            sku_manufacturer='NO-FEED', price=Decimal('10.00'),
        )
        blank = make_product(
            name='Без коду', slug='blank', sku='BLANK',
            sku_manufacturer='', price=Decimal('10.00'),
        )
        spaces = make_product(
            name='Пробіли', slug='spaces', sku='SPACES',
            sku_manufacturer='   ', price=Decimal('10.00'),
        )
        already = make_product(
            name='Вже немає', slug='already', sku='OUT',
            sku_manufacturer='ALREADY-OUT', stock_status='out',
        )
        supplier = make_supplier(mark_missing_out_of_stock=False)
        off = sync_supplier(supplier, source=FIXTURE)
        missing.refresh_from_db()
        self.assertEqual(missing.stock_status, 'in_stock')
        self.assertEqual(off.marked_out, 0)
        self.assertGreater(off.not_in_feed, 0)

        supplier.mark_missing_out_of_stock = True
        supplier.save(update_fields=['mark_missing_out_of_stock'])
        on = sync_supplier(supplier, source=FIXTURE)
        in_feed.refresh_from_db()
        missing.refresh_from_db()
        blank.refresh_from_db()
        spaces.refresh_from_db()
        already.refresh_from_db()
        self.assertEqual(in_feed.stock_status, 'in_stock')
        self.assertEqual(missing.stock_status, 'out')
        self.assertEqual(blank.stock_status, 'in_stock')
        self.assertEqual(spaces.stock_status, 'in_stock')
        self.assertEqual(already.stock_status, 'out')
        self.assertEqual(on.marked_out, 1)
        self.assertIn('Немає у фіді', on.report)

    def test_feed_availability_does_not_change_stock(self):
        product = make_product(
            slug='avail', sku='AV', sku_manufacturer='4812345001003',
            stock_status='in_stock', price=Decimal('28630.50'),
        )
        sync_supplier(make_supplier(), source=FIXTURE)
        product.refresh_from_db()
        self.assertEqual(product.stock_status, 'in_stock')

    def test_duplicate_codes_are_not_updated(self):
        first = make_product(
            name='Перший', slug='dup-1', sku='DUP1',
            sku_manufacturer='Same', price=Decimal('10.00'),
        )
        second = make_product(
            name='Другий', slug='dup-2', sku='DUP2',
            sku_manufacturer='same', price=Decimal('12.00'),
        )
        single = make_product(
            name='Один', slug='single', sku='ONE',
            sku_manufacturer='ONLY', price=Decimal('3.00'),
        )
        run = sync_supplier(make_supplier(), source=feed_bytes([
            {'id': 'SAME', 'price': '40 UAH', 'title': 'Дубль'},
            {'id': 'same', 'price': '41 UAH', 'title': 'Дубль 2'},
            {'id': 'ONLY', 'price': '7 UAH', 'title': 'Нормальний'},
        ]))
        first.refresh_from_db()
        second.refresh_from_db()
        single.refresh_from_db()
        self.assertEqual(first.price, Decimal('10.00'))
        self.assertEqual(second.price, Decimal('12.00'))
        self.assertEqual(single.price, Decimal('7.00'))
        self.assertEqual(run.status, SupplierSyncRun.Status.OK)
        self.assertIn('Конфлікт', run.report)

    def test_duplicate_catalog_codes_are_not_marked_out(self):
        first = make_product(
            slug='cat-dup-1', sku='CD1', sku_manufacturer='DUP', stock_status='in_stock',
        )
        second = make_product(
            slug='cat-dup-2', sku='CD2', sku_manufacturer='dup', stock_status='in_stock',
        )
        supplier = make_supplier(mark_missing_out_of_stock=True)
        run = sync_supplier(supplier, source=feed_bytes([
            {'id': 'OTHER', 'price': '5 UAH', 'title': 'Інший'},
        ]))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.stock_status, 'in_stock')
        self.assertEqual(second.stock_status, 'in_stock')
        self.assertEqual(run.marked_out, 0)
        self.assertEqual(run.status, SupplierSyncRun.Status.OK)
        self.assertIn('каталозі', run.report)

    def test_duplicate_feed_id_does_not_update(self):
        product = make_product(
            slug='feed-dup', sku='FD', sku_manufacturer='ZZ', price=Decimal('8.00'),
        )
        run = sync_supplier(make_supplier(), source=feed_bytes([
            {'id': 'ZZ', 'price': '30 UAH'},
            {'id': 'zz', 'price': '31 UAH'},
        ]))
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('8.00'))
        self.assertIn('у фіді', run.report)

    def test_invalid_price_is_skipped_and_valid_sibling_applies(self):
        good = make_product(slug='good', sku='GOOD', sku_manufacturer='GOOD', price=Decimal('1.00'))
        bad = make_product(slug='bad', sku='BAD', sku_manufacturer='BAD', price=Decimal('2.00'))
        run = sync_supplier(make_supplier(), source=feed_bytes([
            {'id': 'GOOD', 'price': '19 UAH', 'title': 'Добрий'},
            {'id': 'BAD', 'price': '19 USD', 'title': 'Чужий'},
        ]))
        good.refresh_from_db()
        bad.refresh_from_db()
        self.assertEqual(good.price, Decimal('19.00'))
        self.assertEqual(bad.price, Decimal('2.00'))
        self.assertEqual(run.status, SupplierSyncRun.Status.OK)
        self.assertGreater(run.errors, 0)
        self.assertIn('USD', run.report)

    def test_empty_feed_fails_closed(self):
        product = make_product(
            slug='empty', sku='EMP', sku_manufacturer='KEEP',
            price=Decimal('15.00'), stock_status='in_stock',
        )
        supplier = make_supplier(mark_missing_out_of_stock=True)
        empty = io.BytesIO(
            b'<?xml version="1.0"?><rss version="2.0" '
            b'xmlns:g="http://base.google.com/ns/1.0"><channel></channel></rss>'
        )
        run = sync_supplier(supplier, source=empty)
        product.refresh_from_db()
        self.assertEqual(run.status, SupplierSyncRun.Status.FAILED)
        self.assertEqual(run.marked_out, 0)
        self.assertEqual(run.price_changed, 0)
        self.assertEqual(product.price, Decimal('15.00'))
        self.assertEqual(product.stock_status, 'in_stock')

    def test_all_invalid_rows_fail_closed(self):
        product = make_product(
            slug='all-bad', sku='AB', sku_manufacturer='X',
            price=Decimal('4.00'), stock_status='in_stock',
        )
        supplier = make_supplier(mark_missing_out_of_stock=True)
        run = sync_supplier(supplier, source=feed_bytes([
            {'id': 'X', 'price': '5 EUR'},
        ]))
        product.refresh_from_db()
        self.assertEqual(run.status, SupplierSyncRun.Status.FAILED)
        self.assertEqual(product.stock_status, 'in_stock')
        self.assertEqual(product.price, Decimal('4.00'))

    def test_broken_xml_and_bad_url_do_not_write(self):
        product = make_product(slug='broken', sku='BR', sku_manufacturer='4812345001001', price=Decimal('6.00'))
        supplier = make_supplier()
        broken = sync_supplier(supplier, source=io.BytesIO(b'<rss><item></channel>'))
        product.refresh_from_db()
        self.assertEqual(broken.status, SupplierSyncRun.Status.FAILED)
        self.assertEqual(product.price, Decimal('6.00'))

        supplier.feed_url = 'ftp://example.com/feed.xml'
        supplier.save(update_fields=['feed_url'])
        with patch('suppliers.fetch.requests.get') as get:
            failed = sync_supplier(supplier)
        get.assert_not_called()
        product.refresh_from_db()
        self.assertEqual(failed.status, SupplierSyncRun.Status.FAILED)
        self.assertEqual(product.price, Decimal('6.00'))

    def test_fetch_sends_user_agent_without_leaking_url(self):
        make_product(slug='net', sku='NET', sku_manufacturer='4812345001001', price=Decimal('1.00'))
        supplier = make_supplier(feed_url='https://secret.example/feed.xml?token=abc')
        response = io.BytesIO(FIXTURE.read_bytes())
        fake = type('Resp', (), {})()
        fake.raw = response
        fake.raise_for_status = lambda: None
        fake.close = lambda: None
        with patch('suppliers.fetch.requests.get', return_value=fake) as get:
            run = sync_supplier(supplier, dry_run=True)
        self.assertEqual(run.status, SupplierSyncRun.Status.OK)
        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs['headers']['User-Agent'], 'OfionSupplierSync/1.0')
        self.assertEqual(kwargs['timeout'], (10, 60))
        self.assertTrue(kwargs['stream'])

        with patch(
            'suppliers.fetch.requests.get',
            side_effect=requests.ConnectionError('https://secret.example/feed.xml?token=abc'),
        ):
            failed = sync_supplier(supplier)
        self.assertEqual(failed.status, SupplierSyncRun.Status.FAILED)
        self.assertNotIn('secret.example', failed.report)
        self.assertNotIn('token=abc', failed.report)

    def test_apply_failure_rolls_back(self):
        product = make_product(
            slug='roll', sku='ROLL', sku_manufacturer='4812345001001', price=Decimal('9.00'),
        )
        with patch('suppliers.services.Product.objects.bulk_update', side_effect=RuntimeError('db')):
            run = sync_supplier(make_supplier(), source=FIXTURE)
        product.refresh_from_db()
        self.assertEqual(run.status, SupplierSyncRun.Status.FAILED)
        self.assertEqual(product.price, Decimal('9.00'))

    def test_not_in_catalog_is_reported(self):
        run = sync_supplier(make_supplier(), source=feed_bytes([
            {'id': 'NEW-1', 'price': '12.50 UAH', 'title': 'Новий купол'},
        ]))
        self.assertEqual(run.not_in_catalog, 1)
        self.assertEqual(run.matched, 0)
        self.assertIn('Новий купол', run.report)
        self.assertEqual(run.report_json['not_in_catalog_examples'][0]['code'], 'NEW-1')
