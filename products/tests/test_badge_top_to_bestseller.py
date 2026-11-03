"""Data-міграція: старий badge='top' виставляє is_bestseller."""
from decimal import Decimal

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class BadgeTopToBestsellerMigrationTests(TransactionTestCase):
    app = 'products'
    migrate_from = '0022_menu_groups_bestseller'
    migrate_to = '0023_badge_top_to_bestseller'

    def test_top_badge_sets_bestseller_and_reverse_clears_only_top(self):
        try:
            self._migrate([(self.app, self.migrate_from)])
            # Відкат до 0022 знімає лише нащадків цієї гілки. Паралельні
            # 0021 лишаються в схемі, тож вставка йде поточною моделлю:
            # інакше NOT NULL-колонки на кшталт shipping_time не потрапляють в INSERT.
            Product = apps.get_model(self.app, 'Product')
            top = Product.objects.create(
                name='Топ',
                slug='badge-top',
                sku='BADGE-TOP',
                description='Опис',
                price=Decimal('10.00'),
                badge='top',
            )
            other = Product.objects.create(
                name='Акція',
                slug='badge-sale',
                sku='BADGE-SALE',
                description='Опис',
                price=Decimal('11.00'),
                badge='sale',
            )
            empty = Product.objects.create(
                name='Без бейджа',
                slug='badge-empty',
                sku='BADGE-EMPTY',
                description='Опис',
                price=Decimal('12.00'),
                badge='',
            )

            self._migrate([(self.app, self.migrate_to)])
            self.assertEqual(self._bestseller_pks(self.migrate_to), {top.pk})

            before_repeat = self._bestseller_state(self.migrate_to)
            self._apply_forward_again()
            self.assertEqual(self._bestseller_state(self.migrate_to), before_repeat)
            self.assertEqual(self._bestseller_pks(self.migrate_to), {top.pk})

            Product = self._historical_product(self.migrate_to)
            other_before = Product.objects.get(pk=other.pk).is_bestseller
            empty_before = Product.objects.get(pk=empty.pk).is_bestseller

            self._migrate([(self.app, self.migrate_from)])
            Product = self._historical_product(self.migrate_from)
            self.assertFalse(Product.objects.get(pk=top.pk).is_bestseller)
            self.assertEqual(Product.objects.get(pk=other.pk).is_bestseller, other_before)
            self.assertEqual(Product.objects.get(pk=empty.pk).is_bestseller, empty_before)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())

    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        return executor

    def _apply_forward_again(self):
        executor = MigrationExecutor(connection)
        executor.recorder.record_unapplied(self.app, self.migrate_to)
        self._migrate([(self.app, self.migrate_to)])

    def _historical_product(self, migration_name):
        executor = MigrationExecutor(connection)
        apps = executor.loader.project_state([(self.app, migration_name)]).apps
        return apps.get_model(self.app, 'Product')

    def _bestseller_pks(self, migration_name):
        Product = self._historical_product(migration_name)
        return set(Product.objects.filter(is_bestseller=True).values_list('pk', flat=True))

    def _bestseller_state(self, migration_name):
        Product = self._historical_product(migration_name)
        return dict(Product.objects.order_by('pk').values_list('pk', 'is_bestseller'))
