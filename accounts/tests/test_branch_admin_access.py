"""Доступ менеджерів до ТТН, постачальників, фільтрів і груп меню."""
import importlib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse

_groups = importlib.import_module('accounts.migrations.0002_manager_groups')
GROUP_ORDERS = _groups.GROUP_ORDERS
GROUP_PRODUCTS = _groups.GROUP_PRODUCTS
from orders.models import Order
from products.models import Product
from shipping.tests.factories import order, origin, route_np, ttn_settings
from suppliers.models import PendingPriceChange, Supplier, SupplierSyncRun

User = get_user_model()


def _staff(username, group_name=None):
    user = User.objects.create_user(username, password='pass-12345', is_staff=True)
    if group_name:
        user.groups.add(Group.objects.get(name=group_name))
    return user


def _product():
    return Product.objects.create(
        name='Рольовий товар',
        slug='rolovyi-tovar-branch',
        sku='ROLE-BRANCH',
        description='<p>Опис</p>',
        price='80.00',
    )


@override_settings(NOVAPOSHTA_API_KEY='np-test-key')
class BranchAdminAccessTests(TestCase):
    def setUp(self):
        self.catalog = _staff('branch-catalog', GROUP_PRODUCTS)
        self.orders = _staff('branch-orders', GROUP_ORDERS)
        self.bare = _staff('branch-bare')
        self.product = _product()
        self.origin = origin()
        ttn_settings()
        self.order_row = order(shipment_origin=self.origin)
        self.supplier = Supplier.objects.create(
            name='Фід',
            feed_url='https://example.com/feed.xml',
        )
        self.pending = PendingPriceChange.objects.create(
            supplier=self.supplier,
            product=self.product,
            old_price='80.00',
            new_price='120.00',
            percent='50.00',
        )

    def _ttn_url(self, row=None):
        row = row or self.order_row
        return reverse('admin:orders_order_create_ttn', args=[row.pk])

    def test_product_manager_cannot_run_suppliers_or_create_ttn(self):
        self.client.force_login(self.catalog)
        sync = self.client.post(
            reverse('admin:suppliers_supplier_sync', args=[self.supplier.pk]),
        )
        dry = self.client.post(
            reverse('admin:suppliers_supplier_dry_run', args=[self.supplier.pk]),
        )
        self.assertEqual(sync.status_code, 403)
        self.assertEqual(dry.status_code, 403)
        self.assertEqual(SupplierSyncRun.objects.count(), 0)
        action = self.client.post(reverse('admin:suppliers_supplier_changelist'), {
            'action': 'dry_run_selected',
            '_selected_action': [str(self.supplier.pk)],
        })
        self.assertEqual(action.status_code, 403)
        pending = self.client.post(
            reverse('admin:suppliers_pendingpricechange_changelist'),
            {'action': 'apply_pending', '_selected_action': [str(self.pending.pk)]},
        )
        self.assertEqual(pending.status_code, 403)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, PendingPriceChange.Status.PENDING)
        ttn = self.client.post(self._ttn_url())
        self.assertEqual(ttn.status_code, 403)
        self.order_row.refresh_from_db()
        self.assertEqual(self.order_row.ttn_number, '')

    def test_order_manager_can_create_ttn(self):
        self.client.force_login(self.orders)
        with patch('shipping.np_ttn.requests.post', side_effect=route_np()):
            response = self.client.post(self._ttn_url(), follow=True)
        self.order_row.refresh_from_db()
        self.assertEqual(self.order_row.ttn_number, '20450123456789')
        self.assertContains(response, 'ТТН 20450123456789 створено')
        page = self.client.get(reverse('admin:orders_order_change', args=[self.order_row.pk]))
        self.assertContains(page, 'Створити ТТН')

    def test_order_manager_bulk_ttn_and_catalog_manager_is_forbidden(self):
        fresh = order(shipment_origin=self.origin, first_name='Марко')
        self.client.force_login(self.catalog)
        denied = self.client.post(reverse('admin:orders_order_changelist'), {
            'action': 'create_ttn_for_selected',
            '_selected_action': [str(fresh.pk)],
        })
        self.assertEqual(denied.status_code, 403)
        fresh.refresh_from_db()
        self.assertEqual(fresh.ttn_number, '')

        self.client.force_login(self.orders)
        with patch('shipping.np_ttn.requests.post', side_effect=route_np()):
            allowed = self.client.post(reverse('admin:orders_order_changelist'), {
                'action': 'create_ttn_for_selected',
                '_selected_action': [str(fresh.pk)],
            }, follow=True)
        self.assertEqual(allowed.status_code, 200)
        fresh.refresh_from_db()
        self.assertEqual(fresh.ttn_number, '20450123456789')

    def test_anonymous_redirects_and_staff_without_rights_is_forbidden(self):
        anonymous = self.client.post(self._ttn_url())
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn('/admin/login/', anonymous.url)
        supplier = self.client.post(
            reverse('admin:suppliers_supplier_dry_run', args=[self.supplier.pk]),
        )
        self.assertEqual(supplier.status_code, 302)
        self.assertIn('/admin/login/', supplier.url)

        self.client.force_login(self.bare)
        self.assertEqual(self.client.post(self._ttn_url()).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse('admin:suppliers_supplier_sync', args=[self.supplier.pk]),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('admin:products_productgroup_changelist')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('admin:products_consultationrequest_changelist'),
            ).status_code,
            403,
        )
        self.assertEqual(SupplierSyncRun.objects.count(), 0)
        self.order_row.refresh_from_db()
        self.assertEqual(self.order_row.ttn_number, '')

    def test_catalog_sections_follow_the_groups(self):
        catalog_urls = [
            reverse('admin:products_productgroup_changelist'),
            reverse('admin:products_filterattribute_changelist'),
        ]
        order_urls = [
            reverse('admin:products_consultationrequest_changelist'),
            reverse('admin:shipping_shipmentorigin_changelist'),
        ]
        self.client.force_login(self.catalog)
        for url in catalog_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        for url in order_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('admin:shipping_npttnsettings_changelist')).status_code,
            403,
        )
        filters = self.client.post(reverse('admin:products_product_changelist'), {
            'action': 'add_filter_values_action',
            '_selected_action': [str(self.product.pk)],
        })
        self.assertEqual(filters.status_code, 200)
        self.assertContains(filters, 'Підтвердити')

        self.client.force_login(self.orders)
        for url in catalog_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        for url in order_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        settings_page = self.client.get(reverse('admin:shipping_npttnsettings_changelist'))
        self.assertEqual(settings_page.status_code, 302)
        opened = self.client.get(settings_page.url)
        self.assertEqual(opened.status_code, 200)
        denied_filters = self.client.post(reverse('admin:products_product_changelist'), {
            'action': 'add_filter_values_action',
            '_selected_action': [str(self.product.pk)],
        })
        self.assertEqual(denied_filters.status_code, 403)
        denied_sync = self.client.post(
            reverse('admin:suppliers_supplier_dry_run', args=[self.supplier.pk]),
        )
        self.assertEqual(denied_sync.status_code, 403)


class ViewOnlyTtnButtonTests(TestCase):
    def test_view_only_order_page_hides_ttn_button(self):
        user = _staff('branch-view-order')
        perm = Permission.objects.get(
            codename='view_order',
            content_type__app_label='orders',
            content_type__model='order',
        )
        user.user_permissions.add(perm)
        row = Order.objects.create(
            first_name='Іра',
            last_name='Савчук',
            phone='+380501110000',
            city='Одеса',
            warehouse='1',
            total='10.00',
        )
        self.client.force_login(user)
        page = self.client.get(reverse('admin:orders_order_change', args=[row.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'Створити ТТН')
        posted = self.client.post(reverse('admin:orders_order_create_ttn', args=[row.pk]))
        self.assertEqual(posted.status_code, 403)
