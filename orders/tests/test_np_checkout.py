import base64
import hashlib
import json
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from orders.models import Order
from products.models import Product
from shipping.np_ttn import create_ttn
from shipping.tests.factories import origin, route_np, ttn_settings


def _run_ttn_now(order_id):
    create_ttn(order_id)


_np_post = route_np()


@override_settings(NOVAPOSHTA_API_KEY='np-test-key', KEYCRM_API_KEY='')
class CheckoutTtnTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='ТТН товар',
            slug='ttn-product',
            sku='SKU-TTN-1',
            description='Опис',
            price='100.00',
        )
        self.origin = origin(is_default=True, is_active=True)

    def _fill_cart(self):
        session = self.client.session
        session['cart'] = {str(self.product.id): {'quantity': 1, 'price': '100.00'}}
        session.save()

    def _checkout_data(self, payment_method):
        return {
            'first_name': 'Олег',
            'last_name': 'Коваленко',
            'patronymic': '',
            'phone': '+380671112233',
            'email': '',
            'city': 'Львів',
            'city_ref': 'city-lviv',
            'warehouse': 'Відділення №5',
            'warehouse_ref': 'recip-wh-5',
            'comment': '',
            'payment_method': payment_method,
            'checkout_mode': 'guest',
            'website': '',
            'form_ts': 'token',
        }

    def _post_checkout(self, payment_method):
        self._fill_cart()
        return self.client.post(reverse('orders:checkout'), self._checkout_data(payment_method))

    @patch('orders.views.sync_order')
    @patch('orders.forms.validate_form_guards')
    def test_checkout_without_settings_is_not_blocked(self, _guards, _sync):
        with patch('shipping.np_ttn.enqueue_create_ttn') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                response = self._post_checkout('cod')
        order = Order.objects.get()
        enqueue.assert_not_called()
        self.assertEqual(order.ttn_number, '')
        self.assertEqual(order.ttn_error, '')
        self.assertEqual(order.shipment_origin_id, self.origin.pk)
        self.assertRedirects(
            response,
            reverse('orders:success', args=[order.id]),
            fetch_redirect_response=False,
        )

    @patch('orders.views.sync_order')
    @patch('orders.forms.validate_form_guards')
    def test_auto_off_does_not_enqueue(self, _guards, _sync):
        ttn_settings(auto_create_ttn=False)
        with patch('shipping.np_ttn.enqueue_create_ttn') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                response = self._post_checkout('cod')
        self.assertEqual(response.status_code, 302)
        enqueue.assert_not_called()
        self.assertEqual(Order.objects.get().ttn_number, '')

    @patch('orders.views.sync_order')
    @patch('orders.forms.validate_form_guards')
    def test_auto_cod_creates_ttn_without_blocking_checkout(self, _guards, _sync):
        ttn_settings(auto_create_ttn=True)
        with patch('shipping.np_ttn.enqueue_create_ttn', side_effect=_run_ttn_now), \
                patch('shipping.np_ttn.requests.post', side_effect=_np_post):
            with self.captureOnCommitCallbacks(execute=True):
                response = self._post_checkout('cod')
        order = Order.objects.get()
        self.assertRedirects(
            response,
            reverse('orders:success', args=[order.id]),
            fetch_redirect_response=False,
        )
        self.assertEqual(order.ttn_number, '20450123456789')
        self.assertEqual(order.ttn_status, 'created')
        self.assertEqual(order.city_ref, 'city-lviv')
        self.assertEqual(order.warehouse_ref, 'recip-wh-5')

    @patch('orders.views.sync_order')
    @patch('orders.forms.validate_form_guards')
    def test_auto_without_key_records_error_and_checkout_succeeds(self, _guards, _sync):
        ttn_settings(auto_create_ttn=True)
        with override_settings(NOVAPOSHTA_API_KEY=''):
            with patch('shipping.np_ttn.enqueue_create_ttn', side_effect=_run_ttn_now), \
                    patch('shipping.np_ttn.requests.post') as post:
                with self.captureOnCommitCallbacks(execute=True):
                    response = self._post_checkout('cod')
        post.assert_not_called()
        order = Order.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.ttn_error, 'Ключ НП не налаштовано')
        self.assertEqual(order.ttn_number, '')

    @patch('orders.views.sync_order')
    @patch('orders.forms.validate_form_guards')
    def test_auto_online_waits_for_payment(self, _guards, _sync):
        ttn_settings(auto_create_ttn=True)
        with patch('shipping.np_ttn.enqueue_create_ttn') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                response = self._post_checkout('liqpay')
        order = Order.objects.get()
        enqueue.assert_not_called()
        self.assertEqual(order.ttn_number, '')
        self.assertRedirects(
            response,
            reverse('orders:pay_liqpay', args=[order.id]),
            fetch_redirect_response=False,
        )

    @patch('orders.views.sync_order')
    @patch('orders.forms.validate_form_guards')
    def test_manager_payment_is_not_auto_created(self, _guards, _sync):
        ttn_settings(auto_create_ttn=True)
        with patch('shipping.np_ttn.enqueue_create_ttn') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                self._post_checkout('manager')
        enqueue.assert_not_called()

    @patch('orders.forms.validate_form_guards')
    def test_checkout_still_requires_warehouse(self, _guards):
        self._fill_cart()
        data = self._checkout_data('cod')
        data['warehouse'] = ''
        response = self.client.post(reverse('orders:checkout'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())


@override_settings(NOVAPOSHTA_API_KEY='np-test-key', LIQPAY_PRIVATE_KEY='priv', KEYCRM_API_KEY='')
class PaymentCallbackTtnTests(TestCase):
    def setUp(self):
        self.origin = origin(is_default=True)
        ttn_settings(auto_create_ttn=True)
        self.order = Order.objects.create(
            first_name='Іван',
            last_name='Петренко',
            phone='+380501112233',
            city='Київ',
            city_ref='city-recip',
            warehouse='Відділення №1',
            warehouse_ref='recip-wh',
            payment_method='liqpay',
            payment_status='pending',
            total='10.00',
        )

    def _liqpay_request(self, status='success'):
        payload = {'order_id': str(self.order.id), 'status': status, 'payment_id': 'lp-1'}
        data = base64.b64encode(json.dumps(payload).encode()).decode()
        signature = base64.b64encode(hashlib.sha1(f'priv{data}priv'.encode()).digest()).decode()
        return RequestFactory().post('/', {'data': data, 'signature': signature})

    @patch('orders.keycrm.sync_order')
    def test_liqpay_paid_schedules_ttn(self, _sync):
        from orders.payments.liqpay_service import process_callback
        with patch('shipping.np_ttn.enqueue_create_ttn', side_effect=_run_ttn_now), \
                patch('shipping.np_ttn.requests.post', side_effect=_np_post):
            with self.captureOnCommitCallbacks(execute=True):
                process_callback(self._liqpay_request('success'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(self.order.ttn_number, '20450123456789')

    @patch('orders.keycrm.sync_order')
    def test_liqpay_failed_does_not_create_ttn(self, _sync):
        from orders.payments.liqpay_service import process_callback
        with patch('shipping.np_ttn.enqueue_create_ttn') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                process_callback(self._liqpay_request('failure'))
        enqueue.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'failed')
        self.assertEqual(self.order.ttn_number, '')

    @patch('orders.payments.monobank_service._verify_mono_signature', return_value=True)
    @patch('orders.keycrm.sync_order')
    def test_mono_paid_schedules_ttn(self, _sync, _verify):
        from orders.payments.monobank_service import process_callback
        self.order.payment_method = 'monobank'
        self.order.save(update_fields=['payment_method'])
        body = json.dumps({
            'invoiceId': 'inv-1',
            'status': 'success',
            'reference': str(self.order.id),
        }).encode()
        request = RequestFactory().post(
            '/',
            data=body,
            content_type='application/json',
            HTTP_X_SIGN='sign',
        )
        with patch('shipping.np_ttn.enqueue_create_ttn', side_effect=_run_ttn_now), \
                patch('shipping.np_ttn.requests.post', side_effect=_np_post):
            with self.captureOnCommitCallbacks(execute=True):
                process_callback(request)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(self.order.ttn_number, '20450123456789')
