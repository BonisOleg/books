import importlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

GROUP_PRODUCTS = importlib.import_module(
    'accounts.migrations.0002_manager_groups',
).GROUP_PRODUCTS
from products.admin import ProductAdmin
from products.models import Product

User = get_user_model()


def make_product(**kwargs):
    defaults = {
        'name': 'Атлас кодів',
        'slug': 'atlas-kodiv',
        'sku': 'SKU-ATLAS',
        'sku_manufacturer': 'MFG-ATLAS-42',
        'manufacturer': 'Видавництво Тест',
        'description': '<p>Опис</p>',
        'price': '120.00',
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


class ProductAdminCodeTests(TestCase):
    def test_list_display_and_search_fields_include_codes(self):
        self.assertIn('sku', ProductAdmin.list_display)
        self.assertIn('manufacturer_code', ProductAdmin.list_display)
        self.assertIn('manufacturer', ProductAdmin.list_display)
        self.assertEqual(ProductAdmin.manufacturer_code.short_description, 'Код виробника')
        self.assertEqual(ProductAdmin.manufacturer_code.admin_order_field, 'sku_manufacturer')
        self.assertIn('sku', ProductAdmin.search_fields)
        self.assertIn('sku_manufacturer', ProductAdmin.search_fields)
        self.assertIn('manufacturer', ProductAdmin.search_fields)
        self.assertTrue(any(name.startswith('name') for name in ProductAdmin.search_fields))
        self.assertEqual(
            str(Product._meta.get_field('sku').verbose_name),
            'Артикул',
        )
        self.assertEqual(
            str(Product._meta.get_field('sku_manufacturer').verbose_name),
            'Артикул виробника',
        )
        self.assertEqual(
            str(Product._meta.get_field('manufacturer').verbose_name),
            'Виробник',
        )

    def test_changelist_search_by_manufacturer_code(self):
        product = make_product()
        other = make_product(
            name='Інший товар',
            slug='inshyi',
            sku='SKU-OTHER',
            sku_manufacturer='OTHER-CODE',
            manufacturer='Інший виробник',
        )
        user = User.objects.create_user('codes-manager', password='pass-12345', is_staff=True)
        user.groups.add(Group.objects.get(name=GROUP_PRODUCTS))
        self.client.force_login(user)

        url = reverse('admin:products_product_changelist')
        response = self.client.get(url, {'q': 'MFG-ATLAS-42'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, product.name)
        self.assertNotContains(response, other.name)
        self.assertContains(response, 'Код виробника')
        self.assertContains(response, 'Видавництво Тест')
