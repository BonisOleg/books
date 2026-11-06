from datetime import date, timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.admin.widgets import AdminDateWidget
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from modeltranslation.translator import translator

from core.models import SiteSettings
from products.admin import ConsultationRequestAdmin, ProductAdmin
from products.models import ConsultationRequest, Product
from products.shipping_date import format_ship_date, local_today, parse_shipping_time_text


class ShippingTimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = SiteSettings.objects.create(
            site_name='OFION',
            default_shipping_time='1–2 дні',
            enable_en=True,
        )
        cls.today = local_today()
        cls.product = Product.objects.create(
            name='Статуетка лева',
            slug='statuetka-leva',
            sku='SHIP-1',
            description='Опис',
            price='500.00',
            shipping_time=cls.today + timedelta(days=1),
        )

    def _html(self, product=None, lang='uk'):
        product = product or self.product
        with translation.override(lang):
            url = reverse('products:detail', kwargs={'slug': product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_майбутня_дата_видима_біля_наявності(self):
        expected = format_ship_date(self.product.shipping_time)
        html = self._html()
        stock = html.find('stock-status')
        shipping = html.find('product-info__shipping')
        self.assertGreater(stock, 0)
        self.assertGreater(shipping, stock)
        self.assertIn(expected, html)
        self.assertNotIn('1–2 дні', html[shipping:shipping + 200])

    def test_сьогоднішня_дата_видима(self):
        self.product.shipping_time = self.today
        self.product.save()
        self.product.refresh_from_db()
        expected = format_ship_date(self.today)
        self.assertEqual(self.product.display_shipping_time, expected)
        html = self._html()
        self.assertIn('product-info__shipping', html)
        self.assertIn(expected, html)

    def test_минула_дата_прихована_без_дефолту(self):
        past = self.today - timedelta(days=1)
        self.product.shipping_time = past
        self.product.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.display_shipping_time, '')
        html = self._html()
        self.assertNotIn('product-info__shipping', html)
        self.assertNotIn(format_ship_date(past), html)
        self.assertNotIn('1–2 дні', html)

    def test_null_бере_дефолт_сайту(self):
        self.product.shipping_time = None
        self.product.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.display_shipping_time, '1–2 дні')
        html = self._html()
        self.assertIn('product-info__shipping', html)
        self.assertIn('1–2 дні', html)

    def test_нічого_якщо_null_і_дефолт_порожній(self):
        self.product.shipping_time = None
        self.product.save()
        self.site.default_shipping_time = ''
        self.site.save()
        self.product.refresh_from_db()
        self.site.refresh_from_db()
        self.assertEqual(self.product.display_shipping_time, '')
        html = self._html()
        self.assertNotIn('product-info__shipping', html)

    def test_не_перекладається(self):
        product_fields = translator.get_options_for_model(Product).fields
        site_fields = translator.get_options_for_model(SiteSettings).fields
        self.assertNotIn('shipping_time', product_fields)
        self.assertIn('default_shipping_time', site_fields)
        all_fields = []
        for _name, opts in ProductAdmin.fieldsets:
            all_fields.extend(opts.get('fields') or ())
        self.assertIn('shipping_time', all_fields)
        self.assertNotIn('shipping_time_uk', all_fields)
        self.assertNotIn('shipping_time_en', all_fields)
        self.assertNotIn('shipping_time_ru', all_fields)
        self.assertIn('show_consult_button', all_fields)

    def test_admin_datefield_зберігає(self):
        User = get_user_model()
        user = User.objects.create_superuser(
            'ship-admin', 'ship@example.com', 'pass-12345',
        )
        self.client.force_login(user)
        url = reverse('admin:products_product_change', args=[self.product.pk])
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)
        admin_form = get_resp.context['adminform'].form
        self.assertIsInstance(admin_form.fields['shipping_time'].widget, AdminDateWidget)

        target = self.today + timedelta(days=5)
        model_admin = ProductAdmin(Product, admin.site)
        form_class = model_admin.get_form(get_resp.wsgi_request, obj=self.product)
        form = form_class(
            data={
                'sku': self.product.sku,
                'sku_manufacturer': '',
                'slug': self.product.slug,
                'price': '500,00',
                'old_price': '',
                'discount_percent': 0,
                'stock_status': self.product.stock_status,
                'shipping_time': target.strftime('%d.%m.%Y'),
                'badge': '',
                'manufacturer': '',
                'country': '',
                'weight': '',
                'condition': '',
                'is_active': 'on',
                'exclude_from_feeds': '',
                'show_consult_button': '',
                'name_uk': self.product.name,
                'description_uk': 'Опис',
                'short_description_uk': '',
                'order_info_uk': '',
                'meta_title_uk': '',
                'meta_description_uk': '',
                'name_en': '',
                'description_en': '',
                'short_description_en': '',
                'order_info_en': '',
                'meta_title_en': '',
                'meta_description_en': '',
                'name_ru': '',
                'description_ru': '',
                'short_description_ru': '',
                'order_info_ru': '',
                'meta_title_ru': '',
                'meta_description_ru': '',
                'categories': [],
                'groups': [],
                'filter_values': [],
            },
            instance=self.product,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.shipping_time, target)


class ShippingTimeParseTests(TestCase):
    def test_парсить_відносні_та_формати(self):
        today = timezone.localdate()
        cases = [
            ('сьогодні', today),
            ('today', today),
            ('завтра', today + timedelta(days=1)),
            ('tomorrow', today + timedelta(days=1)),
            ('післязавтра', today + timedelta(days=2)),
            ('day after tomorrow', today + timedelta(days=2)),
            ('Відправимо завтра', today + timedelta(days=1)),
            ('15.03.2030', date(2030, 3, 15)),
            ('2030-03-15', date(2030, 3, 15)),
            ('15/03/2030', date(2030, 3, 15)),
            ('незрозуміло', None),
            ('', None),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(parse_shipping_time_text(raw, today=today), expected)


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
