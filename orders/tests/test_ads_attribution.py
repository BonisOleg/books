"""Тести cookie ofion_ads, KeyCRM marketing/custom_fields, eventSource, CSV, Telegram."""

from __future__ import annotations

import csv
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from orders.ads_attribution import (
    COOKIE_NAME,
    apply_ads_to_order,
    encode_ads_cookie,
    marketing_from_order,
    read_ads_cookie,
)
from orders.google_ads_conversions import upload_completed_orders
from orders.google_ads_conversions1 import (
    build_event,
    first_contact_value,
    normalize_phone_e164,
    resolve_event_source,
    transaction_id_of,
)
from orders.keycrm import _build_payload, _clear_runtime_cache, sync_order
from orders.middleware import AdsAttributionMiddleware
from orders.models import OfflineConversionLog, Order, OrderItem
from orders.tests.test_google_ads_conversions import ADS, _Router, _order, _patched
from orders.tests.test_keycrm import LOC_MEM, KeyCrmRouter
from orders.views import (
    ORDER_SESSION_KEY,
    PURCHASE_DATALAYER_SESSION_KEY,
    _purchase_datalayer_payload,
)
from products.models import Product


class AdsCookieTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_middleware_sets_cookie_only_when_params_present(self):
        def view(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        middleware = AdsAttributionMiddleware(view)
        request = self.factory.get('/?gclid=abc123&utm_source=google')
        response = middleware(request)
        raw = response.cookies[COOKIE_NAME].value
        decoded = read_ads_cookie(
            type('R', (), {'COOKIES': {COOKIE_NAME: raw}})(),
        )
        self.assertEqual(decoded['gclid'], 'abc123')
        self.assertEqual(decoded['utm_source'], 'google')

        plain = middleware(self.factory.get('/'))
        self.assertNotIn(COOKIE_NAME, plain.cookies)

    def test_apply_ads_to_order_from_cookie(self):
        request = self.factory.get('/')
        request.COOKIES = {
            COOKIE_NAME: encode_ads_cookie({
                'gclid': 'G1',
                'gbraid': 'GB1',
                'wbraid': 'WB1',
                'utm_source': 'google',
                'utm_medium': 'cpc',
                'utm_campaign': 'spring',
                'utm_term': 'book',
                'utm_content': 'ad1',
            }),
        }
        order = Order(
            first_name='А',
            last_name='Б',
            phone='+380501112233',
            city='Київ',
            warehouse='1',
        )
        changed = apply_ads_to_order(order, request)
        self.assertIn('gclid', changed)
        self.assertEqual(order.gclid, 'G1')
        self.assertEqual(order.utm_campaign, 'spring')
        self.assertEqual(marketing_from_order(order)['utm_campaign'], 'spring')


@override_settings(
    KEYCRM_API_KEY='test-key',
    KEYCRM_SOURCE_ID='22',
    KEYCRM_CF_GCLID_UUID='uuid-gclid',
    KEYCRM_CF_GBRAID_UUID='uuid-gbraid',
    KEYCRM_CF_WBRAID_UUID='',
    CACHES=LOC_MEM,
)
class KeyCrmAdsPayloadTests(TestCase):
    def setUp(self):
        _clear_runtime_cache()
        self.order = Order.objects.create(
            first_name='Іван',
            last_name='Петренко',
            phone='+380501112233',
            email='ivan@example.com',
            city='Київ',
            warehouse='1',
            payment_method='cod',
            total='50.00',
            gclid='click-1',
            gbraid='braid-1',
            wbraid='wbraid-1',
            utm_source='google',
            utm_medium='cpc',
            utm_campaign='books',
            utm_term='statuette',
            utm_content='banner',
        )
        OrderItem.objects.create(
            order=self.order,
            product_name='Книга',
            product_sku='SKU-1',
            price='50.00',
            quantity=1,
        )

    def test_build_payload_source_uuid_and_marketing(self):
        payload = _build_payload(self.order, 22)
        self.assertEqual(payload['source_uuid'], self.order.order_number)
        self.assertEqual(payload['marketing'], {
            'utm_source': 'google',
            'utm_medium': 'cpc',
            'utm_campaign': 'books',
            'utm_term': 'statuette',
            'utm_content': 'banner',
        })
        self.assertEqual(payload['custom_fields'], [
            {'uuid': 'uuid-gclid', 'value': 'click-1'},
            {'uuid': 'uuid-gbraid', 'value': 'braid-1'},
        ])
        self.assertNotIn('manager_comment', payload)

    def test_sync_posts_marketing(self):
        router = KeyCrmRouter()
        with patch('orders.keycrm.requests.request', router):
            sync_order(self.order)
        self.assertEqual(router.posts[0]['source_uuid'], self.order.order_number)
        self.assertEqual(router.posts[0]['marketing']['utm_source'], 'google')


@override_settings(**ADS, KEYCRM_SITE_SOURCE_ID='22', KEYCRM_CF_GCLID_UUID='cf-gclid')
class ConversionAttributionTests(TestCase):
    def test_transaction_id_prefers_source_uuid(self):
        order = {'id': 77, 'source_uuid': '000042', 'buyer': {'email': 'a@b.com'}}
        self.assertEqual(transaction_id_of(order), '000042')
        event = build_event(order)
        self.assertEqual(event['transactionId'], '000042')
        self.assertEqual(transaction_id_of({'id': 77}), 'keycrm-77')

    def test_transaction_id_maps_legacy_order_id_to_order_number(self):
        local = Order.objects.create(
            first_name='А',
            last_name='Б',
            phone='+380501112233',
            city='Київ',
            warehouse='1',
            total='10.00',
        )
        legacy = {'id': 9001, 'source_uuid': str(local.id), 'buyer': {'email': 'a@b.com'}}
        self.assertEqual(transaction_id_of(legacy), local.order_number)
        event = build_event(legacy)
        self.assertEqual(event['transactionId'], local.order_number)

        padded = {'id': 9002, 'source_uuid': local.order_number, 'buyer': {'email': 'a@b.com'}}
        self.assertEqual(transaction_id_of(padded), local.order_number)

        missing = {'id': 9003, 'source_uuid': '999999001', 'buyer': {'email': 'a@b.com'}}
        self.assertEqual(transaction_id_of(missing), '999999001')
        self.assertEqual(
            transaction_id_of({'id': 55, 'source_uuid': ''}),
            'keycrm-55',
        )

    def test_event_source_offline_vs_web(self):
        self.assertEqual(
            resolve_event_source({'id': 1, 'source_uuid': '000001', 'source_id': 99}),
            'WEB',
        )
        self.assertEqual(
            resolve_event_source({'id': 1, 'source_uuid': '', 'source_id': 22}),
            'WEB',
        )
        self.assertEqual(
            resolve_event_source({'id': 1, 'source_uuid': '', 'source_id': 99}),
            'OTHER',
        )
        self.assertEqual(
            resolve_event_source({'id': 1, 'source_uuid': ''}),
            'OTHER',
        )

    def test_phone_email_list_and_click_ids_from_custom_fields(self):
        self.assertEqual(first_contact_value(['', '0501112233']), '0501112233')
        self.assertEqual(normalize_phone_e164(['0501112233']), '+380501112233')
        order = {
            'id': 9,
            'source_uuid': '000009',
            'buyer': {'phone': ['0501112233'], 'email': ['I.van@gmail.com']},
            'custom_fields': [
                {'uuid': 'cf-gclid', 'value': 'GCLID-X'},
                {'uuid': 'other', 'value': 'nope'},
            ],
            'marketing': {'utm_campaign': 'spring'},
        }
        event = build_event(order)
        self.assertEqual(event['adIdentifiers'], {'gclid': 'GCLID-X'})
        self.assertEqual(event['eventSource'], 'WEB')
        self.assertIn('userIdentifiers', event['userData'])

    def test_upload_fills_log_meta_and_gbraid(self):
        order = _order()
        order['source_uuid'] = '000077'
        order['status_id'] = 12
        order['marketing'] = {'utm_campaign': 'winter', 'gbraid': 'GB-1'}
        order['buyer'] = {'phone': '0501112233'}
        router = _Router([order])
        with _patched(router):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 1)
        event = router.uploads[0]['events'][0]
        self.assertEqual(event['transactionId'], '000077')
        self.assertEqual(event['adIdentifiers'], {'gbraid': 'GB-1'})
        log = OfflineConversionLog.objects.get(keycrm_order_id=77)
        self.assertEqual(log.utm_campaign, 'winter')
        self.assertTrue(log.has_gclid)
        self.assertTrue(log.has_contact)
        self.assertEqual(str(log.amount), '150.50')
        self.assertEqual(log.order_status, '12')


@override_settings(**ADS)
class ExportAndTelegramTests(TestCase):
    def test_export_conversion_log_csv(self):
        OfflineConversionLog.objects.create(
            keycrm_order_id=1,
            status=OfflineConversionLog.STATUS_UPLOADED,
            order_status='12',
            utm_campaign='x',
            has_gclid=True,
            has_contact=False,
            amount='10.00',
            order_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'log.csv'
            call_command('export_conversion_log', f'--out={out}')
            with out.open(encoding='utf-8') as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['keycrm_order_id'], '1')
        self.assertEqual(rows[0]['has_gclid'], '1')
        self.assertEqual(rows[0]['utm_campaign'], 'x')
        self.assertNotIn('phone', rows[0])
        self.assertNotIn('email', rows[0])

    @override_settings(TELEGRAM_BOT_TOKEN='tok', TELEGRAM_CHAT_ID='42')
    def test_summary_and_failure_telegram(self):
        router = _Router([_order()])
        with _patched(router), \
                patch('orders.telegram_notify.send_message', return_value=True) as send_mock:
            call_command('upload_keycrm_conversions', '--summary')
        self.assertTrue(send_mock.called)
        self.assertIn('підсумок', send_mock.call_args.args[0])

        OfflineConversionLog.objects.all().delete()
        bad = _Router([_order()], google_status=500)
        with _patched(bad), \
                patch('orders.telegram_notify.send_message', return_value=True) as fail_mock:
            with self.assertRaises(requests.HTTPError):
                upload_completed_orders()
        self.assertTrue(fail_mock.called)
        self.assertIn('збій', fail_mock.call_args.args[0].lower())

    @override_settings(TELEGRAM_BOT_TOKEN='', TELEGRAM_CHAT_ID='')
    def test_telegram_silently_skips_without_credentials(self):
        from orders.telegram_notify import send_message
        with patch('orders.telegram_notify.requests.post') as post_mock:
            self.assertFalse(send_message('hi'))
        post_mock.assert_not_called()


@override_settings(KEYCRM_API_KEY='test-key', KEYCRM_SOURCE_ID='22', CACHES=LOC_MEM)
class CheckoutAdsCookieTests(TestCase):
    def setUp(self):
        _clear_runtime_cache()
        self.product = Product.objects.create(
            name='Статуетка',
            slug='statuetka-ads',
            sku='SKU-ADS-1',
            description='Опис',
            price='100.00',
        )

    @patch('orders.forms.validate_form_guards')
    @patch('orders.views.sync_order')
    def test_oneclick_reads_cookie(self, sync_mock, _guards):
        self.client.cookies[COOKIE_NAME] = encode_ads_cookie({
            'gclid': 'OC1',
            'utm_source': 'google',
        })
        response = self.client.post(
            reverse('orders:oneclick', args=[self.product.id]),
            {'phone': '+380501112233', 'name': 'Марія', 'website': '', 'form_ts': 'token'},
        )
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.gclid, 'OC1')
        self.assertEqual(order.utm_source, 'google')
        sync_mock.assert_called_once()


class PurchaseDataLayerTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            first_name='Іван',
            last_name='Петренко',
            phone='0501112233',
            email='  Ivan.PETRENKO@Example.COM ',
            city='Київ',
            warehouse='1',
            payment_method='cod',
            total='125.50',
        )
        OrderItem.objects.create(
            order=self.order,
            product_name='Книга <b>XSS</b>',
            product_sku='SKU-"1"',
            price='125.50',
            quantity=2,
        )

    def test_payload_ecommerce_and_raw_user_data(self):
        payload = _purchase_datalayer_payload(self.order)
        items = [{
            'item_id': 'SKU-"1"',
            'item_name': 'Книга <b>XSS</b>',
            'price': 125.5,
            'quantity': 2,
        }]
        self.assertEqual(payload['event'], 'purchase')
        self.assertEqual(payload['ecommerce'], {
            'transaction_id': self.order.order_number,
            'value': 125.5,
            'currency': 'UAH',
            'items': items,
        })
        # Top-level дублікати ecommerce (зворотна сумісність GTM)
        self.assertEqual(payload['transaction_id'], self.order.order_number)
        self.assertEqual(payload['value'], 125.5)
        self.assertEqual(payload['currency'], 'UAH')
        self.assertEqual(payload['items'], items)
        self.assertEqual(payload['user_data'], {
            'email': 'ivan.petrenko@example.com',
            'phone_number': '+380501112233',
        })
        # email/phone лише в user_data, не на верхньому рівні
        self.assertNotIn('email', payload)
        self.assertNotIn('phone', payload)
        self.assertNotIn('phone_number', payload)

    def test_order_success_json_script_once_and_access_guard(self):
        url = reverse('orders:success', args=[self.order.id])
        denied = self.client.get(url)
        self.assertEqual(denied.status_code, 404)

        session = self.client.session
        session[ORDER_SESSION_KEY] = [self.order.id]
        session.save()

        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, 'id="purchase-datalayer"', html=False)
        self.assertContains(first, "dataLayer.push({ ecommerce: null })", html=False)
        self.assertContains(first, 'dataLayer.push(data)', html=False)
        self.assertContains(first, 'gtm_purchase_', html=False)
        self.assertNotContains(first, "gtag('event'", html=False)

        script = first.context['purchase_datalayer']
        self.assertEqual(script['ecommerce']['transaction_id'], self.order.order_number)
        self.assertEqual(script['transaction_id'], self.order.order_number)
        self.assertEqual(script['value'], script['ecommerce']['value'])
        self.assertEqual(script['currency'], 'UAH')
        self.assertEqual(script['items'], script['ecommerce']['items'])
        self.assertEqual(script['user_data']['email'], 'ivan.petrenko@example.com')
        self.assertEqual(script['user_data']['phone_number'], '+380501112233')
        self.assertNotIn('email', script)
        self.assertNotIn('phone_number', script)

        node_match = (
            b'<script id="purchase-datalayer" type="application/json">'
            in first.content
        )
        self.assertTrue(node_match)
        # XSS у назві товару має бути в JSON (екрановано), не як сирий HTML-тег
        self.assertNotIn('Книга <b>XSS</b>', first.content.decode())
        embedded = json.loads(
            first.content.split(b'id="purchase-datalayer"', 1)[1]
            .split(b'>', 1)[1]
            .split(b'</script>', 1)[0]
            .decode()
        )
        self.assertEqual(embedded['ecommerce']['items'][0]['item_name'], 'Книга <b>XSS</b>')

        self.assertIn(
            self.order.order_number,
            self.client.session.get(PURCHASE_DATALAYER_SESSION_KEY, []),
        )

        second = self.client.get(url)
        self.assertEqual(second.status_code, 200)
        self.assertNotContains(second, 'id="purchase-datalayer"', html=False)
        self.assertIsNone(second.context['purchase_datalayer'])
