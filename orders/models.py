from django.db import DatabaseError, models
from django.conf import settings
from products.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Нове'),
        ('processing', 'В обробці'),
        ('shipped', 'Відправлено'),
        ('delivered', 'Доставлено'),
        ('cancelled', 'Скасовано'),
    ]
    PAYMENT_CHOICES = [
        ('liqpay', 'LiqPay'),
        ('monobank', 'Monobank'),
        ('cod', 'Накладений платіж'),
        ('manager', 'Зв\'яжіться з менеджером'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Очікує оплати'),
        ('paid', 'Оплачено'),
        ('failed', 'Помилка оплати'),
        ('refunded', 'Повернення'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='Користувач',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders'
    )
    first_name = models.CharField('Ім\'я', max_length=150)
    last_name = models.CharField('Прізвище', max_length=150)
    patronymic = models.CharField('По батькові', max_length=150, blank=True)
    phone = models.CharField('Телефон', max_length=30)
    email = models.EmailField('Email', blank=True)
    city = models.CharField('Місто', max_length=200)
    city_ref = models.CharField('Ref міста', max_length=100, blank=True, default='')
    warehouse = models.CharField('Відділення НП', max_length=300, blank=True)
    warehouse_ref = models.CharField('Ref відділення', max_length=100, blank=True)
    recipient_area = models.CharField('Область отримувача', max_length=200, blank=True)
    recipient_street = models.CharField('Вулиця отримувача', max_length=200, blank=True)
    recipient_house = models.CharField('Будинок отримувача', max_length=50, blank=True)
    recipient_flat = models.CharField('Квартира отримувача', max_length=50, blank=True)
    comment = models.TextField('Коментар', blank=True)
    payment_method = models.CharField(
        'Спосіб оплати', max_length=20, choices=PAYMENT_CHOICES, default='cod'
    )
    payment_status = models.CharField(
        'Статус оплати', max_length=20,
        choices=PAYMENT_STATUS_CHOICES, default='pending'
    )
    payment_id = models.CharField('ID платежу', max_length=200, blank=True)
    keycrm_order_id = models.PositiveBigIntegerField(
        'ID замовлення KeyCRM', null=True, blank=True,
    )
    keycrm_payment_id = models.PositiveBigIntegerField(
        'ID оплати KeyCRM', null=True, blank=True,
    )
    gclid = models.CharField('gclid', max_length=500, blank=True)
    gbraid = models.CharField('gbraid', max_length=500, blank=True)
    wbraid = models.CharField('wbraid', max_length=500, blank=True)
    utm_source = models.CharField('utm_source', max_length=255, blank=True)
    utm_medium = models.CharField('utm_medium', max_length=255, blank=True)
    utm_campaign = models.CharField('utm_campaign', max_length=255, blank=True)
    utm_term = models.CharField('utm_term', max_length=255, blank=True)
    utm_content = models.CharField('utm_content', max_length=255, blank=True)
    status = models.CharField(
        'Статус', max_length=20, choices=STATUS_CHOICES, default='new'
    )
    total = models.DecimalField('Сума', max_digits=12, decimal_places=2, default=0)
    shipment_origin = models.ForeignKey(
        'shipping.ShipmentOrigin',
        verbose_name='Точка відправки',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    parcel_weight = models.DecimalField(
        'Вага посилки, кг',
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
        help_text='Якщо порожньо — вага з налаштувань ТТН.',
    )
    parcel_length = models.PositiveIntegerField(
        'Довжина, см',
        null=True,
        blank=True,
        help_text='Якщо порожньо — значення з налаштувань ТТН.',
    )
    parcel_width = models.PositiveIntegerField('Ширина, см', null=True, blank=True)
    parcel_height = models.PositiveIntegerField('Висота, см', null=True, blank=True)
    ttn_number = models.CharField('Номер ТТН', max_length=50, blank=True, db_index=True)
    ttn_ref = models.CharField('Ref ТТН', max_length=64, blank=True)
    ttn_status = models.CharField(
        'Статус ТТН',
        max_length=20,
        blank=True,
        default='',
        choices=[
            ('', '—'),
            ('created', 'Створено'),
            ('error', 'Помилка'),
        ],
    )
    ttn_error = models.TextField('Помилка ТТН', blank=True)
    ttn_created_at = models.DateTimeField('ТТН створено', null=True, blank=True)
    ttn_delivery_cost = models.DecimalField(
        'Вартість доставки НП',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    updated_at = models.DateTimeField('Дата оновлення', auto_now=True)

    class Meta:
        verbose_name = 'Замовлення'
        verbose_name_plural = 'Замовлення'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self._state.adding and not self.shipment_origin_id:
            origin_id = _active_default_origin_id()
            if origin_id:
                self.shipment_origin_id = origin_id
                update_fields = kwargs.get('update_fields')
                if update_fields is not None:
                    kwargs['update_fields'] = list(
                        dict.fromkeys([*update_fields, 'shipment_origin'])
                    )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Замовлення #{self.id}"

    @property
    def order_number(self):
        return f"{self.id:06d}"


def _active_default_origin_id():
    try:
        from shipping.models import ShipmentOrigin
        return (
            ShipmentOrigin.objects.filter(is_default=True, is_active=True)
            .values_list('pk', flat=True)
            .first()
        )
    except DatabaseError:
        return None


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, verbose_name='Замовлення',
        related_name='items', on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, verbose_name='Товар',
        on_delete=models.SET_NULL, null=True
    )
    product_name = models.CharField('Назва товару', max_length=400)
    product_sku = models.CharField('Артикул', max_length=50)
    price = models.DecimalField('Ціна', max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField('Кількість', default=1)

    class Meta:
        verbose_name = 'Товар замовлення'
        verbose_name_plural = 'Товари замовлення'

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    @property
    def total(self):
        return self.price * self.quantity


class OfflineConversionLog(models.Model):
    STATUS_UPLOADED = 'uploaded'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_UPLOADED, 'Вивантажено'),
        (STATUS_FAILED, 'Помилка'),
    ]

    keycrm_order_id = models.PositiveBigIntegerField(
        'ID замовлення KeyCRM', unique=True,
    )
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES)
    order_date = models.DateTimeField('Дата замовлення', null=True, blank=True)
    order_status = models.CharField(
        'Статус KeyCRM', max_length=100, blank=True,
    )
    amount = models.DecimalField(
        'Сума', max_digits=12, decimal_places=2, null=True, blank=True,
    )
    utm_campaign = models.CharField('utm_campaign', max_length=255, blank=True)
    has_gclid = models.BooleanField('Є click id', default=False)
    has_contact = models.BooleanField('Є контакт', default=False)
    uploaded_at = models.DateTimeField('Час вивантаження', null=True, blank=True)
    error = models.TextField('Помилка', blank=True)
    attempts = models.PositiveIntegerField('Спроби', default=0)
    last_attempt_at = models.DateTimeField('Остання спроба', null=True, blank=True)
    created_at = models.DateTimeField('Створено', auto_now_add=True)

    class Meta:
        verbose_name = 'Офлайн-конверсія Google Ads'
        verbose_name_plural = 'Офлайн-конверсії Google Ads'
        ordering = ['-created_at']

    def __str__(self):
        return f'KeyCRM #{self.keycrm_order_id} ({self.status})'
