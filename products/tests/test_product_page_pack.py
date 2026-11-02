from django.contrib import admin
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from modeltranslation.translator import translator

from core.models import SiteSettings
from products.admin import ConsultationRequestAdmin, ProductAdmin
from products.models import ConsultationRequest, Product


class ShippingTimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = SiteSettings.objects.create(
            site_name='OFION',
            default_shipping_time='1–2 дні',
            enable_en=True,
        )
        cls.product = Product.objects.create(
            name='Статуетка лева',
            slug='statuetka-leva',
            sku='SHIP-1',
            description='Опис',
            price='500.00',
            shipping_time='Відправимо завтра',
        )

    def _html(self, product=None, lang='uk'):
        product = product or self.product
        with translation.override(lang):
            url = reverse('products:detail', kwargs={'slug': product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_свій_час_біля_наявності(self):
        html = self._html()
        stock = html.find('stock-status')
        shipping = html.find('product-info__shipping')
        self.assertGreater(stock, 0)
        self.assertGreater(shipping, stock)
        self.assertIn('Відправимо завтра', html)
        self.assertNotIn('1–2 дні', html[shipping:shipping + 200])

    def test_дефолт_сайту_якщо_у_товарі_порожньо(self):
        self.product.shipping_time = ''
        self.product.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.display_shipping_time, '1–2 дні')
        html = self._html()
        self.assertIn('product-info__shipping', html)
        self.assertIn('1–2 дні', html)

    def test_пробіли_вважаються_порожніми(self):
        self.product.shipping_time = '   '
        self.product.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.display_shipping_time, '1–2 дні')

    def test_нічого_якщо_обидва_порожні(self):
        self.product.shipping_time = ''
        self.product.save()
        self.site.default_shipping_time = ''
        self.site.save()
        self.product.refresh_from_db()
        self.site.refresh_from_db()
        self.assertEqual(self.product.display_shipping_time, '')
        html = self._html()
        self.assertNotIn('product-info__shipping', html)

    def test_переклад_англійською(self):
        self.product.shipping_time_en = 'Ships tomorrow'
        self.product.save()
        html = self._html(lang='en')
        self.assertIn('Ships tomorrow', html)
        self.assertIn('/en/', html)

    def test_поле_зареєстроване_в_перекладах(self):
        product_fields = translator.get_options_for_model(Product).fields
        site_fields = translator.get_options_for_model(SiteSettings).fields
        self.assertIn('shipping_time', product_fields)
        self.assertIn('default_shipping_time', site_fields)
        uk_fields = []
        for _name, opts in ProductAdmin.fieldsets:
            uk_fields.extend(opts.get('fields') or ())
        self.assertIn('shipping_time_uk', uk_fields)
        self.assertIn('shipping_time_en', uk_fields)
        self.assertIn('shipping_time_ru', uk_fields)
        self.assertIn('show_consult_button', uk_fields)


class ConsultationRequestTests(TestCase):
    def test_кнопка_консультації_вимкнена_за_замовчуванням(self):
        product = Product.objects.create(
            name='Кубок',
            slug='kubok',
            sku='CONS-1',
            description='Опис',
            price='10.00',
        )
        self.assertFalse(product.show_consult_button)

    def test_заявка_і_адмінка(self):
        product = Product.objects.create(
            name='Кубок',
            slug='kubok-zayavka',
            sku='CONS-2',
            description='Опис',
            price='10.00',
        )
        request = ConsultationRequest.objects.create(
            product=product,
            product_name=product.name,
            product_url='https://example.test/catalog/product/kubok-zayavka/',
            name='Олег',
            phone='+380501112233',
            question='Який розмір?',
        )
        self.assertFalse(request.is_processed)
        self.assertEqual(str(request), 'Олег — +380501112233')
        self.assertEqual(ConsultationRequest._meta.verbose_name, 'Заявка на консультацію')
        self.assertEqual(product.consultation_requests.get().pk, request.pk)

        registered = admin.site._registry[ConsultationRequest]
        self.assertIsInstance(registered, ConsultationRequestAdmin)
        self.assertEqual(
            registered.list_display,
            ('created_at', 'name', 'phone', 'product_name', 'is_processed'),
        )
        self.assertIn('is_processed', registered.list_filter)
        self.assertIn('phone', registered.search_fields)
        self.assertIn('question', registered.search_fields)
