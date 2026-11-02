import importlib

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

GROUP_ORDERS = importlib.import_module(
    'accounts.migrations.0002_manager_groups',
).GROUP_ORDERS
from orders.admin import OrderItemInline
from orders.models import Order, OrderItem
from products.models import Product

User = get_user_model()


class OrderItemCodeColumnTests(TestCase):
    def setUp(self):
        self.inline = OrderItemInline(Order, admin.site)
        self.order = Order.objects.create(
            first_name='Іван',
            last_name='Петренко',
            phone='+380501112233',
            city='Київ',
            warehouse='Відділення 1',
            total='80.00',
        )
        self.product = Product.objects.create(
            name='Книга з кодом',
            slug='knyha-z-kodom',
            sku='BOOK-77',
            sku_manufacturer='MFG-77',
            manufacturer='Видавництво Код',
            description='<p>Опис</p>',
            price='80.00',
        )

    def test_short_descriptions_are_ukrainian(self):
        self.assertEqual(OrderItemInline.product_article.short_description, 'Артикул')
        self.assertEqual(
            OrderItemInline.product_manufacturer_code.short_description,
            'Код виробника',
        )
        self.assertEqual(
            OrderItemInline.product_manufacturer_code.admin_order_field,
            'sku_manufacturer',
        )
        self.assertEqual(OrderItemInline.product_manufacturer.short_description, 'Виробник')

    def test_methods_are_safe_without_product(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=None,
            product_name='Видалений товар',
            product_sku='OLD-SKU',
            price='10.00',
            quantity=1,
        )
        self.assertEqual(self.inline.product_article(item), '—')
        self.assertEqual(self.inline.product_manufacturer_code(item), '—')
        self.assertEqual(self.inline.product_manufacturer(item), '—')
        self.assertEqual(self.inline.product_article(None), '—')

    def test_methods_read_live_product_codes(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku='SNAPSHOT',
            price='80.00',
            quantity=1,
        )
        self.assertEqual(self.inline.product_article(item), 'BOOK-77')
        self.assertEqual(self.inline.product_manufacturer_code(item), 'MFG-77')
        self.assertEqual(self.inline.product_manufacturer(item), 'Видавництво Код')

    def test_order_change_shows_product_codes(self):
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku='SNAPSHOT',
            price='80.00',
            quantity=1,
        )
        user = User.objects.create_user('order-codes', password='pass-12345', is_staff=True)
        user.groups.add(Group.objects.get(name=GROUP_ORDERS))
        self.client.force_login(user)

        response = self.client.get(reverse('admin:orders_order_change', args=[self.order.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Код виробника')
        self.assertContains(response, 'MFG-77')
        self.assertContains(response, 'Видавництво Код')
        self.assertContains(response, 'BOOK-77')
