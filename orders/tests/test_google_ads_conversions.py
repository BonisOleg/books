import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from orders.google_ads_conversions import (
    build_conversion,
    format_conversion_datetime,
    normalize_and_hash_email,
    normalize_and_hash_phone,
    upload_completed_orders,
)
from orders.models import OfflineConversionLog

ADS = {
    'KEYCRM_API_KEY': 'key',
    'KEYCRM_COMPLETED_STATUS_ID': 12,
    'GOOGLE_ADS_CLIENT_ID': 'cid',
    'GOOGLE_ADS_CLIENT_SECRET': 'sec',
    'GOOGLE_ADS_REFRESH_TOKEN': 'ref',
    'GOOGLE_ADS_DEVELOPER_TOKEN': 'dev-token',
    'GOOGLE_ADS_CUSTOMER_ID': '111-222-3333',
    'GOOGLE_ADS_CONVERSION_ACTION_ID': '999',
    'GOOGLE_ADS_LOGIN_CUSTOMER_ID': '',
    'GOOGLE_ADS_API_VERSION': 'v18',
}


def _sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _response(payload, status_code=200):
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode()
    response.url = 'https://example.test'
    return response


def _order():
    moment = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    return {
        'id': 77,
        'grand_total': '150.50',
        'closed_at': moment,
        'updated_at': moment,
        'buyer': {'phone': '0501112233', 'email': 'I.van@gmail.com'},
    }


class NormalizeTests(TestCase):
    def test_phone_variants_match_e164(self):
        expected = _sha('+380501112233')
        self.assertEqual(normalize_and_hash_phone('0501112233'), expected)
        self.assertEqual(normalize_and_hash_phone('+380 (50) 111-22-33'), expected)
        self.assertEqual(normalize_and_hash_phone('501112233'), expected)

    def test_phone_rejects_foreign_and_empty(self):
        self.assertIsNone(normalize_and_hash_phone(''))
        self.assertIsNone(normalize_and_hash_phone(None))
        self.assertIsNone(normalize_and_hash_phone('+14155552671'))

    def test_email_gmail_dots_and_case(self):
        self.assertEqual(
            normalize_and_hash_email('I.van@gmail.com'),
            _sha('ivan@gmail.com'),
        )
        self.assertEqual(
            normalize_and_hash_email('I.van@Example.com'),
            _sha('i.van@example.com'),
        )
        self.assertIsNone(normalize_and_hash_email('not-an-email'))

    def test_kyiv_offset_has_colon(self):
        text = format_conversion_datetime(
            datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        self.assertRegex(text, r'^2026-01-15 \d{2}:\d{2}:\d{2}\+0[23]:00$')


@override_settings(**ADS)
class UploadTests(TestCase):
    def test_payload_and_dedup(self):
        router = _Router([_order()])
        with patch('orders.google_ads_conversions.requests.get', router.get), \
                patch('orders.google_ads_conversions.requests.post', router.post):
            first = upload_completed_orders()
            second = upload_completed_orders()

        self.assertEqual(first['uploaded'], 1)
        self.assertEqual(first['failed'], 0)
        self.assertEqual(second['uploaded'], 0)
        self.assertEqual(second['skipped'], 1)
        self.assertEqual(len(router.uploads), 1)

        conversion = router.uploads[0]['conversions'][0]
        self.assertEqual(conversion['orderId'], '77')
        self.assertEqual(conversion['currencyCode'], 'UAH')
        self.assertEqual(conversion['conversionValue'], 150.5)
        self.assertEqual(
            conversion['conversionAction'],
            'customers/1112223333/conversionActions/999',
        )
        self.assertEqual(
            conversion['userIdentifiers'],
            [
                {'hashedPhoneNumber': _sha('+380501112233')},
                {'hashedEmail': _sha('ivan@gmail.com')},
            ],
        )
        self.assertRegex(
            conversion['conversionDateTime'],
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\+0[23]:00$',
        )
        self.assertEqual(router.uploads[0].get('partialFailure'), True)
        self.assertNotIn('login-customer-id', router.headers)
        self.assertEqual(
            OfflineConversionLog.objects.get(keycrm_order_id=77).status,
            OfflineConversionLog.STATUS_UPLOADED,
        )

    def test_skips_order_without_identifiers(self):
        order = _order()
        order['buyer'] = {'phone': '123', 'email': ''}
        router = _Router([order])
        with patch('orders.google_ads_conversions.requests.get', router.get), \
                patch('orders.google_ads_conversions.requests.post', router.post):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 0)
        self.assertEqual(summary['skipped'], 1)
        self.assertEqual(router.uploads, [])
        self.assertFalse(OfflineConversionLog.objects.exists())

    def test_duplicate_order_id_is_treated_as_uploaded(self):
        router = _Router([_order()], google_payload={
            'partialFailureError': {
                'code': 3,
                'message': 'Multiple errors',
                'details': [{
                    'errors': [{
                        'errorCode': {'conversionUploadError': 'ORDER_ID_ALREADY_EXISTS'},
                        'message': 'The click conversion already has this order id.',
                        'location': {'fieldPathElements': [
                            {'fieldName': 'conversions', 'index': 0},
                        ]},
                    }],
                }],
            },
            'results': [{}],
        })
        with patch('orders.google_ads_conversions.requests.get', router.get), \
                patch('orders.google_ads_conversions.requests.post', router.post):
            first = upload_completed_orders()
            second = upload_completed_orders()
        self.assertEqual(first['uploaded'], 1)
        self.assertEqual(second['skipped'], 1)
        self.assertEqual(len(router.uploads), 1)

    def test_failed_order_is_retried(self):
        router = _Router([_order()], google_payload={
            'partialFailureError': {
                'message': 'bad action',
                'details': [{
                    'errors': [{
                        'errorCode': {'conversionUploadError': 'INVALID_CONVERSION_ACTION'},
                        'message': 'bad action',
                        'location': {'fieldPathElements': [
                            {'fieldName': 'conversions', 'index': 0},
                        ]},
                    }],
                }],
            },
            'results': [{}],
        })
        with patch('orders.google_ads_conversions.requests.get', router.get), \
                patch('orders.google_ads_conversions.requests.post', router.post):
            first = upload_completed_orders()
            second = upload_completed_orders()
        self.assertEqual(first['failed'], 1)
        self.assertEqual(second['uploaded'], 0)
        self.assertEqual(second['failed'], 1)
        self.assertEqual(len(router.uploads), 2)

    @override_settings(GOOGLE_ADS_LOGIN_CUSTOMER_ID='999-111-2222')
    def test_login_customer_header(self):
        router = _Router([_order()])
        with patch('orders.google_ads_conversions.requests.get', router.get), \
                patch('orders.google_ads_conversions.requests.post', router.post):
            upload_completed_orders()
        self.assertEqual(router.headers.get('login-customer-id'), '9991112222')

    def test_date_filter_fallback(self):
        router = _Router([_order()], reject_dated=True)
        with patch('orders.google_ads_conversions.requests.get', router.get), \
                patch('orders.google_ads_conversions.requests.post', router.post):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 1)
        self.assertGreaterEqual(len(router.gets), 2)
        self.assertNotIn('filter[updated_between]', router.gets[-1])

    def test_build_conversion_keeps_source_clock(self):
        self.assertIsNone(build_conversion(
            {'id': 1, 'buyer': {}},
            customer_id='1',
            action_id='2',
        ))
        conversion = build_conversion(
            {
                'id': 5,
                'grand_total': 10,
                'closed_at': '2026-10-20 12:00:00',
                'buyer': {'email': 'a@b.com'},
            },
            customer_id='1',
            action_id='2',
            now=datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc),
        )
        self.assertRegex(
            conversion['conversionDateTime'],
            r'^2026-10-20 12:00:00\+0[23]:00$',
        )


@override_settings(**ADS)
class CommandTests(TestCase):
    def test_command_prints_summary(self):
        router = _Router([_order()])
        with patch('orders.google_ads_conversions.requests.get', router.get), \
                patch('orders.google_ads_conversions.requests.post', router.post):
            call_command('upload_keycrm_conversions')
        self.assertEqual(len(router.uploads), 1)

    @override_settings(GOOGLE_ADS_DEVELOPER_TOKEN='')
    def test_command_noop_without_token(self):
        with patch('orders.google_ads_conversions.requests.get') as get_mock:
            call_command('upload_keycrm_conversions')
        get_mock.assert_not_called()

    def test_command_fails_on_http_error(self):
        router = _Router([_order()], google_status=401)
        with patch('orders.google_ads_conversions.requests.get', router.get), \
                patch('orders.google_ads_conversions.requests.post', router.post):
            with self.assertRaises(CommandError):
                call_command('upload_keycrm_conversions')
        log = OfflineConversionLog.objects.get(keycrm_order_id=77)
        self.assertEqual(log.status, OfflineConversionLog.STATUS_FAILED)


class _Router:
    def __init__(self, orders, google_payload=None, google_status=200, reject_dated=False):
        self.orders = orders
        self.google_payload = google_payload or {'results': [{'conversionAction': 'ok'}]}
        self.google_status = google_status
        self.reject_dated = reject_dated
        self.uploads = []
        self.headers = {}
        self.gets = []

    def get(self, url, **kwargs):
        params = kwargs.get('params') or {}
        self.gets.append(params)
        if self.reject_dated and 'filter[updated_between]' in params:
            return _response({'message': 'bad filter'}, 400)
        return _response({'data': self.orders, 'last_page': 1})

    def post(self, url, **kwargs):
        if 'oauth2.googleapis.com' in url:
            return _response({'access_token': 'token'})
        self.headers = kwargs.get('headers') or {}
        self.uploads.append(kwargs.get('json') or {})
        return _response(self.google_payload, self.google_status)
