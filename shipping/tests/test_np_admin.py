from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Order
from shipping.tests.factories import order, origin, route_np, ttn_settings

User = get_user_model()


def _message_html(response):
    content = response.content.decode()
    return content


@override_settings(NOVAPOSHTA_API_KEY='np-test-key')
class OrderTtnAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('np-root', 'np@example.com', 'pass12345')
        self.staff = User.objects.create_user(
            'np-staff', 'staff@example.com', 'pass12345', is_staff=True,
        )
        self.origin_row = origin()
        ttn_settings()
        self.order = order(shipment_origin=self.origin_row)
        self.client.force_login(self.admin)

    def _create_url(self, row):
        return reverse('admin:orders_order_create_ttn', args=[row.pk])

    def test_change_page_has_csrf_button(self):
        response = self.client.get(reverse('admin:orders_order_change', args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Створити ТТН')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_get_is_not_allowed(self):
        response = self.client.get(self._create_url(self.order))
        self.assertEqual(response.status_code, 405)

    def test_anonymous_and_staff_without_permission_are_rejected(self):
        self.client.logout()
        response = self.client.post(self._create_url(self.order))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)
        self.client.force_login(self.staff)
        response = self.client.post(self._create_url(self.order))
        self.assertEqual(response.status_code, 403)

    def test_post_creates_ttn(self):
        with patch('shipping.np_ttn.requests.post', side_effect=route_np()):
            response = self.client.post(self._create_url(self.order), follow=True)
        self.order.refresh_from_db()
        self.assertEqual(self.order.ttn_number, '20450123456789')
        self.assertContains(response, 'ТТН 20450123456789 створено')

    def test_unpaid_online_requires_confirmation(self):
        self.order.payment_method = 'liqpay'
        self.order.payment_status = 'pending'
        self.order.save(update_fields=['payment_method', 'payment_status'])
        with patch('shipping.np_ttn.requests.post') as post:
            response = self.client.post(self._create_url(self.order), follow=True)
        post.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.ttn_number, '')
        self.assertContains(response, 'Онлайн-оплата ще не підтверджена')
        self.assertContains(response, 'Підтвердити створення ТТН')
        with patch('shipping.np_ttn.requests.post', side_effect=route_np()):
            self.client.post(self._create_url(self.order), {'confirm': '1'}, follow=True)
        self.order.refresh_from_db()
        self.assertEqual(self.order.ttn_number, '20450123456789')

    def test_bulk_action_skips_unpaid_online(self):
        online = order(
            shipment_origin=self.origin_row,
            payment_method='monobank',
            payment_status='pending',
            first_name='Марія',
        )
        with patch('shipping.np_ttn.requests.post', side_effect=route_np()) as post:
            response = self.client.post(reverse('admin:orders_order_changelist'), {
                'action': 'create_ttn_for_selected',
                '_selected_action': [str(self.order.pk), str(online.pk)],
                'select_across': '0',
            }, follow=True)
        self.assertEqual(post.call_count, 2)
        self.order.refresh_from_db()
        online.refresh_from_db()
        self.assertEqual(self.order.ttn_number, '20450123456789')
        self.assertEqual(online.ttn_number, '')
        html = _message_html(response)
        self.assertIn('Створено ТТН: 1', html)
        self.assertIn('Пропущено без підтвердження', html)
        self.assertIn(f'#{online.pk}', html)

    def test_changelist_links_tracking(self):
        self.order.ttn_number = '59000000000001'
        self.order.ttn_status = 'created'
        self.order.ttn_error = 'коротка помилка'
        self.order.save(update_fields=['ttn_number', 'ttn_status', 'ttn_error'])
        response = self.client.get(reverse('admin:orders_order_changelist'))
        self.assertContains(
            response,
            'https://novaposhta.ua/tracking/?cargo_number=59000000000001',
        )
        self.assertContains(response, 'коротка помилка')

    def test_city_and_warehouse_search_are_staff_only(self):
        city_url = reverse('admin:shipping_shipmentorigin_city_search')
        warehouse_url = reverse('admin:shipping_shipmentorigin_warehouse_search')
        self.client.logout()
        self.assertEqual(self.client.get(city_url).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(city_url, {'q': 'Київ'}).status_code, 403)
        self.client.force_login(self.admin)
        with patch(
            'shipping.novaposhta_api.search_cities',
            return_value=[{'ref': 'c1', 'name': 'м. Київ', 'settlement_ref': 's1'}],
        ) as cities:
            response = self.client.get(city_url, {'q': 'Київ'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['ref'], 'c1')
        cities.assert_called_once()
        with patch('shipping.novaposhta_api.search_cities') as cities:
            response = self.client.get(city_url, {'q': 'К'})
        cities.assert_not_called()
        self.assertEqual(response.json()['results'], [])
        city_ref = '11111111-1111-1111-1111-111111111111'
        with patch(
            'shipping.novaposhta_api.search_warehouses',
            return_value=[{'ref': 'w1', 'number': '1', 'description': '№1'}],
        ) as warehouses:
            response = self.client.get(warehouse_url, {'city_ref': city_ref, 'q': '1'})
        self.assertEqual(response.json()['results'][0]['ref'], 'w1')
        warehouses.assert_called_once()
        with patch('shipping.novaposhta_api.search_warehouses') as warehouses:
            response = self.client.get(warehouse_url, {'city_ref': 'bad', 'q': '1'})
        warehouses.assert_not_called()
        self.assertEqual(response.json()['results'], [])


class OrderWithoutPermissionQueryTests(TestCase):
    def test_missing_order_is_not_found_for_admin(self):
        admin = User.objects.create_superuser('np-root2', 'np2@example.com', 'pass12345')
        self.client.force_login(admin)
        response = self.client.post(reverse('admin:orders_order_create_ttn', args=[999999]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Order.objects.filter(pk=999999).exists())
