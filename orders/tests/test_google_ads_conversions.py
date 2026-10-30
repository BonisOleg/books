import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings

from orders.google_ads_conversions import (
    build_event,
    format_conversion_datetime,
    normalize_and_hash_email,
    normalize_and_hash_phone,
    normalize_phone_e164,
    upload_completed_orders,
)
from orders.models import OfflineConversionLog

ADS = {
    'KEYCRM_API_KEY': 'key',
    'KEYCRM_COMPLETED_STATUS_ID': 12,
    'GOOGLE_ADS_CLIENT_ID': 'cid',
    'GOOGLE_ADS_CLIENT_SECRET': 'sec',
    'GOOGLE_ADS_REFRESH_TOKEN': 'ads-ref',
    'GOOGLE_ADS_CUSTOMER_ID': '111-222-3333',
    'GOOGLE_ADS_CONVERSION_ACTION_ID': '999',
    'GOOGLE_ADS_LOGIN_CUSTOMER_ID': '',
    'GOOGLE_DATAMANAGER_REFRESH_TOKEN': 'dm-ref',
    'GOOGLE_DATAMANAGER_VALIDATE_ONLY': False,
    'GOOGLE_DATAMANAGER_CONSENT_GRANTED': False,
}


def _sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _response(payload, status_code=200):
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode()
    response.url = 'https://example.test'
    response.encoding = 'utf-8'
    return response


def _order():
    moment = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    return {
        'id': 77,
        'source_uuid': '000077',
        'source_id': 22,
        'grand_total': '150.50',
        'closed_at': moment,
        'updated_at': moment,
        'buyer': {'phone': '0501112233', 'email': 'I.van@gmail.com'},
    }


@contextmanager
def _patched(router):
    with patch('orders.google_ads_conversions.requests.get', router.get), \
            patch('orders.google_ads_conversions.requests.post', router.post):
        yield router


class NormalizeTests(TestCase):
    def test_phone_variants_match_e164(self):
        expected = _sha('+380501112233')
        samples = (
            '0501112233',
            '380501112233',
            '+380501112233',
            '80501112233',
            '050 111 22 33',
            '+380 (50) 111-22-33',
            '050.111.22.33',
            '80 50 111-22-33',
            '501112233',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(normalize_phone_e164(sample), '+380501112233')
                self.assertEqual(normalize_and_hash_phone(sample), expected)

    def test_phone_keeps_international_and_rejects_garbage(self):
        self.assertEqual(normalize_phone_e164('+48 22 123-45-67'), '+48221234567')
        self.assertEqual(
            normalize_and_hash_phone('+48 22 123-45-67'),
            _sha('+48221234567'),
        )
        self.assertEqual(normalize_phone_e164('+14155552671'), '+14155552671')
        self.assertEqual(normalize_phone_e164('+12345678'), '+12345678')
        self.assertEqual(normalize_phone_e164('+' + ('1' * 15)), '+' + ('1' * 15))
        rejected = (
            '', None, 'abc', '+380123', '12345', '+1234567',
            '++380501112233', '+' + ('1' * 16), '+380' + ('1' * 12),
        )
        for sample in rejected:
            with self.subTest(sample=sample):
                self.assertIsNone(normalize_phone_e164(sample))
                self.assertIsNone(normalize_and_hash_phone(sample))

    def test_email_gmail_dots_plus_and_case(self):
        self.assertEqual(
            normalize_and_hash_email('I.van@gmail.com'),
            _sha('ivan@gmail.com'),
        )
        self.assertEqual(
            normalize_and_hash_email('I.van+Promo@gmail.com'),
            _sha('ivan@gmail.com'),
        )
        self.assertEqual(
            normalize_and_hash_email('I. van + Promo @ Gmail.com'),
            _sha('ivan@gmail.com'),
        )
        self.assertEqual(
            normalize_and_hash_email('I.van+Promo@googlemail.com'),
            _sha('ivan@googlemail.com'),
        )
        self.assertEqual(
            normalize_and_hash_email('A.B+C@Example.com'),
            _sha('a.b+c@example.com'),
        )
        self.assertEqual(
            normalize_and_hash_email('I.van@Example.com'),
            _sha('i.van@example.com'),
        )
        self.assertIsNone(normalize_and_hash_email('not-an-email'))
        self.assertIsNone(normalize_and_hash_email('+tag@gmail.com'))

    def test_kyiv_offset_has_colon(self):
        text = format_conversion_datetime(
            datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        self.assertRegex(text, r'^2026-01-15 \d{2}:\d{2}:\d{2}\+0[23]:00$')


@override_settings(**ADS)
class UploadTests(TestCase):
    def test_invalid_phone_is_not_added_and_value_is_non_negative(self):
        event = build_event({
            'id': 9,
            'grand_total': -2,
            'buyer': {'phone': 'abc', 'email': 'A.B+C@Example.com'},
        })
        self.assertEqual(event['userData']['userIdentifiers'], [
            {'emailAddress': _sha('a.b+c@example.com')},
        ])
        self.assertEqual(event['conversionValue'], 0.0)
        self.assertIn('T', event['eventTimestamp'])
        self.assertNotRegex(event['eventTimestamp'], r'\s')

    def test_skip_without_identifiers_logs_transaction_id_only(self):
        order = _order()
        order['id'] = 4242
        order['source_uuid'] = '004242'
        phone = '0509998877'
        email = 'hidden.person+tag@'
        order['buyer'] = {'phone': f'xx{phone}', 'email': email}
        secrets = (
            phone,
            email,
            _sha('+380509998877'),
            _sha('hidden.person@gmail.com'),
        )
        router = _Router([order])
        with _patched(router):
            with self.assertLogs('orders', level='INFO') as captured:
                summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 0)
        self.assertEqual(summary['skipped'], 1)
        self.assertEqual(summary['invalid'], 0)
        self.assertEqual(router.uploads, [])
        text = '\n'.join(captured.output)
        self.assertIn('transactionId=004242', text)
        for secret in secrets:
            self.assertNotIn(secret, text)

    def test_field_violation_retries_chunk_without_invalid_event(self):
        fields = (
            'events.events[3]',
            'events[3].userData.userIdentifiers[0].phoneNumber',
        )
        for field in fields:
            with self.subTest(field=field):
                OfflineConversionLog.objects.all().delete()
                router, secrets = _violation_router(field)
                with _patched(router):
                    with self.assertLogs('orders.google_ads_conversions', level='ERROR') as captured:
                        summary = upload_completed_orders()
                self._assert_violation_retry(
                    router, summary, secrets, captured.output, field,
                )
                log = OfflineConversionLog.objects.get(keycrm_order_id=103)
                self.assertEqual(log.status, OfflineConversionLog.STATUS_FAILED)
                self.assertEqual(log.error, f'invalid: {field}: User identifier rejected')
                for order_id in (100, 101, 102):
                    self.assertEqual(
                        OfflineConversionLog.objects.get(keycrm_order_id=order_id).status,
                        OfflineConversionLog.STATUS_UPLOADED,
                    )

    def test_validate_only_field_violation_retries_without_log(self):
        router, secrets = _violation_router('events.events[3]')
        with _patched(router):
            with self.assertLogs('orders.google_ads_conversions', level='ERROR') as captured:
                summary = upload_completed_orders(validate_only=True)
        self._assert_violation_retry(
            router, summary, secrets, captured.output, 'events.events[3]',
        )
        self.assertTrue(summary['validate_only'])
        self.assertIs(router.uploads[0]['validateOnly'], True)
        self.assertIs(router.uploads[1]['validateOnly'], True)
        self.assertFalse(OfflineConversionLog.objects.exists())

    def _assert_violation_retry(self, router, summary, secrets, lines, field):
        self.assertEqual(summary['invalid'], 1)
        self.assertEqual(summary['uploaded'], 3)
        self.assertEqual(summary['failed'], 0)
        self.assertEqual(len(router.uploads), 2)
        self.assertEqual(len(router.token_bodies), 1)
        self.assertIs(router.uploads[0]['validateOnly'], summary['validate_only'])
        self.assertIs(router.uploads[1]['validateOnly'], summary['validate_only'])
        self.assertEqual(
            [item['transactionId'] for item in router.uploads[0]['events']],
            ['000100', '000101', '000102', '000103'],
        )
        self.assertEqual(
            [item['transactionId'] for item in router.uploads[1]['events']],
            ['000100', '000101', '000102'],
        )
        text = '\n'.join(lines)
        self.assertIn(f'field={field}', text)
        self.assertIn('description=User identifier rejected', text)
        for secret in secrets:
            self.assertNotIn(secret, text)


def _violation_router(field):
    phone = '0501112233'
    email = 'I.van@gmail.com'
    secrets = (phone, email, _sha('+380501112233'), _sha('ivan@gmail.com'))
    payload = {
        'error': {
            'code': 400,
            'message': 'Request contains an invalid argument.',
            'status': 'INVALID_ARGUMENT',
            'details': [{
                'fieldViolations': [{
                    'field': field,
                    'description': 'User identifier rejected',
                }],
                'debugInfo': '|'.join(secrets),
            }],
        },
    }
    moment = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    orders = [{
        'id': 100 + index,
        'source_uuid': f'{100 + index:06d}',
        'source_id': 22,
        'grand_total': '10',
        'closed_at': moment,
        'updated_at': moment,
        'buyer': {'phone': phone, 'email': email},
    } for index in range(4)]
    router = _Router(orders, ingest_responses=[
        (400, payload),
        (200, {'requestId': 'req-ok'}),
    ])
    return router, secrets


class _Router:
    def __init__(
        self, orders, google_payload=None, google_status=200, reject_dated=False,
        ingest_responses=None,
    ):
        self.orders = orders
        self.google_payload = google_payload if google_payload is not None else {
            'requestId': 'req-1',
            'fieldWarnings': [{'field': 'events[0].currency'}],
        }
        self.google_status = google_status
        self.reject_dated = reject_dated
        self.ingest_responses = ingest_responses
        self.uploads = []
        self.headers = {}
        self.gets = []
        self.urls = []
        self.token_urls = []
        self.token_bodies = []

    def get(self, url, **kwargs):
        params = kwargs.get('params') or {}
        self.gets.append(params)
        if self.reject_dated and 'filter[updated_between]' in params:
            return _response({'message': 'bad filter'}, 400)
        return _response({'data': self.orders, 'last_page': 1})

    def post(self, url, **kwargs):
        if 'oauth2.googleapis.com' in url:
            self.token_urls.append(url)
            self.token_bodies.append(kwargs.get('data') or {})
            return _response({'access_token': 'token'})
        self.urls.append(url)
        self.headers = kwargs.get('headers') or {}
        self.uploads.append(kwargs.get('json') or {})
        if self.ingest_responses is not None:
            if not self.ingest_responses:
                return _response({'error': {'message': 'unexpected ingest'}}, 500)
            status, payload = self.ingest_responses.pop(0)
            return _response(payload, status)
        return _response(self.google_payload, self.google_status)
