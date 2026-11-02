from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings

from shipping.np_ttn import MSG_NO_KEY, MSG_UNAVAILABLE, create_ttn
from shipping.tests.factories import (
    LOC_MEM,
    json_response,
    order,
    origin,
    ttn_api_success,
    ttn_settings,
)


def _post_returning(payload):
    def _post(url, json=None, timeout=None):
        return json_response(payload)
    return _post


@override_settings(NOVAPOSHTA_API_KEY='np-test-key')
class CreateTtnTests(TestCase):
    def setUp(self):
        self.origin = origin()
        self.settings = ttn_settings()
        self.order = order(shipment_origin=self.origin)

    def test_success_stores_number_and_ignores_warnings_in_error(self):
        payload = ttn_api_success(warnings=['дрібне попередження'])
        with patch('shipping.np_ttn.requests.post', side_effect=_post_returning(payload)) as post:
            result = create_ttn(self.order.pk)
        self.order.refresh_from_db()
        self.assertEqual(post.call_count, 1)
        body = post.call_args.kwargs['json']
        self.assertEqual(body['modelName'], 'InternetDocument')
        self.assertEqual(body['calledMethod'], 'save')
        self.assertEqual(body['apiKey'], 'np-test-key')
        self.assertEqual(body['methodProperties']['Cost'], '150.00')
        self.assertEqual(result.ttn_number, '20450123456789')
        self.assertEqual(self.order.ttn_number, '20450123456789')
        self.assertEqual(self.order.ttn_ref, 'ref-ttn')
        self.assertEqual(self.order.ttn_delivery_cost, 68)
        self.assertEqual(self.order.ttn_status, 'created')
        self.assertEqual(self.order.ttn_error, '')
        self.assertIsNotNone(self.order.ttn_created_at)

    def test_idempotent_when_number_exists(self):
        with patch('shipping.np_ttn.requests.post', side_effect=_post_returning(ttn_api_success())) as post:
            create_ttn(self.order.pk)
            second = create_ttn(self.order.pk)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(second.ttn_number, '20450123456789')

    def test_retries_after_error_without_number(self):
        calls = {'n': 0}

        def post(url, json=None, timeout=None):
            calls['n'] += 1
            if calls['n'] == 1:
                raise requests.Timeout('slow')
            return json_response(ttn_api_success())

        with patch('shipping.np_ttn.requests.post', side_effect=post):
            create_ttn(self.order.pk)
            create_ttn(self.order.pk)
        self.order.refresh_from_db()
        self.assertEqual(self.order.ttn_number, '20450123456789')
        self.assertEqual(self.order.ttn_error, '')

    def test_mapped_api_error_is_ukrainian(self):
        payload = {
            'success': False,
            'data': [],
            'errors': ['Weight is empty'],
            'errorCodes': ['20000300412'],
            'warnings': [],
        }
        with patch('shipping.np_ttn.requests.post', side_effect=_post_returning(payload)):
            create_ttn(self.order.pk)
        self.order.refresh_from_db()
        self.assertEqual(self.order.ttn_status, 'error')
        self.assertEqual(self.order.ttn_number, '')
        self.assertIn('Некоректна вага відправлення', self.order.ttn_error)
        self.assertNotIn('Weight is empty', self.order.ttn_error)

    def test_unmapped_error_falls_back_to_raw_text(self):
        payload = {
            'success': False,
            'data': [],
            'errors': ['Сирий текст НП'],
            'errorCodes': ['999000'],
            'warnings': ['Уточніть опис'],
        }
        with patch('shipping.np_ttn.requests.post', side_effect=_post_returning(payload)):
            create_ttn(self.order.pk)
        self.order.refresh_from_db()
        self.assertIn('Сирий текст НП', self.order.ttn_error)
        self.assertIn('Попередження: Уточніть опис', self.order.ttn_error)

    def test_network_errors(self):
        for exc in (requests.Timeout('slow'), requests.ConnectionError('down')):
            with self.subTest(exc=type(exc).__name__):
                self.order.ttn_error = ''
                self.order.ttn_status = ''
                self.order.ttn_number = ''
                self.order.save(update_fields=['ttn_error', 'ttn_status', 'ttn_number'])
                with patch('shipping.np_ttn.requests.post', side_effect=exc):
                    create_ttn(self.order.pk)
                self.order.refresh_from_db()
                self.assertEqual(self.order.ttn_error, MSG_UNAVAILABLE)

    def test_api_key_is_not_stored_or_logged(self):
        payload = {
            'success': False,
            'data': [],
            'errors': ['bad np-test-key'],
            'errorCodes': ['999000'],
            'warnings': [],
        }
        with patch('shipping.np_ttn.requests.post', side_effect=_post_returning(payload)):
            with self.assertLogs('shipping.np_ttn', level='WARNING') as captured:
                create_ttn(self.order.pk)
        self.order.refresh_from_db()
        self.assertNotIn('np-test-key', self.order.ttn_error)
        self.assertIn('***', self.order.ttn_error)
        self.assertNotIn('np-test-key', '\n'.join(captured.output))

    def test_missing_origin_does_not_call_api(self):
        self.order.shipment_origin = None
        self.order.save(update_fields=['shipment_origin'])
        with patch('shipping.np_ttn.requests.post') as post:
            create_ttn(self.order.pk)
        post.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.ttn_error, 'Не обрано точку відправки')


@override_settings(NOVAPOSHTA_API_KEY='')
class CreateTtnWithoutKeyTests(TestCase):
    def test_no_key_skips_request(self):
        row = order(shipment_origin=origin())
        ttn_settings()
        with patch('shipping.np_ttn.requests.post') as post:
            create_ttn(row.pk)
        post.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.ttn_error, MSG_NO_KEY)
        self.assertEqual(row.ttn_status, 'error')
        self.assertEqual(row.ttn_number, '')


@override_settings(NOVAPOSHTA_API_KEY='np-test-key', CACHES=LOC_MEM)
class SenderCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.origin = origin(name='Склад', city_ref='city-1', warehouse_ref='wh-1')
        ttn_settings(sender_ref='', contact_sender_ref='', sender_phone='+380671112233')

    def test_counterparties_are_cached(self):
        methods = []

        def post(url, json=None, timeout=None):
            method = json['calledMethod']
            methods.append(method)
            if method == 'getCounterparties':
                return json_response({
                    'success': True,
                    'data': [{
                        'Ref': 'sender-auto',
                        'CounterpartyType': 'Organization',
                    }],
                    'errors': [],
                    'errorCodes': [],
                    'warnings': [],
                })
            if method == 'getCounterpartyContactPersons':
                return json_response({
                    'success': True,
                    'data': [{'Ref': 'contact-auto', 'Phones': '380671112233'}],
                    'errors': [],
                    'errorCodes': [],
                    'warnings': [],
                })
            return json_response(ttn_api_success(number=f'2045000000000{len(methods)}'))

        first = order(shipment_origin=self.origin, warehouse='Відділення №1', warehouse_ref='r1')
        second = order(shipment_origin=self.origin, warehouse='Відділення №2', warehouse_ref='r2')
        with patch('shipping.np_ttn.requests.post', side_effect=post):
            create_ttn(first.pk)
            create_ttn(second.pk)
        self.assertEqual(methods, [
            'getCounterparties',
            'getCounterpartyContactPersons',
            'save',
            'save',
        ])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.ttn_number)
        self.assertTrue(second.ttn_number)
        self.assertNotEqual(first.ttn_number, second.ttn_number)

    def test_blank_sender_type_picks_organization(self):
        from shipping.models import NPTTNSettings

        field = NPTTNSettings._meta.get_field('sender_type')
        self.assertEqual(field.default, NPTTNSettings.SENDER_ORGANIZATION)
        ttn_settings(sender_ref='', contact_sender_ref='', sender_phone='+380671112233', sender_type='')
        seen = {}

        def post(url, json=None, timeout=None):
            method = json['calledMethod']
            if method == 'getCounterparties':
                return json_response({
                    'success': True,
                    'data': [
                        {'Ref': 'private-ref', 'CounterpartyType': 'PrivatePerson'},
                        {'Ref': 'org-ref', 'CounterpartyType': 'Organization'},
                    ],
                    'errors': [],
                    'errorCodes': [],
                    'warnings': [],
                })
            if method == 'getCounterpartyContactPersons':
                seen['contact_for'] = json['methodProperties']['Ref']
                return json_response({
                    'success': True,
                    'data': [{'Ref': 'contact-org', 'Phones': '380671112233'}],
                    'errors': [],
                    'errorCodes': [],
                    'warnings': [],
                })
            seen['sender'] = json['methodProperties']['Sender']
            return json_response(ttn_api_success(number='20450000000999'))

        row = order(shipment_origin=self.origin, warehouse='Відділення №3', warehouse_ref='r3')
        with patch('shipping.np_ttn.requests.post', side_effect=post):
            create_ttn(row.pk)
        self.assertEqual(seen['contact_for'], 'org-ref')
        self.assertEqual(seen['sender'], 'org-ref')
        row.refresh_from_db()
        self.assertEqual(row.ttn_number, '20450000000999')
