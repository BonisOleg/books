from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings

from orders.models import Order
from shipping.models import ShipmentOrigin
from shipping.origin_refs import pick_warehouse
from shipping.tests.factories import json_response, order

SEEDED_NAMES = [
    'Хмельницький №7',
    'Київ №129',
    'Київ, адресний забір, вул. Золотоустівська 10-12',
    'Дніпро №64',
    'Вишгород №1',
    'Кагарлик №1',
    'Зимна Вода №1',
]

CATALOG = {
    'Хмельницький': ('city-khm', 'settlement-khm', '7', 'wh-7'),
    'Київ': ('city-kyiv', 'settlement-kyiv', '129', 'wh-129'),
    'Дніпро': ('city-dp', 'settlement-dp', '64', 'wh-64'),
    'Вишгород': ('city-vysh', 'settlement-vysh', '1', 'wh-vysh'),
    'Кагарлик': ('city-kag', 'settlement-kag', '1', 'wh-kag'),
    'Зимна Вода': ('city-zym', 'settlement-zym', '1', 'wh-zym'),
}


class SeededOriginsTests(TestCase):
    def test_migration_seeds_seven_origins_without_refs(self):
        origins = list(ShipmentOrigin.objects.filter(name__in=SEEDED_NAMES))
        self.assertEqual(len(origins), 7)
        self.assertEqual(
            list(ShipmentOrigin.objects.filter(is_default=True).values_list('name', flat=True)),
            ['Київ №129'],
        )
        for row in origins:
            self.assertEqual(row.city_ref, '')
            self.assertEqual(row.warehouse_ref, '')
            self.assertEqual(row.street_ref, '')
            self.assertEqual(row.is_default, row.name == 'Київ №129')
            self.assertTrue(row.is_active)
        address = ShipmentOrigin.objects.get(
            name='Київ, адресний забір, вул. Золотоустівська 10-12',
        )
        self.assertEqual(address.kind, ShipmentOrigin.KIND_ADDRESS)
        self.assertEqual(address.city_name, 'Київ')
        self.assertEqual(address.street_name, 'Золотоустівська')
        self.assertEqual(address.building, '10-12')
        self.assertEqual(
            ShipmentOrigin.objects.filter(name__in=SEEDED_NAMES, kind='warehouse').count(),
            6,
        )

    def test_only_one_default_via_save_and_validation(self):
        first = ShipmentOrigin.objects.create(
            name='Склад А', kind='warehouse', city_name='Київ', is_default=True,
        )
        second = ShipmentOrigin.objects.create(
            name='Склад Б', kind='warehouse', city_name='Львів', is_default=True,
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)
        self.assertEqual(ShipmentOrigin.objects.filter(is_default=True).count(), 1)

        candidate = ShipmentOrigin(
            name='Склад В', kind='warehouse', city_name='Одеса', is_default=True,
        )
        with self.assertRaises(ValidationError):
            candidate.full_clean()

        inactive = ShipmentOrigin(
            name='Склад Г', kind='warehouse', city_name='Дніпро',
            is_default=True, is_active=False,
        )
        with self.assertRaises(ValidationError):
            inactive.full_clean()

    def test_new_order_gets_active_default_origin(self):
        chosen = ShipmentOrigin.objects.create(
            name='Типова', kind='warehouse', city_name='Київ',
            is_default=True, is_active=True,
        )
        ShipmentOrigin.objects.create(
            name='Неактивна', kind='warehouse', city_name='Львів',
            is_default=True, is_active=False,
        )
        created = order()
        self.assertEqual(created.shipment_origin_id, chosen.pk)
        inactive = ShipmentOrigin.objects.get(name='Неактивна')
        self.assertFalse(inactive.is_default)

    def test_order_without_default_stays_empty(self):
        ShipmentOrigin.objects.filter(is_default=True).update(is_default=False)
        created = Order.objects.create(
            first_name='А', last_name='Б', phone='+380501112233',
            city='Київ', warehouse='1',
        )
        self.assertIsNone(created.shipment_origin_id)

    def test_pick_warehouse_does_not_confuse_1_and_10(self):
        rows = [
            {'number': '10', 'ref': 'ten', 'description': 'Відділення №10'},
            {'number': '1', 'ref': 'one', 'description': 'Відділення №1'},
        ]
        self.assertEqual(pick_warehouse(rows, '1')['ref'], 'one')


def _np_post(url, json=None, timeout=None):
    method = json['calledMethod']
    props = json['methodProperties']
    if method == 'searchSettlements':
        city_name = props['CityName']
        city_ref, settlement_ref, _number, _wh = CATALOG[city_name]
        return json_response({
            'success': True,
            'data': [{
                'Addresses': [{
                    'Present': f'м. {city_name}, область',
                    'DeliveryCity': city_ref,
                    'Ref': settlement_ref,
                }],
            }],
            'errors': [],
        })
    if method == 'getWarehouses':
        match = next(item for item in CATALOG.values() if item[0] == props['CityRef'])
        _city, _settlement, number, warehouse_ref = match
        return json_response({
            'success': True,
            'data': [{
                'Ref': warehouse_ref,
                'Number': number,
                'Description': f'Відділення №{number}',
                'ShortAddress': 'вул. Тестова',
            }],
            'errors': [],
        })
    if method == 'searchSettlementStreets':
        self_ref = props.get('SettlementRef')
        if self_ref != 'settlement-kyiv':
            return json_response({'success': True, 'data': [], 'errors': []})
        return json_response({
            'success': True,
            'data': [{
                'Addresses': [{
                    'SettlementStreetRef': 'street-zol',
                    'SettlementStreetDescription': 'Золотоустівська',
                    'Present': 'вул. Золотоустівська',
                }],
            }],
            'errors': [],
        })
    raise AssertionError(method)


@override_settings(NOVAPOSHTA_API_KEY='np-test-key')
class FillOriginRefsTests(TestCase):
    def test_command_fills_refs_from_api(self):
        with patch('shipping.novaposhta_api.requests.post', side_effect=_np_post) as post:
            call_command('fill_origin_refs', stdout=StringIO())
        self.assertGreater(post.call_count, 0)
        khm = ShipmentOrigin.objects.get(name='Хмельницький №7')
        self.assertEqual(khm.city_ref, 'city-khm')
        self.assertEqual(khm.warehouse_ref, 'wh-7')
        kyiv = ShipmentOrigin.objects.get(name='Київ №129')
        self.assertEqual(kyiv.city_ref, 'city-kyiv')
        self.assertEqual(kyiv.warehouse_ref, 'wh-129')
        address = ShipmentOrigin.objects.get(
            name='Київ, адресний забір, вул. Золотоустівська 10-12',
        )
        self.assertEqual(address.city_ref, 'city-kyiv')
        self.assertEqual(address.street_ref, 'street-zol')
        self.assertEqual(address.warehouse_ref, '')
        self.assertEqual(
            list(ShipmentOrigin.objects.filter(is_default=True).values_list('name', flat=True)),
            ['Київ №129'],
        )
        post.reset_mock()
        with patch('shipping.novaposhta_api.requests.post', side_effect=_np_post) as again:
            call_command('fill_origin_refs', stdout=StringIO())
        again.assert_not_called()

    @override_settings(NOVAPOSHTA_API_KEY='')
    def test_command_without_key_does_not_call_api(self):
        err = StringIO()
        with patch('shipping.novaposhta_api.requests.post') as post:
            call_command('fill_origin_refs', stdout=StringIO(), stderr=err)
        post.assert_not_called()
        self.assertIn('Ключ НП не налаштовано', err.getvalue())
        self.assertEqual(
            ShipmentOrigin.objects.filter(name__in=SEEDED_NAMES, city_ref='').count(),
            7,
        )
