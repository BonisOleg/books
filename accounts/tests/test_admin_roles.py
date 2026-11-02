import importlib
import json

from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from accounts.admin import SUPERUSER_HELP, permission_label

_groups = importlib.import_module('accounts.migrations.0002_manager_groups')
GROUP_ORDERS = _groups.GROUP_ORDERS
GROUP_PRODUCTS = _groups.GROUP_PRODUCTS
create_manager_groups = _groups.create_manager_groups
remove_manager_groups = _groups.remove_manager_groups
from orders.models import Order
from products.admin import ProductAdmin
from products.models import Product

User = get_user_model()

PRODUCT_GROUP_PERMS = {
    ('products', 'view_product'),
    ('products', 'add_product'),
    ('products', 'change_product'),
    ('products', 'view_category'),
    ('products', 'add_category'),
    ('products', 'change_category'),
    ('products', 'view_badge'),
    ('products', 'add_badge'),
    ('products', 'change_badge'),
    ('products', 'view_productimage'),
    ('products', 'add_productimage'),
    ('products', 'change_productimage'),
    ('products', 'delete_productimage'),
    ('products', 'view_filtergroup'),
    ('products', 'add_filtergroup'),
    ('products', 'change_filtergroup'),
    ('products', 'view_filteroption'),
    ('products', 'add_filteroption'),
    ('products', 'change_filteroption'),
}

ORDER_GROUP_PERMS = {
    ('orders', 'view_order'),
    ('orders', 'change_order'),
    ('orders', 'view_orderitem'),
    ('orders', 'change_orderitem'),
    ('products', 'view_product'),
}


class _Schema:
    connection = connection


def _perm_set(group):
    return set(group.permissions.values_list('content_type__app_label', 'codename'))


def _staff(username, group_name=None):
    user = User.objects.create_user(username, password='pass-12345', is_staff=True)
    if group_name:
        user.groups.add(Group.objects.get(name=group_name))
    return user


def _product():
    return Product.objects.create(
        name='Рольовий товар',
        slug='rolovyi-tovar',
        sku='ROLE-1',
        sku_manufacturer='ROLE-MFG',
        manufacturer='Роль',
        description='<p>Опис</p>',
        price='50.00',
    )


def _order():
    return Order.objects.create(
        first_name='Олена',
        last_name='Коваленко',
        phone='+380671112233',
        city='Львів',
        warehouse='Відділення 12',
        total='50.00',
    )


class ManagerGroupMigrationTests(TestCase):
    def test_groups_exist_with_expected_permissions(self):
        products = Group.objects.get(name=GROUP_PRODUCTS)
        orders = Group.objects.get(name=GROUP_ORDERS)
        self.assertEqual(_perm_set(products), PRODUCT_GROUP_PERMS)
        self.assertEqual(_perm_set(orders), ORDER_GROUP_PERMS)
        self.assertNotIn(('products', 'delete_product'), _perm_set(products))
        self.assertNotIn(('orders', 'delete_order'), _perm_set(orders))
        self.assertNotIn(('products', 'add_product'), _perm_set(orders))
        self.assertNotIn(('products', 'change_product'), _perm_set(orders))

    def test_migration_is_idempotent_and_reversible(self):
        from django.apps import apps

        remove_manager_groups(apps, _Schema())
        self.assertFalse(Group.objects.filter(name=GROUP_PRODUCTS).exists())
        self.assertFalse(Group.objects.filter(name=GROUP_ORDERS).exists())

        create_manager_groups(apps, _Schema())
        create_manager_groups(apps, _Schema())
        self.assertEqual(Group.objects.filter(name=GROUP_PRODUCTS).count(), 1)
        self.assertEqual(Group.objects.filter(name=GROUP_ORDERS).count(), 1)
        self.assertEqual(
            _perm_set(Group.objects.get(name=GROUP_PRODUCTS)),
            PRODUCT_GROUP_PERMS,
        )
        self.assertEqual(
            _perm_set(Group.objects.get(name=GROUP_ORDERS)),
            ORDER_GROUP_PERMS,
        )


class PermissionLabelTests(TestCase):
    def test_standard_permissions_use_model_verbose_name(self):
        expected = {
            'view_product': 'Товар — може переглядати',
            'add_product': 'Товар — може додавати',
            'change_product': 'Товар — може редагувати',
            'delete_product': 'Товар — може видаляти',
        }
        for codename, label in expected.items():
            perm = Permission.objects.get(
                codename=codename,
                content_type__app_label='products',
                content_type__model='product',
            )
            self.assertEqual(permission_label(perm), label)

    def test_group_change_form_keeps_filter_horizontal(self):
        root = User.objects.create_superuser('root-roles', 'root@example.com', 'pass-12345')
        self.client.force_login(root)
        group = Group.objects.get(name=GROUP_PRODUCTS)
        response = self.client.get(reverse('admin:auth_group_change', args=[group.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Товар — може переглядати')
        self.assertContains(response, 'class="selectfilter"')
        self.assertContains(response, 'SelectFilter2.js')
        self.assertContains(response, 'Як додати менеджера')


class AdminShellTests(TestCase):
    def test_ukrainian_admin_branding(self):
        self.assertEqual(admin.site.site_header, 'Адмінка магазину')
        self.assertEqual(admin.site.site_title, 'Адмінка магазину')
        self.assertEqual(admin.site.index_title, 'Керування магазином')

    def test_guide_is_available_to_any_staff(self):
        user = _staff('guide-staff')
        self.client.force_login(user)
        response = self.client.get(reverse('admin:how_to_add_manager'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Статус персоналу')
        self.assertContains(response, 'суперкористувача')
        self.assertContains(response, 'Менеджер товарів')
        self.assertContains(response, 'Менеджер замовлень')

    def test_user_change_warns_not_to_set_superuser(self):
        root = User.objects.create_superuser('root-users', 'users@example.com', 'pass-12345')
        staff = _staff('plain-staff')
        self.client.force_login(root)
        response = self.client.get(
            reverse('admin:accounts_customuser_change', args=[staff.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, SUPERUSER_HELP)
        self.assertContains(response, reverse('admin:how_to_add_manager'))


class AdminAccessTests(TestCase):
    def setUp(self):
        self.product = _product()
        self.order = _order()
        self.bare = _staff('bare-staff')
        self.catalog = _staff('catalog-staff', GROUP_PRODUCTS)
        self.orders = _staff('orders-staff', GROUP_ORDERS)
        self.product_url = reverse('admin:products_product_changelist')
        self.order_url = reverse('admin:orders_order_changelist')
        self.order_change = reverse('admin:orders_order_change', args=[self.order.pk])
        self.order_delete = reverse('admin:orders_order_delete', args=[self.order.pk])
        self.product_add = reverse('admin:products_product_add')

    def _action(self, name):
        return {
            'action': name,
            'index': '0',
            ACTION_CHECKBOX_NAME: [str(self.product.pk)],
        }

    def test_staff_without_permissions_is_forbidden(self):
        self.client.force_login(self.bare)
        forbidden = [
            self.product_url,
            self.order_url,
            reverse('admin:products_product_bulk_upload', args=[self.product.pk]),
            reverse('import_export_app:dashboard'),
            reverse('import_export_app:export'),
        ]
        for url in forbidden:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

        posts = [
            (reverse('admin:products_product_quick_save'), {'product_id': self.product.pk}),
            (reverse('import_export_app:import_action'), {}),
            (reverse('tinymce_upload_image'), {}),
        ]
        for url, data in posts:
            with self.subTest(url=url):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 403)

        quick = self.client.post(
            reverse('admin:products_product_quick_save'),
            data=json.dumps({'product_id': self.product.pk, 'price': '10'}),
            content_type='application/json',
        )
        self.assertEqual(quick.status_code, 403)

        for action_name in ProductAdmin.actions:
            with self.subTest(action=action_name):
                response = self.client.post(self.product_url, self._action(action_name))
                self.assertEqual(response.status_code, 403)

    def test_product_manager_can_open_products_not_orders(self):
        self.client.force_login(self.catalog)
        self.assertEqual(self.client.get(self.product_url).status_code, 200)
        self.assertEqual(self.client.get(self.order_change).status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse('admin:products_product_bulk_upload', args=[self.product.pk]),
            ).status_code,
            200,
        )
        action = self.client.post(self.product_url, self._action('set_sale_end_date_action'))
        self.assertEqual(action.status_code, 200)
        self.assertContains(action, 'Встановити таймер акції')
        quick = self.client.post(
            reverse('admin:products_product_quick_save'),
            data=json.dumps({'product_id': self.product.pk, 'price': '19.50'}),
            content_type='application/json',
        )
        self.assertEqual(quick.status_code, 200)
        upload = self.client.post(reverse('tinymce_upload_image'), {})
        self.assertEqual(upload.status_code, 400)
        self.assertEqual(self.client.get(reverse('import_export_app:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('import_export_app:export')).status_code, 200)
        imported = self.client.post(reverse('import_export_app:import_action'), {})
        self.assertEqual(imported.status_code, 302)

    def test_order_manager_can_change_orders_not_delete_or_add_products(self):
        self.client.force_login(self.orders)
        self.assertEqual(self.client.get(self.order_change).status_code, 200)
        self.assertEqual(self.client.get(self.order_delete).status_code, 403)
        self.assertEqual(self.client.post(self.order_delete, {'post': 'yes'}).status_code, 403)
        self.assertEqual(self.client.get(self.product_add).status_code, 403)
        self.assertEqual(self.client.get(self.product_url).status_code, 200)
        action = self.client.post(self.product_url, self._action('clear_sale_end_date_action'))
        self.assertEqual(action.status_code, 403)
        self.assertEqual(self.client.post(reverse('tinymce_upload_image'), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse('import_export_app:export')).status_code, 200)
        self.assertEqual(self.client.post(reverse('import_export_app:import_action'), {}).status_code, 403)

    def test_editor_with_article_change_can_upload_tinymce(self):
        user = _staff('article-editor')
        perm = Permission.objects.get(
            codename='change_article',
            content_type__app_label='blog',
        )
        user.user_permissions.add(perm)
        self.client.force_login(user)
        response = self.client.post(reverse('tinymce_upload_image'), {})
        self.assertEqual(response.status_code, 400)
