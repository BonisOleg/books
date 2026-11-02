from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from products.forms import ProductAdminForm
from products.models import FilterAttribute, FilterValue, Product
from products.widgets import FilterValueAutocompleteWidget

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'filter-admin-tests',
    }
}


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


@override_settings(CACHES=LOC_MEM)
class FilterAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_superuser(
            'filter-admin', 'filter-admin@example.com', 'pass-12345',
        )
        self.client.force_login(self.admin_user)
        self.attribute = FilterAttribute.objects.create(name='Колір', slug='color', position=1)
        self.red = FilterValue.objects.create(
            attribute=self.attribute, name='Червоний', slug='red',
        )
        self.blue = FilterValue.objects.create(
            attribute=self.attribute, name='Синій', slug='blue',
        )
        self.product = make_product()
        self.other = make_product(name='Інший', slug='inshyi', sku='SKU-2')

    def test_create_attribute_with_inline_value(self):
        url = reverse('admin:products_filterattribute_add')
        response = self.client.post(url, {
            'name': 'Обкладинка',
            'slug': 'cover',
            'position': '2',
            'is_active': 'on',
            'values-TOTAL_FORMS': '1',
            'values-INITIAL_FORMS': '0',
            'values-MIN_NUM_FORMS': '0',
            'values-MAX_NUM_FORMS': '1000',
            'values-0-name': 'Шкіра',
            'values-0-slug': 'leather',
            'values-0-position': '0',
        })
        self.assertEqual(response.status_code, 302, response.content.decode()[:1500])
        attribute = FilterAttribute.objects.get(slug='cover')
        self.assertTrue(attribute.is_active)
        self.assertTrue(attribute.values.filter(slug='leather', name='Шкіра').exists())

    def test_product_form_autocomplete_saves_reverse_m2m(self):
        request = RequestFactory().get('/')
        request.user = self.admin_user
        form_class = admin.site._registry[Product].get_form(request, self.product)
        self.assertTrue(issubclass(form_class, ProductAdminForm))
        form = form_class(instance=self.product)
        widget = form.fields['filter_values'].widget
        self.assertIsInstance(widget, FilterValueAutocompleteWidget)
        self.assertIn('filtervalue/autocomplete', widget.get_url())

        form.cleaned_data = {'filter_values': [self.red, self.blue]}
        form._save_filter_values()
        self.assertCountEqual(
            list(self.product.filter_values.all()),
            [self.red, self.blue],
        )

        form.cleaned_data = {'filter_values': FilterValue.objects.filter(pk=self.red.pk)}
        form._save_filter_values()
        self.assertEqual(list(self.product.filter_values.all()), [self.red])

        change = self.client.get(
            reverse('admin:products_product_change', args=[self.product.pk]),
        )
        self.assertEqual(change.status_code, 200)
        self.assertContains(change, 'Значення фільтрів')

    def test_bulk_action_confirms_then_adds_without_removing(self):
        self.red.products.add(self.product)
        url = reverse('admin:products_product_changelist')
        preview = self.client.post(url, {
            'action': 'add_filter_values_action',
            '_selected_action': [self.product.pk, self.other.pk],
        })
        self.assertEqual(preview.status_code, 200)
        body = preview.content.decode()
        self.assertIn('Підтвердити', body)
        self.assertIn(self.product.name, body)
        self.assertIn('Значення фільтра', body)

        applied = self.client.post(url, {
            'action': 'add_filter_values_action',
            'apply': '1',
            '_selected_action': [self.product.pk, self.other.pk],
            'filter_values': [self.blue.pk],
        }, follow=True)
        self.assertEqual(applied.status_code, 200)
        self.assertIn(self.product, self.blue.products.all())
        self.assertIn(self.other, self.blue.products.all())
        self.assertIn(self.product, self.red.products.all())

        again = self.client.post(url, {
            'action': 'add_filter_values_action',
            'apply': '1',
            '_selected_action': [self.product.pk],
            'filter_values': [self.blue.pk],
        }, follow=True)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(self.blue.products.count(), 2)

    def test_bulk_action_requires_a_value(self):
        url = reverse('admin:products_product_changelist')
        response = self.client.post(url, {
            'action': 'add_filter_values_action',
            'apply': '1',
            '_selected_action': [self.product.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.product.filter_values.exists())
        self.assertIn('Підтвердити', response.content.decode())

    def test_autocomplete_finds_value(self):
        url = reverse('admin:products_filtervalue_autocomplete')
        response = self.client.get(url, {'term': 'Черв'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ids = {item['id'] for item in payload['results']}
        self.assertIn(str(self.red.pk), ids)
        self.assertNotIn(str(self.blue.pk), ids)
