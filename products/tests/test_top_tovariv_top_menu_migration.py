"""Data-міграція 0029: увімкнути show_in_top_menu для «Топ товарів»."""
import importlib

from django.apps import apps
from django.test import TestCase

from products.models import ProductGroup

_migration = importlib.import_module(
    'products.migrations.0029_enable_top_tovariv_top_menu'
)
enable_top_tovariv_top_menu = _migration.enable_top_tovariv_top_menu
noop_reverse = _migration.noop_reverse


class EnableTopTovarivTopMenuMigrationTests(TestCase):
    def test_finds_by_slug(self):
        group = ProductGroup.objects.create(
            name='Інша назва',
            slug='top-tovariv',
            show_in_header=True,
            show_in_top_menu=False,
            is_active=True,
        )
        other = ProductGroup.objects.create(
            name='Топ товарів',
            slug='insha-grupa',
            show_in_header=True,
            show_in_top_menu=False,
            is_active=True,
        )

        enable_top_tovariv_top_menu(apps, None)

        group.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(group.show_in_top_menu)
        self.assertFalse(other.show_in_top_menu)
        self.assertTrue(group.show_in_header)

    def test_finds_by_name_when_slug_unknown(self):
        group = ProductGroup.objects.create(
            name='Топ товарів',
            name_uk='Топ товарів',
            slug='custom-top-slug',
            show_in_header=False,
            show_in_top_menu=False,
            is_active=True,
        )

        enable_top_tovariv_top_menu(apps, None)

        group.refresh_from_db()
        self.assertTrue(group.show_in_top_menu)
        self.assertFalse(group.show_in_header)

    def test_noop_when_not_found(self):
        group = ProductGroup.objects.create(
            name='Звичайна група',
            slug='zvychaina-grupa',
            show_in_header=True,
            show_in_top_menu=False,
            is_active=True,
        )

        enable_top_tovariv_top_menu(apps, None)

        group.refresh_from_db()
        self.assertFalse(group.show_in_top_menu)

    def test_noop_when_ambiguous_slugs(self):
        first = ProductGroup.objects.create(
            name='A',
            slug='top-tovariv',
            show_in_top_menu=False,
            is_active=True,
        )
        second = ProductGroup.objects.create(
            name='B',
            slug='top',
            show_in_top_menu=False,
            is_active=True,
        )

        enable_top_tovariv_top_menu(apps, None)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.show_in_top_menu)
        self.assertFalse(second.show_in_top_menu)

    def test_reverse_is_noop(self):
        group = ProductGroup.objects.create(
            name='Топ товарів',
            slug='top-tovariv',
            show_in_top_menu=True,
            is_active=True,
        )
        noop_reverse(apps, None)
        group.refresh_from_db()
        self.assertTrue(group.show_in_top_menu)
