from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Product

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'cart-tests',
    }
}


@override_settings(CACHES=LOC_MEM)
class CartAddTests(TestCase):
    def test_add_increments_count(self):
        product = Product.objects.create(
            name='Статуетка',
            slug='statuetka-test',
            sku='SKU-CART-1',
            description='Опис',
            price='250.00',
        )
        response = self.client.post(reverse('cart:add', args=[product.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'1')
        again = self.client.post(reverse('cart:add', args=[product.id]), {'quantity': 2})
        self.assertEqual(again.content, b'3')
