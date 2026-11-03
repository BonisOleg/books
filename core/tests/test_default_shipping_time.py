"""Час відправки за замовчуванням: 1-3 дні, якщо поле порожнє."""
import importlib

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

from core.models import SiteSettings

_migration = importlib.import_module('core.migrations.0018_default_shipping_time_value')
fill_blank_shipping_time = _migration.fill_blank_shipping_time
SHIPPING_TIME = _migration.SHIPPING_TIME


class _Schema:
    connection = connection


def _historical_apps():
    """Стан до дескриптора перекладів: колонки читаються як є."""
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    return loader.project_state(('core', '0017_default_shipping_time')).apps


class DefaultShippingTimeTests(TestCase):
    def test_model_default_is_client_phrase(self):
        self.assertEqual(
            SiteSettings._meta.get_field('default_shipping_time').default,
            '1-3 дні',
        )
        fresh = SiteSettings.objects.create(site_name='Новий')
        self.assertEqual(fresh.default_shipping_time, SHIPPING_TIME)

    def _columns(self, pk):
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT default_shipping_time, default_shipping_time_uk,
                       default_shipping_time_en, default_shipping_time_ru
                FROM core_sitesettings WHERE id = %s
                ''',
                [pk],
            )
            return cursor.fetchone()

    def _write(self, pk, **columns):
        assignments = ', '.join(f'{name} = %s' for name in columns)
        with connection.cursor() as cursor:
            cursor.execute(
                f'UPDATE core_sitesettings SET {assignments} WHERE id = %s',
                [*columns.values(), pk],
            )

    def test_data_migration_fills_only_blank_and_is_idempotent(self):
        custom = SiteSettings.objects.create(site_name='Свій')
        blank = SiteSettings.objects.create(site_name='Порожній')
        mixed = SiteSettings.objects.create(site_name='Мікс')
        self._write(
            custom.pk,
            default_shipping_time='До 5 днів',
            default_shipping_time_uk='До 5 днів',
            default_shipping_time_en='',
            default_shipping_time_ru='',
        )
        self._write(
            blank.pk,
            default_shipping_time='',
            default_shipping_time_uk='   ',
            default_shipping_time_en='',
            default_shipping_time_ru=None,
        )
        self._write(
            mixed.pk,
            default_shipping_time='',
            default_shipping_time_uk='Свій термін',
            default_shipping_time_en='Ships soon',
            default_shipping_time_ru='',
        )

        historical = _historical_apps()
        fill_blank_shipping_time(historical, _Schema())
        fill_blank_shipping_time(historical, _Schema())

        self.assertEqual(
            self._columns(custom.pk),
            ('До 5 днів', 'До 5 днів', None, None),
        )
        self.assertEqual(
            self._columns(blank.pk),
            (SHIPPING_TIME, SHIPPING_TIME, None, None),
        )
        self.assertEqual(
            self._columns(mixed.pk),
            (SHIPPING_TIME, 'Свій термін', 'Ships soon', None),
        )
        mixed.refresh_from_db()
        self.assertEqual(mixed.default_shipping_time, 'Свій термін')
