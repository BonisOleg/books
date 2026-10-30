import os
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from orders.google_ads_conversions import (
    _lookback,
    _window,
    build_conversion,
    build_event,
    clamp_lookback_days,
    upload_completed_orders,
)
from orders.models import OfflineConversionLog
from orders.tests.test_google_ads_conversions import (
    ADS,
    _Router,
    _order,
    _patched,
    _sha,
)

TOKEN_URL = 'https://oauth2.googleapis.com/token'
INGEST_URL = 'https://datamanager.googleapis.com/v1/events:ingest'


class LookbackTests(TestCase):
    def test_default_is_10_days(self):
        with patch.dict(os.environ):
            os.environ.pop('KEYCRM_CONVERSION_DAYS', None)
            os.environ.pop('LOOKBACK_DAYS', None)
            with override_settings(KEYCRM_CONVERSION_DAYS=10, LOOKBACK_DAYS=None):
                self.assertEqual(clamp_lookback_days(), 10)
                self.assertEqual(_lookback(), timedelta(days=10))
                start, end = _window()
        self.assertEqual(end - start, timedelta(days=10))

    def test_days_clamped_to_7_14(self):
        self.assertEqual(clamp_lookback_days(3), 7)
        self.assertEqual(clamp_lookback_days(7), 7)
        self.assertEqual(clamp_lookback_days(14), 14)
        self.assertEqual(clamp_lookback_days(30), 14)

    @override_settings(KEYCRM_CONVERSION_DAYS=12)
    def test_settings_override_env(self):
        with patch.dict(os.environ, {'KEYCRM_CONVERSION_DAYS': '8'}):
            self.assertEqual(clamp_lookback_days(), 12)

    def test_invalid_falls_back_then_clamped(self):
        invalid = ('', '   ', 'nope', '12.5')
        for raw in invalid:
            with self.subTest(source='env', raw=raw):
                with patch.dict(os.environ, {'KEYCRM_CONVERSION_DAYS': raw}):
                    with override_settings(KEYCRM_CONVERSION_DAYS=None, LOOKBACK_DAYS=None):
                        self.assertEqual(clamp_lookback_days(), 10)
        with override_settings(KEYCRM_CONVERSION_DAYS=0):
            self.assertEqual(clamp_lookback_days(), 7)
        with override_settings(KEYCRM_CONVERSION_DAYS=-1):
            self.assertEqual(clamp_lookback_days(), 7)


@override_settings(**ADS)
class UploadTests(TestCase):
    def test_payload_and_dedup(self):
        router = _Router([_order()])
        with _patched(router):
            first = upload_completed_orders()
            second = upload_completed_orders()

        self.assertEqual(first['uploaded'], 1)
        self.assertEqual(first['failed'], 0)
        self.assertEqual(first['invalid'], 0)
        self.assertFalse(first['validate_only'])
        self.assertEqual(second['uploaded'], 0)
        self.assertEqual(second['skipped'], 1)
        self.assertEqual(router.urls, [INGEST_URL])
        self.assertEqual(set(router.headers), {'Authorization', 'Content-Type'})
        self.assertEqual(router.headers['Authorization'], 'Bearer token')
        self.assertNotIn('developer-token', router.headers)
        self.assertNotIn('login-customer-id', router.headers)
        self.assertEqual(router.token_bodies[0]['client_id'], 'cid')
        self.assertEqual(router.token_bodies[0]['client_secret'], 'sec')
        self.assertEqual(router.token_bodies[0]['refresh_token'], 'dm-ref')
        self.assertEqual(router.token_bodies[0]['grant_type'], 'refresh_token')

        body = router.uploads[0]
        self.assertEqual(body['encoding'], 'HEX')
        self.assertIs(body['validateOnly'], False)
        self.assertNotIn('consent', body)
        destination = body['destinations'][0]
        self.assertEqual(destination['reference'], 'keycrm')
        self.assertNotIn('loginAccount', destination)
        self.assertEqual(destination['operatingAccount'], {
            'accountType': 'GOOGLE_ADS',
            'accountId': '1112223333',
        })
        self.assertEqual(destination['productDestinationId'], '999')

        event = body['events'][0]
        self.assertEqual(event['transactionId'], '000077')
        self.assertEqual(event['currency'], 'UAH')
        self.assertEqual(event['conversionValue'], 150.5)
        self.assertEqual(event['eventSource'], 'WEB')
        self.assertNotIn('adIdentifiers', event)
        self.assertEqual(event['userData']['userIdentifiers'], [
            {'phoneNumber': _sha('+380501112233')},
            {'emailAddress': _sha('ivan@gmail.com')},
        ])
        self.assertRegex(
            event['eventTimestamp'],
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$',
        )
        self.assertEqual(
            OfflineConversionLog.objects.get(keycrm_order_id=77).status,
            OfflineConversionLog.STATUS_UPLOADED,
        )

    def test_skips_order_without_identifiers(self):
        order = _order()
        order['buyer'] = {'phone': '123', 'email': ''}
        router = _Router([order])
        with _patched(router):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 0)
        self.assertEqual(summary['skipped'], 1)
        self.assertEqual(router.uploads, [])
        self.assertFalse(OfflineConversionLog.objects.exists())

    def test_order_with_only_gclid_is_uploaded(self):
        order = _order()
        order['buyer'] = {}
        order['marketing'] = {'utm': {'gclid': 'CjwKCAjw'}}
        router = _Router([order])
        with _patched(router):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 1)
        event = router.uploads[0]['events'][0]
        self.assertEqual(event['adIdentifiers'], {'gclid': 'CjwKCAjw'})
        self.assertNotIn('userData', event)

    def test_duplicate_transaction_is_treated_as_uploaded(self):
        messages = (
            'The transactionId already exists.',
            'DUPLICATE_TRANSACTION_ID',
        )
        for message in messages:
            with self.subTest(message=message):
                OfflineConversionLog.objects.all().delete()
                router = _Router([_order()], google_status=400, google_payload={
                    'error': {'message': message},
                })
                with _patched(router):
                    first = upload_completed_orders()
                    second = upload_completed_orders()
                self.assertEqual(first['uploaded'], 1)
                self.assertEqual(first['failed'], 0)
                self.assertEqual(second['skipped'], 1)
                self.assertEqual(len(router.uploads), 1)
                self.assertEqual(
                    OfflineConversionLog.objects.get(keycrm_order_id=77).status,
                    OfflineConversionLog.STATUS_UPLOADED,
                )

    def test_http_error_marks_failed_and_retries(self):
        router = _Router([_order()], google_status=400, google_payload={
            'error': {'message': 'Invalid productDestinationId'},
        })
        with _patched(router):
            first = upload_completed_orders()
            second = upload_completed_orders()
        self.assertEqual(first['failed'], 1)
        self.assertEqual(first['uploaded'], 0)
        self.assertEqual(second['failed'], 1)
        self.assertEqual(len(router.uploads), 2)
        log = OfflineConversionLog.objects.get(keycrm_order_id=77)
        self.assertEqual(log.status, OfflineConversionLog.STATUS_FAILED)

    @override_settings(GOOGLE_ADS_LOGIN_CUSTOMER_ID='999-111-2222')
    def test_login_account_only_when_set(self):
        router = _Router([_order()])
        with _patched(router):
            upload_completed_orders()
        destination = router.uploads[0]['destinations'][0]
        self.assertEqual(destination['loginAccount'], {
            'accountType': 'GOOGLE_ADS',
            'accountId': '9991112222',
        })
        self.assertNotIn('login-customer-id', router.headers)
        self.assertNotIn('developer-token', router.headers)

    @override_settings(GOOGLE_DATAMANAGER_CONSENT_GRANTED=True)
    def test_consent_only_when_enabled(self):
        router = _Router([_order()])
        with _patched(router):
            upload_completed_orders()
        self.assertEqual(router.uploads[0]['consent'], {
            'adUserData': 'CONSENT_GRANTED',
            'adPersonalization': 'CONSENT_GRANTED',
        })

    def test_validate_only_flag_does_not_write_log(self):
        router = _Router([_order()])
        with _patched(router):
            summary = upload_completed_orders(validate_only=True)
            again = upload_completed_orders()
        self.assertTrue(summary['validate_only'])
        self.assertIs(router.uploads[0]['validateOnly'], True)
        self.assertIs(router.uploads[1]['validateOnly'], False)
        self.assertEqual(
            OfflineConversionLog.objects.get(keycrm_order_id=77).status,
            OfflineConversionLog.STATUS_UPLOADED,
        )

    @override_settings(GOOGLE_DATAMANAGER_VALIDATE_ONLY=True)
    def test_validate_only_from_setting(self):
        router = _Router([_order()])
        with _patched(router):
            summary = upload_completed_orders()
        self.assertTrue(summary['validate_only'])
        self.assertIs(router.uploads[0]['validateOnly'], True)
        self.assertFalse(OfflineConversionLog.objects.exists())

    @override_settings(GOOGLE_DATAMANAGER_VALIDATE_ONLY=True)
    def test_explicit_false_overrides_setting(self):
        router = _Router([_order()])
        with _patched(router):
            summary = upload_completed_orders(validate_only=False)
        self.assertFalse(summary['validate_only'])
        self.assertIs(router.uploads[0]['validateOnly'], False)
        self.assertEqual(
            OfflineConversionLog.objects.get(keycrm_order_id=77).status,
            OfflineConversionLog.STATUS_UPLOADED,
        )

    def test_validate_only_http_error_does_not_write_log(self):
        router = _Router([_order()], google_status=400, google_payload={
            'error': {'message': 'permission denied'},
        })
        with _patched(router):
            summary = upload_completed_orders(validate_only=True)
        self.assertEqual(summary['failed'], 1)
        self.assertFalse(OfflineConversionLog.objects.exists())

    def test_date_filter_fallback(self):
        router = _Router([_order()], reject_dated=True)
        with _patched(router):
            summary = upload_completed_orders()
        self.assertEqual(summary['uploaded'], 1)
        self.assertGreaterEqual(len(router.gets), 2)
        self.assertNotIn('filter[updated_between]', router.gets[-1])

    def test_build_event_keeps_source_clock(self):
        self.assertIsNone(build_event({'id': 1, 'buyer': {}}))
        self.assertIsNone(build_event({'id': 1, 'buyer': {}, 'gclid': '   '}))
        event = build_conversion(
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
            event['eventTimestamp'],
            r'^2026-10-20T12:00:00\+0[23]:00$',
        )
        self.assertNotRegex(event['eventTimestamp'], r'\s')
        self.assertEqual(event['userData']['userIdentifiers'], [
            {'emailAddress': _sha('a@b.com')},
        ])
        gclid_event = build_event({
            'id': 8,
            'buyer': {},
            'marketing': {'utm': {'utm_source': 'google', 'gclid': 'from-utm'}},
        })
        self.assertEqual(gclid_event['adIdentifiers'], {'gclid': 'from-utm'})
        self.assertNotIn('userData', gclid_event)

    @override_settings(
        GOOGLE_DATAMANAGER_REFRESH_TOKEN='',
        GOOGLE_ADS_REFRESH_TOKEN='ads-only-ref',
    )
    def test_ads_refresh_token_alone_is_not_configured(self):
        with patch('orders.google_ads_conversions.requests.get') as get_mock, \
                patch('orders.google_ads_conversions.requests.post') as post_mock:
            summary = upload_completed_orders()
        self.assertTrue(summary['not_configured'])
        self.assertEqual(summary['invalid'], 0)
        self.assertIn('GOOGLE_DATAMANAGER_REFRESH_TOKEN', summary['missing'])
        get_mock.assert_not_called()
        post_mock.assert_not_called()

    @override_settings(
        GOOGLE_ADS_CLIENT_ID='ads-cid',
        GOOGLE_ADS_CLIENT_SECRET='ads-sec',
        GOOGLE_ADS_REFRESH_TOKEN='ads-ref',
        GOOGLE_DATAMANAGER_REFRESH_TOKEN='dm-ref-only',
    )
    def test_token_post_uses_datamanager_refresh_and_ads_client(self):
        router = _Router([_order()])
        with _patched(router):
            summary = upload_completed_orders()
        self.assertFalse(summary['not_configured'])
        self.assertEqual(router.token_urls, [TOKEN_URL])
        sent = router.token_bodies[0]
        self.assertEqual(sent['client_id'], 'ads-cid')
        self.assertEqual(sent['client_secret'], 'ads-sec')
        self.assertEqual(sent['refresh_token'], 'dm-ref-only')


@override_settings(**ADS)
class CommandTests(TestCase):
    def test_command_prints_summary(self):
        router = _Router([_order()])
        with _patched(router):
            call_command('upload_keycrm_conversions')
        self.assertEqual(router.urls, [INGEST_URL])
        self.assertIs(router.uploads[0]['validateOnly'], False)

    @override_settings(
        GOOGLE_DATAMANAGER_REFRESH_TOKEN='',
        GOOGLE_ADS_REFRESH_TOKEN='',
    )
    def test_command_noop_without_credentials(self):
        with patch('orders.google_ads_conversions.requests.get') as get_mock:
            call_command('upload_keycrm_conversions')
        get_mock.assert_not_called()

    def test_command_continues_on_http_error(self):
        router = _Router([_order()], google_status=401)
        out = StringIO()
        with _patched(router):
            call_command('upload_keycrm_conversions', stdout=out)
        self.assertIn('помилки: 1', out.getvalue())
        log = OfflineConversionLog.objects.get(keycrm_order_id=77)
        self.assertEqual(log.status, OfflineConversionLog.STATUS_FAILED)

    def test_command_validate_flags_do_not_write_log(self):
        for flag in ('--validate-only', '--dry-run'):
            with self.subTest(flag=flag):
                OfflineConversionLog.objects.all().delete()
                router = _Router([_order()])
                out = StringIO()
                with _patched(router):
                    call_command('upload_keycrm_conversions', flag, stdout=out)
                self.assertIn('перевірки', out.getvalue())
                self.assertIs(router.uploads[0]['validateOnly'], True)
                self.assertFalse(OfflineConversionLog.objects.exists())

