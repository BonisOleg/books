from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone as dj_timezone

from orders.google_ads_conversions import upload_completed_orders
from orders.models import OfflineConversionLog
from orders.tests.test_google_ads_conversions import ADS, _Router, _order, _patched

FAILED = OfflineConversionLog.STATUS_FAILED
UPLOADED = OfflineConversionLog.STATUS_UPLOADED


def _ready(order_id, *, status_id=12, closed_at=None):
    order = _order()
    order['id'] = order_id
    order['status_id'] = status_id
    if closed_at is not None:
        for key in ('closed_at', 'status_changed_at', 'updated_at', 'created_at'):
            order[key] = closed_at
    return order


def _failed(order_id, attempts=1, **extra):
    return OfflineConversionLog.objects.create(
        keycrm_order_id=order_id,
        status=FAILED,
        attempts=attempts,
        error='old',
        **extra,
    )


@override_settings(**ADS)
class RetryTests(TestCase):
    def test_uploaded_orders_are_not_resent(self):
        for order_id in (11, 12, 13):
            OfflineConversionLog.objects.create(keycrm_order_id=order_id, status=UPLOADED)
        orders = []
        for order_id in (11, 12, 13, 14):
            item = _order()
            item['id'] = order_id
            orders.append(item)
        router = _Router(orders)
        with _patched(router):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 1)
        self.assertEqual(summary['skipped'], 3)
        self.assertEqual(summary['retried'], 0)
        self.assertEqual(
            [item['transactionId'] for item in router.uploads[0]['events']],
            ['keycrm-14'],
        )
        self.assertEqual(router.by_id, [])
        for order_id in (11, 12, 13):
            self.assertEqual(
                OfflineConversionLog.objects.get(keycrm_order_id=order_id).status,
                UPLOADED,
            )

    @override_settings(KEYCRM_MAX_RETRY_ATTEMPTS=3)
    def test_failed_outside_window_is_fetched_by_id(self):
        fresh = (datetime.now(timezone.utc) - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
        old = (datetime.now(timezone.utc) - timedelta(days=91)).strftime('%Y-%m-%d %H:%M:%S')
        stale = _ready(57, closed_at=fresh)
        stale['closed_at'] = old
        undated = _ready(58, closed_at=fresh)
        for key in ('closed_at', 'updated_at', 'status_changed_at', 'created_at'):
            undated.pop(key, None)
        orders = {
            55: _ready(55, closed_at=fresh),
            56: _ready(56, status_id=3, closed_at=fresh),
            57: stale,
            58: undated,
            11: _ready(11, closed_at=fresh),
            59: _ready(59, closed_at=fresh),
        }
        _failed(55)
        _failed(56)
        _failed(57)
        _failed(58)
        OfflineConversionLog.objects.create(keycrm_order_id=11, status=UPLOADED)
        _failed(59, attempts=3)
        router = _Router([_order()], by_id_orders=orders)
        with _patched(router):
            summary = upload_completed_orders()

        self.assertEqual(router.by_id, [55, 56, 57, 58])
        self.assertEqual(summary['retried'], 1)
        self.assertEqual(summary['uploaded'], 2)
        self.assertEqual(
            [item['transactionId'] for item in router.uploads[0]['events']],
            ['keycrm-77', 'keycrm-55'],
        )
        for url, params in zip(router.get_urls, router.gets):
            if '/order/' in url:
                self.assertEqual(params.get('include'), 'buyer')
        sent = OfflineConversionLog.objects.get(keycrm_order_id=55)
        self.assertEqual(sent.status, UPLOADED)
        self.assertEqual(sent.attempts, 1)
        for order_id in (56, 57, 58, 59):
            log = OfflineConversionLog.objects.get(keycrm_order_id=order_id)
            self.assertEqual(log.status, FAILED)
            self.assertEqual(log.attempts, 3 if order_id == 59 else 1)
            self.assertIsNone(log.last_attempt_at)

    @override_settings(KEYCRM_RETRY_FETCH_LIMIT=1)
    def test_retry_batch_is_limited(self):
        moment = dj_timezone.now()
        _failed(301, last_attempt_at=moment)
        _failed(302)
        _failed(303, last_attempt_at=moment - timedelta(hours=5))
        router = _Router([], by_id_orders={
            301: _ready(301),
            302: _ready(302),
            303: _ready(303),
        })
        with _patched(router):
            summary = upload_completed_orders()
        self.assertEqual(router.by_id, [302])
        self.assertEqual(summary['fetched'], 0)
        self.assertEqual(summary['retried'], 1)
        self.assertEqual(summary['uploaded'], 1)
        self.assertEqual(router.uploads[0]['events'][0]['transactionId'], 'keycrm-302')
        self.assertEqual(OfflineConversionLog.objects.get(keycrm_order_id=301).status, FAILED)
        self.assertEqual(OfflineConversionLog.objects.get(keycrm_order_id=303).status, FAILED)

    @override_settings(KEYCRM_MAX_RETRY_ATTEMPTS=2)
    def test_attempt_cap_skips_failed_order_still_in_window(self):
        _failed(77, attempts=2)
        router = _Router([_order()])
        with _patched(router):
            with self.assertLogs('orders.google_ads_conversions2', level='INFO') as captured:
                summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 0)
        self.assertEqual(summary['skipped'], 1)
        self.assertEqual(summary['retried'], 0)
        self.assertEqual(router.uploads, [])
        self.assertEqual(router.by_id, [])
        self.assertIn('вичерпано спроби', '\n'.join(captured.output))
        log = OfflineConversionLog.objects.get(keycrm_order_id=77)
        self.assertEqual(log.status, FAILED)
        self.assertEqual(log.attempts, 2)

    def test_successful_resend_keeps_attempt_count(self):
        stamp = dj_timezone.now() - timedelta(days=1)
        _failed(77, attempts=4, last_attempt_at=stamp)
        router = _Router([_order()])
        with _patched(router):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 1)
        self.assertEqual(router.by_id, [])
        self.assertEqual(router.uploads[0]['events'][0]['transactionId'], 'keycrm-77')
        log = OfflineConversionLog.objects.get(keycrm_order_id=77)
        self.assertEqual(log.status, UPLOADED)
        self.assertEqual(log.attempts, 4)
        self.assertEqual(log.last_attempt_at, stamp)
        self.assertEqual(log.error, '')
        self.assertIsNotNone(log.uploaded_at)

    def test_retry_keycrm_error_does_not_block_window(self):
        _failed(55)
        router = _Router([_order()], by_id_orders={55: (500, {'message': 'down'})})
        with _patched(router):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 1)
        self.assertEqual(summary['retried'], 0)
        self.assertEqual(router.uploads[0]['events'][0]['transactionId'], 'keycrm-77')
        log = OfflineConversionLog.objects.get(keycrm_order_id=55)
        self.assertEqual(log.status, FAILED)
        self.assertEqual(log.attempts, 1)

    def test_validate_only_does_not_increment_attempts(self):
        _failed(77, attempts=3)
        router = _Router([_order()], google_status=400, google_payload={
            'error': {'message': 'There was a problem with the request.'},
        })
        with _patched(router):
            with self.assertRaises(requests.HTTPError):
                upload_completed_orders(validate_only=True)
        log = OfflineConversionLog.objects.get(keycrm_order_id=77)
        self.assertEqual(log.status, FAILED)
        self.assertEqual(log.attempts, 3)
        self.assertEqual(log.error, 'old')
        self.assertIsNone(log.last_attempt_at)


@override_settings(**ADS)
class OrderIdCommandTests(TestCase):
    def test_order_ids_ignore_window_and_attempt_cap(self):
        OfflineConversionLog.objects.create(keycrm_order_id=6, status=UPLOADED)
        _failed(7, attempts=100)
        nested = _ready(8)
        nested.pop('status_id')
        nested['status'] = {'id': 12}
        router = _Router([_order()], by_id_orders={
            6: _ready(6),
            7: _ready(7),
            8: nested,
            9: _ready(9, status_id=4),
        })
        out = StringIO()
        with _patched(router):
            call_command(
                'upload_keycrm_conversions',
                '--order-ids', '6, 7,8,9,8',
                stdout=out,
            )
        self.assertEqual(router.by_id, [6, 7, 8, 9])
        self.assertFalse(any(str(url).rstrip('/').endswith('/order') for url in router.get_urls))
        self.assertEqual(
            [item['transactionId'] for item in router.uploads[0]['events']],
            ['keycrm-7', 'keycrm-8'],
        )
        for url, params in zip(router.get_urls, router.gets):
            self.assertEqual(params.get('include'), 'buyer')
        text = out.getvalue()
        self.assertIn('ID: 6,7,8,9', text)
        self.assertIn('Отримано: 4', text)
        self.assertIn('повторів: 0', text)
        self.assertIn('вивантажено: 2', text)
        self.assertIn('пропущено: 2', text)
        self.assertIn('невалідні: 0', text)
        self.assertEqual(OfflineConversionLog.objects.get(keycrm_order_id=6).status, UPLOADED)
        resent = OfflineConversionLog.objects.get(keycrm_order_id=7)
        self.assertEqual(resent.status, UPLOADED)
        self.assertEqual(resent.attempts, 100)
        self.assertFalse(OfflineConversionLog.objects.filter(keycrm_order_id=9).exists())

    def test_order_ids_validate_only_prints_summary_without_log(self):
        router = _Router([], by_id_orders={8: _ready(8)})
        out = StringIO()
        with _patched(router):
            call_command(
                'upload_keycrm_conversions',
                '--order-ids', '8',
                '--validate-only',
                stdout=out,
            )
        self.assertFalse(OfflineConversionLog.objects.exists())
        self.assertIs(router.uploads[0]['validateOnly'], True)
        text = out.getvalue()
        self.assertIn('перевірки', text)
        self.assertIn('Отримано: 1', text)
        self.assertIn('вивантажено: 1', text)
        self.assertEqual(router.by_id, [8])

    def test_order_ids_validate_only_http_error_does_not_write_log(self):
        router = _Router([], by_id_orders={8: _ready(8)}, google_status=400, google_payload={
            'error': {'message': 'There was a problem with the request.'},
        })
        with _patched(router):
            with self.assertRaises(CommandError):
                call_command(
                    'upload_keycrm_conversions',
                    '--order-ids', '8',
                    '--validate-only',
                )
        self.assertFalse(OfflineConversionLog.objects.exists())
        self.assertIs(router.uploads[0]['validateOnly'], True)

    def test_missing_order_is_skipped(self):
        router = _Router([], by_id_orders={6: _ready(6)})
        out = StringIO()
        with _patched(router):
            call_command('upload_keycrm_conversions', '--order-ids', '6,99', stdout=out)
        self.assertEqual(router.by_id, [6, 99])
        text = out.getvalue()
        self.assertIn('Отримано: 1', text)
        self.assertIn('пропущено: 1', text)
        self.assertIn('вивантажено: 1', text)

    def test_bad_order_ids_do_not_call_network(self):
        with patch('orders.google_ads_conversions.requests.get') as get_mock, \
                patch('orders.google_ads_conversions.requests.post') as post_mock:
            with self.assertRaises(CommandError):
                call_command('upload_keycrm_conversions', '--order-ids', '6,nope')
            with self.assertRaises(CommandError):
                call_command('upload_keycrm_conversions', '--order-ids', '0')
        get_mock.assert_not_called()
        post_mock.assert_not_called()
