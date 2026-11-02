import io
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from suppliers.admin import SupplierSyncRunAdmin
from suppliers.models import SupplierSyncRun

from .utils import FIXTURE, make_product, make_supplier

User = get_user_model()


class SupplierAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.staff = User.objects.create_user('clerk', 'clerk@example.com', 'pass', is_staff=True)
        self.staff.user_permissions.add(
            Permission.objects.get(codename='change_supplier', content_type__app_label='suppliers')
        )
        self.product = make_product(
            slug='admin-p', sku='ADM', sku_manufacturer='4812345001001',
            price=Decimal('10.00'), old_price=Decimal('40.00'),
        )
        self.supplier = make_supplier()
        self.client.force_login(self.admin)
        self.fetch = patch('suppliers.fetch.requests.get', side_effect=self._feed_response)
        self.fetch.start()
        self.addCleanup(self.fetch.stop)

    def _feed_response(self, *args, **kwargs):
        fake = Mock()
        fake.raw = io.BytesIO(FIXTURE.read_bytes())
        fake.raise_for_status.return_value = None
        return fake

    def test_change_page_has_post_buttons(self):
        response = self.client.get(reverse('admin:suppliers_supplier_change', args=[self.supplier.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Перевірити (dry-run)')
        self.assertContains(response, 'Запустити')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_get_does_not_sync(self):
        url = reverse('admin:suppliers_supplier_sync', args=[self.supplier.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(SupplierSyncRun.objects.count(), 0)

    def test_dry_run_post_redirects_without_price_change(self):
        url = reverse('admin:suppliers_supplier_dry_run', args=[self.supplier.pk])
        response = self.client.post(url)
        run = SupplierSyncRun.objects.get()
        self.assertRedirects(response, reverse('admin:suppliers_suppliersyncrun_change', args=[run.pk]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('10.00'))
        self.assertTrue(run.dry_run)
        follow = self.client.get(response.url)
        self.assertEqual(follow.status_code, 200)
        self.assertContains(follow, 'Пробний запуск')
        self.assertContains(follow, 'supplier-sync-report')

    def test_dry_run_report_lists_future_out_of_stock(self):
        missing = make_product(
            name='Зникне з вітрини',
            slug='admin-missing',
            sku='ADM-MISS',
            sku_manufacturer='NO-FEED-ADM',
            price=Decimal('11.00'),
            stock_status='in_stock',
        )
        url = reverse('admin:suppliers_supplier_dry_run', args=[self.supplier.pk])
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Стане «Немає в наявності»: 1')
        self.assertContains(response, 'Зникне з вітрини | NO-FEED-ADM')
        missing.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(missing.stock_status, 'in_stock')
        self.assertEqual(self.product.price, Decimal('10.00'))
        self.assertEqual(self.product.stock_status, 'in_stock')

    def test_sync_post_updates_price(self):
        url = reverse('admin:suppliers_supplier_sync', args=[self.supplier.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('28630.00'))
        self.assertEqual(self.product.old_price, Decimal('40.00'))

    def test_csrf_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        change = client.get(reverse('admin:suppliers_supplier_change', args=[self.supplier.pk]))
        self.assertEqual(change.status_code, 200)
        url = reverse('admin:suppliers_supplier_dry_run', args=[self.supplier.pk])
        denied = client.post(url)
        self.assertEqual(denied.status_code, 403)
        token = client.cookies['csrftoken'].value
        allowed = client.post(url, {'csrfmiddlewaretoken': token})
        self.assertEqual(allowed.status_code, 302)
        self.assertEqual(SupplierSyncRun.objects.count(), 1)

    def test_staff_without_change_perm_is_forbidden(self):
        outsider = User.objects.create_user('outsider', 'o@example.com', 'pass', is_staff=True)
        self.client.force_login(outsider)
        response = self.client.post(reverse('admin:suppliers_supplier_sync', args=[self.supplier.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(SupplierSyncRun.objects.count(), 0)

    def test_anonymous_is_redirected(self):
        self.client.logout()
        response = self.client.post(reverse('admin:suppliers_supplier_sync', args=[self.supplier.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_staff_with_change_can_open_run(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('admin:suppliers_supplier_dry_run', args=[self.supplier.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Пробний запуск')
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('10.00'))

    def test_changelist_action_dry_run(self):
        response = self.client.post(reverse('admin:suppliers_supplier_changelist'), {
            'action': 'dry_run_selected',
            '_selected_action': [str(self.supplier.pk)],
        })
        self.assertEqual(response.status_code, 302)
        run = SupplierSyncRun.objects.get()
        self.assertTrue(run.dry_run)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('10.00'))

    def test_sync_run_is_readonly(self):
        site = AdminSite()
        model_admin = SupplierSyncRunAdmin(SupplierSyncRun, site)
        request = RequestFactory().get('/')
        request.user = self.staff
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertTrue(model_admin.has_view_permission(request))
        request.user = self.admin
        self.assertTrue(model_admin.has_delete_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
