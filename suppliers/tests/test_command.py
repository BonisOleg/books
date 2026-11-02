import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from suppliers.models import SupplierSyncRun

from .utils import FIXTURE, make_product, make_supplier


class SyncCommandTests(TestCase):
    def test_dry_run_prints_examples_and_skips_inactive(self):
        product = make_product(
            name='Купол церковний малий',
            slug='cmd', sku='CMD', sku_manufacturer='4812345001001',
            price=Decimal('10.00'),
        )
        active = make_supplier(name='Активний')
        make_supplier(name='Вимкнений', is_active=False, feed_url='https://example.com/other.xml')
        out = StringIO()
        call_command(
            'sync_supplier_feeds',
            '--dry-run',
            '--file', str(FIXTURE),
            stdout=out,
        )
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('10.00'))
        text = out.getvalue()
        self.assertIn('Активний', text)
        self.assertNotIn('Вимкнений', text)
        self.assertIn('10.00 → 28630.00', text)
        self.assertIn('Купол церковний малий', text)
        self.assertEqual(SupplierSyncRun.objects.count(), 1)
        self.assertTrue(SupplierSyncRun.objects.get().dry_run)
        self.assertEqual(SupplierSyncRun.objects.get().supplier_id, active.pk)

    def test_supplier_id_runs_even_if_inactive(self):
        product = make_product(
            slug='inactive', sku='INA', sku_manufacturer='4812345001001', price=Decimal('3.00'),
        )
        supplier = make_supplier(is_active=False)
        out = StringIO()
        call_command(
            'sync_supplier_feeds',
            '--supplier', str(supplier.pk),
            '--file', str(FIXTURE),
            stdout=out,
        )
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('28630.00'))
        self.assertIn(supplier.name, out.getvalue())

    def test_missing_supplier_and_file(self):
        with self.assertRaises(CommandError):
            call_command('sync_supplier_feeds', '--supplier', '99999')
        with self.assertRaises(CommandError):
            call_command('sync_supplier_feeds', '--file', '/tmp/ofion-no-such-feed.xml')
        self.assertEqual(SupplierSyncRun.objects.count(), 0)

    def test_empty_feed_exits_with_error_and_keeps_stock(self):
        product = make_product(
            slug='cmd-empty', sku='CE', sku_manufacturer='KEEP',
            price=Decimal('8.00'), stock_status='in_stock',
        )
        supplier = make_supplier(mark_missing_out_of_stock=True)
        with tempfile.TemporaryDirectory() as folder:
            empty = Path(folder) / 'empty.xml'
            empty.write_text(
                '<?xml version="1.0"?><rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">'
                '<channel></channel></rss>',
                encoding='utf-8',
            )
            with self.assertRaises(CommandError):
                call_command(
                    'sync_supplier_feeds',
                    '--supplier', str(supplier.pk),
                    '--file', str(empty),
                )
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('8.00'))
        self.assertEqual(product.stock_status, 'in_stock')
        self.assertEqual(SupplierSyncRun.objects.get().status, SupplierSyncRun.Status.FAILED)

    def test_no_active_suppliers(self):
        make_supplier(is_active=False)
        out = StringIO()
        call_command('sync_supplier_feeds', stdout=out)
        self.assertIn('Немає активних', out.getvalue())
        self.assertEqual(SupplierSyncRun.objects.count(), 0)
