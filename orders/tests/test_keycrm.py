import base64
import hashlib
import json
from unittest.mock import patch

import requests
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from orders.keycrm import _clear_runtime_cache, sync_order
from orders.models import Order, OrderItem
from products.models import Product

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'keycrm-tests',
    }
}


def _response(payload, status_code=200):
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode()
    response.url = 'https://openapi.keycrm.app/v1/order'
    return response


class KeyCrmRouter:
    def __init__(self):
        self.posts = []
        self.puts = []

    def __call__(self, method, url, **kwargs):
        path = url.split('/v1', 1)[-1]
        if method == 'GET' and path.startswith('/order/payment-method'):
            return _response({'data': [
                {'id': 7, 'name': 'LiqPay', 'alias': 'liqpay'},
                {'id': 8, 'name': 'Накладений платіж'},
            ]})
        if method == 'GET' and path.startswith('/order/delivery-service'):
            return _response({'data': [{'id': 3, 'name': 'Нова Пошта'}]})
        if method == 'GET' and path.startswith('/order/source'):
            return _response({'data': [{'id': 22, 'name': 'Сайт'}]})
        if method == 'POST' and path == '/order':
            self.posts.append(kwargs.get('json'))
            return _response({'id': 501, 'payments': [{'id': 900, 'status': 'not_paid'}]})
        if method == 'PUT' and '/payment/' in path:
            self.puts.append((path, kwargs.get('json')))
            return _response({'id': 900, 'status': 'paid'})
        if method == 'GET' and path.startswith('/order'):
            return _response({'data': []})
        return _response({})


@override_settings(KEYCRM_API_KEY='test-key', KEYCRM_SOURCE_ID='22', CACHES=LOC_MEM)
class KeyCrmSyncTests(TestCase):
    def setUp(self):
        _clear_runtime_cache()
        self.router = KeyCrmRouter()
        self.order = Order.objects.create(
            first_name='Іван',
            last_name='Петренко',
            patronymic='Іванович',
            phone='+380501112233',
            email='ivan@example.com',
            city='Київ',
            warehouse='Відділення 1',
            warehouse_ref='wh-ref',
            comment='Передзвоніть',
            payment_method='liqpay',
            payment_status='pending',
            total='150.00',
        )
        OrderItem.objects.create(
            order=self.order,
            product_name='Книга',
            product_sku='SKU-1',
            price='150.00',
            quantity=2,
        )

    def test_skips_without_api_key(self):
        with override_settings(KEYCRM_API_KEY=''):
            with patch('orders.keycrm.requests.request') as request_mock:
                sync_order(self.order)
        request_mock.assert_not_called()
        self.order.refresh_from_db()
        self.assertIsNone(self.order.keycrm_order_id)

    def test_posts_order_payload_once(self):
        with patch('orders.keycrm.requests.request', self.router):
            sync_order(self.order)
            sync_order(self.order)

        self.assertEqual(len(self.router.posts), 1)
        payload = self.router.posts[0]
        self.assertEqual(payload['source_id'], 22)
        self.assertEqual(payload['source_uuid'], str(self.order.id))
        self.assertEqual(payload['buyer']['full_name'], 'Іван Іванович Петренко')
        self.assertEqual(payload['buyer']['phone'], '+380501112233')
        self.assertEqual(payload['buyer_comment'], 'Передзвоніть')
        self.assertEqual(payload['products'], [{
            'sku': 'SKU-1',
            'name': 'Книга',
            'price': 150.0,
            'quantity': 2,
        }])
        self.assertEqual(payload['shipping']['shipping_address_city'], 'Київ')
        self.assertEqual(payload['shipping']['shipping_receive_point'], 'Відділення 1')
        self.assertEqual(payload['shipping']['warehouse_ref'], 'wh-ref')
        self.assertEqual(payload['shipping']['delivery_service_id'], 3)
        self.assertEqual(payload['payments'][0]['status'], 'not_paid')
        self.assertEqual(payload['payments'][0]['payment_method_id'], 7)
        self.assertEqual(payload['payments'][0]['amount'], 150.0)
        self.order.refresh_from_db()
        self.assertEqual(self.order.keycrm_order_id, 501)
        self.assertEqual(self.order.keycrm_payment_id, 900)
        self.assertEqual(len(self.router.puts), 1)
        self.assertEqual(self.router.puts[0][1], {'status': 'not_paid'})

    def test_reuses_existing_crm_order(self):
        def existing(method, url, **kwargs):
            path = url.split('/v1', 1)[-1]
            if (
                method == 'GET'
                and path.startswith('/order')
                and not path.startswith('/order/payment')
                and not path.startswith('/order/source')
                and not path.startswith('/order/delivery')
            ):
                return _response({'data': [{
                    'id': 77,
                    'source_uuid': str(self.order.id),
                    'payments': [{'id': 88}],
                }]})
            return self.router(method, url, **kwargs)

        with patch('orders.keycrm.requests.request', existing):
            sync_order(self.order)

        self.assertEqual(self.router.posts, [])
        self.order.refresh_from_db()
        self.assertEqual(self.order.keycrm_order_id, 77)
        self.assertEqual(self.order.keycrm_payment_id, 88)

    def test_paid_status_updates_payment(self):
        self.order.keycrm_order_id = 501
        self.order.keycrm_payment_id = 900
        self.order.payment_status = 'paid'
        self.order.save(update_fields=['keycrm_order_id', 'keycrm_payment_id', 'payment_status'])

        with patch('orders.keycrm.requests.request', self.router):
            sync_order(self.order)

        self.assertEqual(self.router.posts, [])
        self.assertEqual(
            self.router.puts,
            [('/order/501/payment/900', {'status': 'paid'})],
        )

    def test_api_error_is_swallowed(self):
        with patch('orders.keycrm.requests.request', side_effect=requests.Timeout('slow')):
            sync_order(self.order)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.keycrm_order_id)

    @override_settings(KEYCRM_SOURCE_ID='')
    def test_single_source_is_used_when_id_is_empty(self):
        _clear_runtime_cache()
        with patch('orders.keycrm.requests.request', self.router):
            sync_order(self.order)
        self.assertEqual(self.router.posts[0]['source_id'], 22)

    @override_settings(KEYCRM_SOURCE_ID='')
    def test_several_sources_skip_create(self):
        _clear_runtime_cache()

        def several(method, url, **kwargs):
            path = url.split('/v1', 1)[-1]
            if method == 'GET' and path.startswith('/order/source'):
                return _response({'data': [{'id': 1}, {'id': 2}]})
            return self.router(method, url, **kwargs)

        with patch('orders.keycrm.requests.request', several):
            sync_order(self.order)
        self.assertEqual(self.router.posts, [])
        self.order.refresh_from_db()
        self.assertIsNone(self.order.keycrm_order_id)


@override_settings(KEYCRM_API_KEY='test-key', KEYCRM_SOURCE_ID='22', CACHES=LOC_MEM)
class KeyCrmCheckoutTests(TestCase):
    def setUp(self):
        _clear_runtime_cache()
        self.product = Product.objects.create(
            name='Статуетка',
            slug='statuetka-keycrm',
            sku='SKU-KEYCRM-1',
            description='Опис',
            price='100.00',
        )

    def _fill_cart(self):
        session = self.client.session
        session['cart'] = {
            str(self.product.id): {'quantity': 1, 'price': '100.00'},
        }
        session.save()

    def _checkout_data(self, payment_method):
        return {
            'first_name': 'Олег',
            'last_name': 'Коваленко',
            'patronymic': '',
            'phone': '+380671112233',
            'email': '',
            'city': 'Львів',
            'warehouse': 'Відділення 5',
            'warehouse_ref': '',
            'comment': '',
            'payment_method': payment_method,
            'checkout_mode': 'guest',
            'website': '',
            'form_ts': 'token',
        }

    @patch('orders.forms.validate_form_guards')
    def test_checkout_survives_keycrm_outage(self, _guards):
        self._fill_cart()
        with patch('orders.keycrm.requests.request', side_effect=requests.ConnectionError('down')):
            response = self.client.post(
                reverse('orders:checkout'),
                self._checkout_data('liqpay'),
            )
        order = Order.objects.get()
        self.assertRedirects(
            response,
            reverse('orders:pay_liqpay', args=[order.id]),
            fetch_redirect_response=False,
        )
        self.assertIsNone(order.keycrm_order_id)
        self.assertEqual(order.payment_method, 'liqpay')

    @patch('orders.views.sync_order')
    @patch('orders.forms.validate_form_guards')
    def test_oneclick_calls_sync(self, _guards, sync_mock):
        response = self.client.post(
            reverse('orders:oneclick', args=[self.product.id]),
            {'phone': '+380501112233', 'name': 'Марія', 'website': '', 'form_ts': 'token'},
        )
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.comment, 'Замовлення в 1 клік — уточнити доставку')
        sync_mock.assert_called_once()
        self.assertEqual(sync_mock.call_args.args[0].pk, order.pk)


@override_settings(LIQPAY_PRIVATE_KEY='priv', KEYCRM_API_KEY='', CACHES=LOC_MEM)
class KeyCrmCallbackTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            first_name='Іван',
            last_name='Петренко',
            phone='+380501112233',
            city='Київ',
            warehouse='Відділення 1',
            payment_method='liqpay',
            total='10.00',
        )

    @patch('orders.keycrm.sync_order')
    def test_liqpay_callback_syncs_paid_order(self, sync_mock):
        payload = {'order_id': str(self.order.id), 'status': 'success', 'payment_id': 'lp-1'}
        data = base64.b64encode(json.dumps(payload).encode()).decode()
        signature = base64.b64encode(
            hashlib.sha1(f'priv{data}priv'.encode()).digest()
        ).decode()
        request = RequestFactory().post('/', {'data': data, 'signature': signature})
        from orders.payments.liqpay_service import process_callback
        process_callback(request)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'paid')
        sync_mock.assert_called_once()

    @patch('orders.payments.monobank_service._verify_mono_signature', return_value=True)
    @patch('orders.keycrm.sync_order')
    def test_mono_callback_syncs_paid_order(self, sync_mock, _verify):
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
        from orders.payments.monobank_service import process_callback
        process_callback(request)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'paid')
        sync_mock.assert_called_once()
