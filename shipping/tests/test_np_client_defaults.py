"""Data-міграція Нової Пошти: Київ №129 і параметри ТТН."""
import importlib
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.db import connection
from django.test import TestCase

from shipping.models import NPTTNSettings, ShipmentOrigin

_np = importlib.import_module('shipping.migrations.0003_client_np_defaults')
ORIGIN_NAME = _np.ORIGIN_NAME
SENDER_PHONE = _np.SENDER_PHONE
configure_np = _np.configure_np

ROOT = Path(__file__).resolve().parents[2]


class _Schema:
    connection = connection


class NovaPoshtaClientDefaultTests(TestCase):
    def test_migration_sets_origin_and_ttn_settings(self):
        defaults = list(ShipmentOrigin.objects.filter(is_default=True))
        self.assertEqual([row.name for row in defaults], [ORIGIN_NAME])
        kyiv = defaults[0]
        self.assertTrue(kyiv.is_active)
        self.assertEqual(kyiv.city_name, 'Київ')
        self.assertEqual(kyiv.warehouse_name, '№129')

        settings_row = NPTTNSettings.objects.get()
        self.assertEqual(settings_row.payer_type, NPTTNSettings.PAYER_RECIPIENT)
        self.assertEqual(settings_row.cod_mode, NPTTNSettings.COD_AFTERPAYMENT)
        self.assertNotEqual(settings_row.cod_mode, NPTTNSettings.COD_BACKWARD)
        self.assertEqual(settings_row.sender_phone, SENDER_PHONE)
        self.assertEqual(settings_row.sender_type, NPTTNSettings.SENDER_ORGANIZATION)
        self.assertFalse(settings_row.auto_create_ttn)
        self.assertEqual(settings_row.default_weight, Decimal('1.000'))

    def test_rerun_keeps_weight_refs_and_resets_the_chosen_fields(self):
        kyiv = ShipmentOrigin.objects.get(name=ORIGIN_NAME)
        kyiv.city_ref = 'city-keep'
        kyiv.warehouse_ref = 'wh-keep'
        kyiv.is_default = False
        kyiv.save(update_fields=['city_ref', 'warehouse_ref', 'is_default'])
        other = ShipmentOrigin.objects.create(
            name='Склад тимчасовий',
            kind=ShipmentOrigin.KIND_WAREHOUSE,
            city_name='Львів',
            is_active=True,
            is_default=True,
        )
        row = NPTTNSettings.objects.get()
        row.default_weight = Decimal('2.500')
        row.sender_phone = '+380671110000'
        row.cod_mode = NPTTNSettings.COD_BACKWARD
        row.payer_type = NPTTNSettings.PAYER_SENDER
        row.sender_type = NPTTNSettings.SENDER_PRIVATE
        row.auto_create_ttn = True
        row.save()

        configure_np(apps, _Schema())
        configure_np(apps, _Schema())

        kyiv.refresh_from_db()
        other.refresh_from_db()
        row.refresh_from_db()
        self.assertTrue(kyiv.is_default)
        self.assertEqual(kyiv.city_ref, 'city-keep')
        self.assertEqual(kyiv.warehouse_ref, 'wh-keep')
        self.assertFalse(other.is_default)
        self.assertEqual(ShipmentOrigin.objects.filter(is_default=True).count(), 1)
        self.assertEqual(row.default_weight, Decimal('2.500'))
        self.assertEqual(row.sender_phone, SENDER_PHONE)
        self.assertEqual(row.cod_mode, NPTTNSettings.COD_AFTERPAYMENT)
        self.assertEqual(row.payer_type, NPTTNSettings.PAYER_RECIPIENT)
        self.assertEqual(row.sender_type, NPTTNSettings.SENDER_ORGANIZATION)
        self.assertFalse(row.auto_create_ttn)
        self.assertEqual(NPTTNSettings.objects.count(), 1)

    def test_model_defaults_match_client_without_a_sender_name_field(self):
        self.assertEqual(
            NPTTNSettings._meta.get_field('cod_mode').default,
            NPTTNSettings.COD_AFTERPAYMENT,
        )
        self.assertEqual(
            NPTTNSettings._meta.get_field('payer_type').default,
            NPTTNSettings.PAYER_RECIPIENT,
        )
        self.assertEqual(
            NPTTNSettings._meta.get_field('sender_type').default,
            NPTTNSettings.SENDER_ORGANIZATION,
        )
        self.assertFalse(NPTTNSettings._meta.get_field('auto_create_ttn').default)
        names = {field.name for field in NPTTNSettings._meta.fields}
        self.assertFalse(names & {'sender_name', 'sender_full_name', 'organization_name'})
        doc = (ROOT / 'docs' / 'novaposhta.md').read_text(encoding='utf-8')
        self.assertIn('ФОП Барабан Л.В.', doc)
        self.assertIn('кабінет', doc.lower())
