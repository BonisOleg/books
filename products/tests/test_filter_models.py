from pathlib import Path

from django.db import IntegrityError, transaction
from django.test import TestCase

from products.models import Category, FilterAttribute, FilterValue, Product


def make_product(**kwargs):
    defaults = {
        'name': 'Товар',
        'slug': 'tovar',
        'sku': 'SKU-1',
        'description': 'Опис',
        'price': '100.00',
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


class FilterAttributeModelTests(TestCase):
    def test_create_attribute_value_and_reverse_m2m(self):
        attribute = FilterAttribute.objects.create(
            name='Колір', slug='color', position=2, is_active=True,
        )
        value = FilterValue.objects.create(
            attribute=attribute, name='Червоний', slug='red', position=1,
        )
        product = make_product()
        value.products.add(product)

        self.assertEqual(attribute.position, 2)
        self.assertTrue(attribute.is_active)
        self.assertFalse(attribute.categories.exists())
        self.assertEqual(list(product.filter_values.all()), [value])
        self.assertEqual(str(value), 'Колір: Червоний')

    def test_same_value_slug_allowed_on_another_attribute(self):
        color = FilterAttribute.objects.create(name='Колір', slug='color')
        size = FilterAttribute.objects.create(name='Розмір', slug='size')
        FilterValue.objects.create(attribute=color, name='M', slug='m')
        other = FilterValue.objects.create(attribute=size, name='M', slug='m')
        self.assertEqual(other.slug, 'm')

    def test_value_slug_unique_per_attribute(self):
        attribute = FilterAttribute.objects.create(name='Колір', slug='color')
        FilterValue.objects.create(attribute=attribute, name='Червоний', slug='red')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FilterValue.objects.create(attribute=attribute, name='Інший', slug='red')

    def test_attribute_slug_unique(self):
        FilterAttribute.objects.create(name='Колір', slug='color')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FilterAttribute.objects.create(name='Інший колір', slug='color')

    def test_categories_limit_is_optional(self):
        category = Category.objects.create(name='Книги', slug='books')
        limited = FilterAttribute.objects.create(name='Обкладинка', slug='cover')
        limited.categories.add(category)
        everywhere = FilterAttribute.objects.create(name='Мова', slug='lang')
        self.assertEqual(list(limited.categories.all()), [category])
        self.assertFalse(everywhere.categories.exists())

    def test_migration_does_not_touch_product_state(self):
        import importlib
        migration = importlib.import_module(
            'products.migrations.0021_filter_attribute_value',
        )
        names = []
        for operation in migration.Migration.operations:
            self.assertNotEqual(getattr(operation, 'model_name', None), 'product')
            self.assertEqual(operation.__class__.__name__, 'CreateModel')
            names.append(operation.name)
            if operation.name == 'FilterValue':
                fields = dict(operation.fields)
                products = fields['products']
                self.assertEqual(products.remote_field.related_name, 'filter_values')
                self.assertTrue(products.blank)
        self.assertEqual(names, ['FilterAttribute', 'FilterValue'])

    def test_attribute_migration_does_not_seed_rows(self):
        import importlib
        migration = importlib.import_module(
            'products.migrations.0021_filter_attribute_value',
        )
        source = Path(migration.__file__).read_text(encoding='utf-8')
        self.assertNotIn('RunPython', source)
        self.assertNotIn('FilterAttribute.objects', source)
        self.assertNotIn('FilterValue.objects', source)

    def test_no_starter_filter_rows_outside_tests(self):
        root = Path(__file__).resolve().parents[2]
        calls = (
            'FilterAttribute.objects.create',
            'FilterAttribute.objects.get_or_create',
            'FilterAttribute.objects.update_or_create',
            'FilterAttribute.objects.bulk_create',
            'FilterValue.objects.create',
            'FilterValue.objects.get_or_create',
            'FilterValue.objects.update_or_create',
            'FilterValue.objects.bulk_create',
        )
        skip = {
            'tests', 'books', '.git', 'node_modules', '__pycache__', '.venv', 'venv',
        }
        hits = []
        for path in root.rglob('*.py'):
            rel = path.relative_to(root)
            if skip.intersection(rel.parts):
                continue
            text = path.read_text(encoding='utf-8')
            for call in calls:
                if call in text:
                    hits.append(f'{rel}: {call}')
        for folder in root.rglob('fixtures'):
            if not folder.is_dir() or skip.intersection(folder.relative_to(root).parts):
                continue
            for path in folder.rglob('*'):
                if not path.is_file() or path.suffix.lower() not in {'.json', '.yaml', '.yml'}:
                    continue
                rel = path.relative_to(root)
                if skip.intersection(rel.parts):
                    continue
                text = path.read_text(encoding='utf-8').lower()
                if 'filterattribute' in text or 'filtervalue' in text:
                    hits.append(str(rel))
        self.assertEqual(hits, [])
