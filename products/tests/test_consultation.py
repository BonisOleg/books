import time
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import SiteSettings
from products.models import ConsultationRequest, Product


LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'consult-tests',
    }
}


def aged_form_ts(seconds=10):
    stamped = time.time() - seconds
    with patch('django.core.signing.time.time', return_value=stamped):
        return TimestampSigner().sign('ok')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@example.test',
    CACHES=LOC_MEM,
    ABUSE_CONSULT_IP=(5, 60),
)
class ConsultationRequestViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = SiteSettings.objects.create(
            site_name='OFION',
            notification_email='ops@example.test',
        )
        cls.off = Product.objects.create(
            name='Кубок без кнопки',
            slug='consult-off',
            sku='CONS-OFF',
            description='Опис',
            price='100.00',
            show_consult_button=False,
        )
        cls.on = Product.objects.create(
            name='Статуетка лева',
            slug='consult-on',
            sku='CONS-ON',
            description='Опис',
            price='500.00',
            show_consult_button=True,
        )
        cls.out = Product.objects.create(
            name='Ваза під замовлення',
            slug='consult-out',
            sku='CONS-OUT',
            description='Опис',
            price='200.00',
            stock_status='out',
            show_consult_button=True,
        )

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def _detail(self, product):
        return reverse('products:detail', kwargs={'slug': product.slug})

    def _consult(self, product):
        return reverse('products:consult', kwargs={'slug': product.slug})

    def _html(self, product):
        response = self.client.get(self._detail(product))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _data(self, **overrides):
        data = {
            'name': 'Олег',
            'phone': '0501112233',
            'question': 'Який розмір?',
            'website': '',
            'form_ts': aged_form_ts(),
        }
        data.update(overrides)
        return data

    def _post(self, product=None, ajax=True, data=None, client=None):
        product = product or self.on
        payload = self._data() if data is None else data
        extra = {}
        if ajax:
            extra['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
            extra['HTTP_ACCEPT'] = 'application/json'
        http = client or self.client
        return http.post(self._consult(product), payload, **extra)

    def _page_messages(self, response):
        followed = self.client.get(response.url)
        self.assertEqual(followed.status_code, 200)
        return [str(item) for item in followed.context['messages']]

    def test_кнопка_лише_коли_галочка(self):
        off_html = self._html(self.off)
        self.assertNotIn('Проконсультуватися', off_html)
        self.assertNotIn('consult-modal', off_html)
        self.assertNotIn(self._consult(self.off), off_html)

        on_html = self._html(self.on)
        self.assertIn('Проконсультуватися', on_html)
        self.assertIn('btn btn--outline btn--block', on_html)
        self.assertIn('id="consult-modal"', on_html)
        self.assertIn('class="modal consult-modal"', on_html)
        self.assertIn(self._consult(self.on), on_html)

        out_html = self._html(self.out)
        self.assertIn('Товар тимчасово відсутній', out_html)
        self.assertIn('Проконсультуватися', out_html)

    def test_post_створює_заявку_і_лист(self):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('зв\'яжемося', payload['message'])

        saved = ConsultationRequest.objects.get()
        self.assertEqual(saved.product_id, self.on.id)
        self.assertEqual(saved.product_name, self.on.name)
        self.assertEqual(saved.name, 'Олег')
        self.assertEqual(saved.phone, '+380501112233')
        self.assertEqual(saved.question, 'Який розмір?')
        self.assertEqual(
            saved.product_url,
            'http://testserver' + self.on.get_absolute_url(),
        )
        self.assertTrue(saved.product_url.startswith('http://'))

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['ops@example.test'])
        self.assertIn(self.on.name, email.subject)
        self.assertIn('Олег', email.body)
        self.assertIn('+380501112233', email.body)
        self.assertIn('Який розмір?', email.body)
        self.assertIn(self.on.name, email.body)
        self.assertIn(saved.product_url, email.body)

    def test_без_js_редірект_з_повідомленням(self):
        response = self._post(ajax=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.on.get_absolute_url())
        messages = self._page_messages(response)
        self.assertTrue(any('зв\'яжемося' in item for item in messages))
        self.assertEqual(ConsultationRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_невалідний_телефон(self):
        response = self._post(data=self._data(phone='12345'))
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['ok'])
        self.assertIn('phone', payload['errors'])
        self.assertIn('номер', payload['errors']['phone'][0].lower())
        self.assertEqual(ConsultationRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

        plain = self._post(ajax=False, data=self._data(phone='12345'))
        self.assertEqual(plain.status_code, 302)
        messages = self._page_messages(plain)
        self.assertTrue(any('номер' in item.lower() for item in messages))
        self.assertEqual(ConsultationRequest.objects.count(), 0)

    def test_honeypot(self):
        response = self._post(data=self._data(website='http://spam.test'))
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['ok'])
        self.assertIn('Не вдалося надіслати форму', payload['message'])
        self.assertEqual(ConsultationRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ABUSE_CONSULT_IP=(1, 60))
    def test_rate_limit(self):
        cache.clear()
        first = self._post()
        second = self._post()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn('Забагато спроб', second.json()['message'])
        self.assertEqual(ConsultationRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_csrf(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(self._detail(self.on))
        self.assertEqual(page.status_code, 200)
        token = client.cookies['csrftoken'].value

        blocked = client.post(
            self._consult(self.on),
            self._data(),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(ConsultationRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

        allowed = client.post(
            self._consult(self.on),
            self._data(csrfmiddlewaretoken=token),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(ConsultationRequest.objects.count(), 1)

    def test_без_галочки_і_get_не_створюють_заявку(self):
        missing = self._post(product=self.off)
        self.assertEqual(missing.status_code, 404)
        inactive = Product.objects.create(
            name='Прихований',
            slug='consult-hidden',
            sku='CONS-HIDDEN',
            description='Опис',
            price='10.00',
            is_active=False,
            show_consult_button=True,
        )
        hidden = self._post(product=inactive)
        self.assertEqual(hidden.status_code, 404)
        method = self.client.get(self._consult(self.on))
        self.assertEqual(method.status_code, 405)
        self.assertEqual(ConsultationRequest.objects.count(), 0)

    def test_помилка_листа_не_скасовує_запис(self):
        with patch('products.notifications.send_mail', side_effect=RuntimeError('smtp')):
            with self.assertLogs('products.notifications', level='ERROR'):
                response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(ConsultationRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_без_email_отримувача_запис_лишається(self):
        self.site.notification_email = ''
        self.site.save(update_fields=['notification_email'])
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ConsultationRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
