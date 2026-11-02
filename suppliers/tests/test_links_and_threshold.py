from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from suppliers.models import PendingPriceChange, SupplierProduct
from suppliers.report import money
from suppliers.services import sync_supplier

from .utils import feed_bytes, make_link, make_product, make_supplier

User = get_user_model()


class MoneyFormatTests(TestCase):
    def test_groups_hryvnias_with_kopecks(self):
        self.assertEqual(money(Decimal('11020')), '11 020,00 грн')
        self.assertEqual(money(Decimal('10')), '10,00 грн')
        self.assertEqual(money(Decimal('28630')), '28 630,00 грн')
        self.assertEqual(money(Decimal('12.5')), '12,50 грн')


class AutoLinkTests(TestCase):
    def test_first_match_links_and_second_sync_does_not_duplicate(self):
        product = make_product(
            slug='link-1', sku='LINK-1', sku_manufacturer='LINK-1',
            price=Decimal('100.00'),
        )
        supplier = make_supplier()
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'LINK-1', 'price': '110 UAH', 'title': 'Купол'},
        ]))
        link = SupplierProduct.objects.get()
        self.assertEqual(link.supplier, supplier)
        self.assertEqual(link.product, product)
        self.assertEqual(link.feed_code, 'LINK-1')
        self.assertIsNotNone(link.linked_at)
        self.assertIsNotNone(link.last_seen_at)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('110.00'))

        past = timezone.now() - timedelta(days=2)
        link.last_seen_at = past
        link.save(update_fields=['last_seen_at'])
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'LINK-1', 'price': '110 UAH', 'title': 'Купол'},
        ]))
        self.assertEqual(SupplierProduct.objects.count(), 1)
        link.refresh_from_db()
        self.assertGreater(link.last_seen_at, past)

    def test_other_supplier_is_reported_and_not_touched(self):
        product = make_product(
            slug='owned', sku='OWN', sku_manufacturer='OWN',
            price=Decimal('100.00'), stock_status='in_stock',
        )
        owner = make_supplier(name='Власник', feed_url='https://example.com/owner.xml')
        stranger = make_supplier(name='Чужий', feed_url='https://example.com/stranger.xml')
        make_link(owner, product, feed_code='OWN')
        run = sync_supplier(stranger, source=feed_bytes([
            {'id': 'OWN', 'price': '110 UAH', 'title': 'Чужий фід'},
        ]))
        product.refresh_from_db()
        link = SupplierProduct.objects.get()
        self.assertEqual(product.price, Decimal('100.00'))
        self.assertEqual(product.stock_status, 'in_stock')
        self.assertEqual(link.supplier, owner)
        self.assertFalse(link.ignored)
        self.assertEqual(run.matched, 0)
        self.assertIn('Конфлікт', run.report)
        self.assertIn('Власник', run.report)
        self.assertEqual(PendingPriceChange.objects.count(), 0)

    def test_duplicate_catalog_code_is_not_linked(self):
        make_product(slug='dup-a', sku='DUP-A', sku_manufacturer='SAME', price=Decimal('10.00'))
        make_product(slug='dup-b', sku='DUP-B', sku_manufacturer='same', price=Decimal('11.00'))
        sync_supplier(make_supplier(), source=feed_bytes([
            {'id': 'SAME', 'price': '40 UAH', 'title': 'Дубль'},
        ]))
        self.assertEqual(SupplierProduct.objects.count(), 0)


class StockLinkTests(TestCase):
    def test_unlinked_product_is_never_marked_out(self):
        loose = make_product(
            slug='loose-stock', sku='LOOSE-ST', sku_manufacturer='LOOSE-ST',
            price=Decimal('15.00'), stock_status='in_stock',
        )
        linked = make_product(
            slug='linked-stock', sku='LINK-ST', sku_manufacturer='LINK-ST',
            price=Decimal('15.00'), stock_status='in_stock',
        )
        supplier = make_supplier()
        make_link(supplier, linked)
        run = sync_supplier(supplier, source=feed_bytes([
            {'id': 'OTHER', 'price': '5 UAH', 'title': 'Інший'},
        ]))
        loose.refresh_from_db()
        linked.refresh_from_db()
        self.assertEqual(loose.stock_status, 'in_stock')
        self.assertEqual(loose.price, Decimal('15.00'))
        self.assertFalse(SupplierProduct.objects.filter(product=loose).exists())
        self.assertEqual(linked.stock_status, 'out')
        self.assertTrue(SupplierProduct.objects.get(product=linked).marked_out_by_sync)
        self.assertEqual(run.marked_out, 1)

    def test_reappearing_product_returns_to_stock_only_if_sync_marked_it(self):
        product = make_product(
            slug='back', sku='BACK', sku_manufacturer='BACK',
            price=Decimal('50.00'), stock_status='out',
        )
        supplier = make_supplier()
        link = make_link(supplier, product, marked_out_by_sync=True)
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'BACK', 'price': '50 UAH', 'title': 'Знову'},
        ]))
        product.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(product.stock_status, 'in_stock')
        self.assertFalse(link.marked_out_by_sync)

    def test_manual_out_is_not_restored(self):
        product = make_product(
            slug='manual-out', sku='MAN', sku_manufacturer='MAN',
            price=Decimal('50.00'), stock_status='out',
        )
        supplier = make_supplier()
        link = make_link(supplier, product, marked_out_by_sync=False)
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'MAN', 'price': '50 UAH', 'title': 'Ручне'},
        ]))
        product.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(product.stock_status, 'out')
        self.assertFalse(link.marked_out_by_sync)

    def test_ignored_skips_price_and_stock(self):
        priced = make_product(
            slug='ign-price', sku='IGN-P', sku_manufacturer='IGN-P',
            price=Decimal('100.00'), stock_status='in_stock',
        )
        absent = make_product(
            slug='ign-miss', sku='IGN-A', sku_manufacturer='IGN-A',
            price=Decimal('40.00'), stock_status='in_stock',
        )
        supplier = make_supplier(max_price_change_percent=Decimal('0'))
        make_link(supplier, priced, ignored=True)
        make_link(supplier, absent, ignored=True)
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'IGN-P', 'price': '10 UAH', 'title': 'Дешевше'},
        ]))
        priced.refresh_from_db()
        absent.refresh_from_db()
        self.assertEqual(priced.price, Decimal('100.00'))
        self.assertEqual(priced.stock_status, 'in_stock')
        self.assertEqual(absent.stock_status, 'in_stock')
        self.assertFalse(SupplierProduct.objects.get(product=absent).marked_out_by_sync)
        self.assertEqual(PendingPriceChange.objects.count(), 0)


class ThresholdTests(TestCase):
    def test_over_thirty_percent_waits_and_within_is_applied(self):
        quiet = make_product(
            slug='quiet', sku='QUIET', sku_manufacturer='QUIET', price=Decimal('100.00'),
        )
        down = make_product(
            slug='down', sku='DOWN', sku_manufacturer='DOWN', price=Decimal('200.00'),
        )
        loud = make_product(
            slug='loud', sku='LOUD', sku_manufacturer='LOUD', price=Decimal('100.00'),
        )
        supplier = make_supplier(max_price_change_percent=Decimal('30'))
        run = sync_supplier(supplier, source=feed_bytes([
            {'id': 'QUIET', 'price': '130 UAH', 'title': 'Рівно 30'},
            {'id': 'DOWN', 'price': '140 UAH', 'title': 'Мінус 30'},
            {'id': 'LOUD', 'price': '160 UAH', 'title': 'Понад'},
        ]))
        quiet.refresh_from_db()
        down.refresh_from_db()
        loud.refresh_from_db()
        self.assertEqual(quiet.price, Decimal('130.00'))
        self.assertEqual(down.price, Decimal('140.00'))
        self.assertEqual(loud.price, Decimal('100.00'))
        self.assertTrue(SupplierProduct.objects.filter(product=loud, supplier=supplier).exists())
        pending = PendingPriceChange.objects.get()
        self.assertEqual(pending.product, loud)
        self.assertEqual(pending.old_price, Decimal('100.00'))
        self.assertEqual(pending.new_price, Decimal('160.00'))
        self.assertEqual(pending.percent, Decimal('60.00'))
        self.assertEqual(pending.status, PendingPriceChange.Status.PENDING)
        self.assertEqual(pending.run_id, run.pk)
        self.assertIn('Застосовуються автоматично: 2', run.report)
        self.assertIn('Потребують підтвердження: 1', run.report)
        self.assertIn('60,00%', run.report)
        self.assertIn('160,00 грн', run.report)

    def test_repeat_sync_updates_the_same_pending_row(self):
        product = make_product(
            slug='again', sku='AGAIN', sku_manufacturer='AGAIN', price=Decimal('100.00'),
        )
        supplier = make_supplier(max_price_change_percent=Decimal('30'))
        source = feed_bytes([{'id': 'AGAIN', 'price': '160 UAH', 'title': 'Перша'}])
        sync_supplier(supplier, source=source)
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'AGAIN', 'price': '180 UAH', 'title': 'Друга'},
        ]))
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('100.00'))
        self.assertEqual(PendingPriceChange.objects.count(), 1)
        pending = PendingPriceChange.objects.get()
        self.assertEqual(pending.new_price, Decimal('180.00'))
        self.assertEqual(pending.old_price, Decimal('100.00'))
        self.assertEqual(pending.percent, Decimal('80.00'))
        self.assertEqual(pending.status, PendingPriceChange.Status.PENDING)

    def test_pending_goes_away_when_feed_price_is_back_in_range(self):
        product = make_product(
            slug='settle', sku='SETTLE', sku_manufacturer='SETTLE', price=Decimal('100.00'),
        )
        supplier = make_supplier(max_price_change_percent=Decimal('30'))
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'SETTLE', 'price': '160 UAH', 'title': 'Стрибок'},
        ]))
        self.assertEqual(PendingPriceChange.objects.count(), 1)
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'SETTLE', 'price': '100 UAH', 'title': 'Як було'},
        ]))
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('100.00'))
        self.assertEqual(PendingPriceChange.objects.count(), 0)
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'SETTLE', 'price': '120 UAH', 'title': 'В межах'},
        ]))
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('120.00'))
        self.assertEqual(PendingPriceChange.objects.count(), 0)

    def test_zero_threshold_applies_a_large_change(self):
        product = make_product(
            slug='open', sku='OPEN', sku_manufacturer='OPEN', price=Decimal('10.00'),
        )
        supplier = make_supplier(max_price_change_percent=Decimal('0'))
        sync_supplier(supplier, source=feed_bytes([
            {'id': 'OPEN', 'price': '1000 UAH', 'title': 'Стрибок'},
        ]))
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('1000.00'))
        self.assertEqual(PendingPriceChange.objects.count(), 0)


class DryRunWriteTests(TestCase):
    def test_dry_run_counts_links_stock_and_pending_without_writing(self):
        supplier = make_supplier(max_price_change_percent=Decimal('30'))
        fresh = make_product(
            name='Новий звʼязок', slug='dry-fresh', sku='DRY-F',
            sku_manufacturer='FRESH', price=Decimal('100.00'),
        )
        missing = make_product(
            name='Зникне', slug='dry-miss', sku='DRY-M',
            sku_manufacturer='MISS', price=Decimal('10.00'), stock_status='in_stock',
        )
        back = make_product(
            name='Повернеться', slug='dry-back', sku='DRY-B',
            sku_manufacturer='BACK', price=Decimal('10.00'), stock_status='out',
        )
        loose = make_product(
            name='Вільний', slug='dry-loose', sku='DRY-L',
            sku_manufacturer='LOOSE', price=Decimal('10.00'), stock_status='in_stock',
        )
        make_link(supplier, missing)
        make_link(supplier, back, marked_out_by_sync=True)
        links_before = SupplierProduct.objects.count()
        with CaptureQueriesContext(connection) as ctx:
            run = sync_supplier(supplier, dry_run=True, source=feed_bytes([
                {'id': 'FRESH', 'price': '200 UAH', 'title': 'Новий звʼязок'},
                {'id': 'BACK', 'price': '10 UAH', 'title': 'Повернеться'},
            ]))
        fresh.refresh_from_db()
        missing.refresh_from_db()
        back.refresh_from_db()
        loose.refresh_from_db()
        self.assertEqual(fresh.price, Decimal('100.00'))
        self.assertEqual(fresh.stock_status, 'in_stock')
        self.assertEqual(missing.stock_status, 'in_stock')
        self.assertEqual(back.stock_status, 'out')
        self.assertEqual(loose.stock_status, 'in_stock')
        self.assertEqual(loose.price, Decimal('10.00'))
        self.assertEqual(SupplierProduct.objects.count(), links_before)
        self.assertFalse(SupplierProduct.objects.filter(product=fresh).exists())
        self.assertFalse(SupplierProduct.objects.filter(product=loose).exists())
        self.assertEqual(PendingPriceChange.objects.count(), 0)
        self.assertTrue(run.dry_run)
        self.assertIn('Стане «Немає в наявності»: 1', run.report)
        self.assertIn('Повернеться в наявність: 1', run.report)
        self.assertIn("Буде прив'язано: 1", run.report)
        self.assertIn('Потребують підтвердження: 1', run.report)
        self.assertIn('100,00%', run.report)
        sql = ' '.join(query['sql'] for query in ctx.captured_queries)
        self.assertNotIn('UPDATE "products_product"', sql)
        self.assertNotIn('UPDATE products_product', sql)
        self.assertNotIn('INSERT INTO "suppliers_supplierproduct"', sql)
        self.assertNotIn('INSERT INTO "suppliers_pendingpricechange"', sql)


class PendingAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('price-admin', 'price@example.com', 'pass')
        self.client.force_login(self.admin)
        self.supplier = make_supplier(max_price_change_percent=Decimal('30'))
        self.product = make_product(
            name='Купол на підтвердженні',
            slug='pending-admin',
            sku='PEND',
            sku_manufacturer='PEND',
            price=Decimal('100.00'),
            stock_status='in_stock',
        )

    def _pending(self, **kwargs):
        data = {
            'supplier': self.supplier,
            'product': self.product,
            'old_price': Decimal('100.00'),
            'new_price': Decimal('150.00'),
            'percent': Decimal('50.00'),
        }
        data.update(kwargs)
        return PendingPriceChange.objects.create(**data)

    def test_apply_action_sets_price_when_old_matches(self):
        pending = self._pending()
        response = self.client.post(
            reverse('admin:suppliers_pendingpricechange_changelist'),
            {'action': 'apply_pending', '_selected_action': [str(pending.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('150.00'))
        self.assertEqual(pending.status, PendingPriceChange.Status.APPLIED)
        self.assertEqual(pending.resolved_by, self.admin)
        self.assertIsNotNone(pending.resolved_at)
        self.assertContains(response, 'Застосовано змін цін: 1')

    def test_apply_action_refuses_when_price_changed(self):
        pending = self._pending()
        self.product.price = Decimal('110.00')
        self.product.save(update_fields=['price'])
        response = self.client.post(
            reverse('admin:suppliers_pendingpricechange_changelist'),
            {'action': 'apply_pending', '_selected_action': [str(pending.pk)]},
            follow=True,
        )
        self.product.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('110.00'))
        self.assertEqual(pending.status, PendingPriceChange.Status.PENDING)
        self.assertContains(response, 'не застосовано')
        self.assertContains(response, '110,00 грн')
        self.assertContains(response, '100,00 грн')

    def test_ignore_action_blocks_later_price_and_stock(self):
        pending = self._pending()
        response = self.client.post(
            reverse('admin:suppliers_pendingpricechange_changelist'),
            {'action': 'ignore_product', '_selected_action': [str(pending.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        link = SupplierProduct.objects.get(product=self.product)
        self.assertEqual(pending.status, PendingPriceChange.Status.IGNORED)
        self.assertEqual(pending.resolved_by, self.admin)
        self.assertTrue(link.ignored)
        self.assertEqual(link.supplier, self.supplier)
        self.supplier.max_price_change_percent = Decimal('0')
        self.supplier.save(update_fields=['max_price_change_percent'])
        sync_supplier(self.supplier, source=feed_bytes([
            {'id': 'PEND', 'price': '20 UAH', 'title': 'Дешевше'},
        ]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('100.00'))
        sync_supplier(self.supplier, source=feed_bytes([
            {'id': 'OTHER', 'price': '5 UAH', 'title': 'Інший'},
        ]))
        self.product.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(self.product.stock_status, 'in_stock')
        self.assertTrue(link.ignored)
        self.assertFalse(link.marked_out_by_sync)

    def test_supplier_page_shows_readonly_link_list(self):
        make_link(self.supplier, self.product, feed_code='PEND')
        response = self.client.get(
            reverse('admin:suppliers_supplier_change', args=[self.supplier.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Купол на підтвердженні')
        self.assertContains(response, 'PEND')
        self.assertContains(response, 'Ігнорувати цей товар')
