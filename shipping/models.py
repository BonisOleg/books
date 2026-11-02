from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import connection, models, transaction

DEFAULT_ORIGIN_ERROR = 'Може бути лише одна точка відправки за замовчуванням.'


class ShipmentOrigin(models.Model):
    KIND_WAREHOUSE = 'warehouse'
    KIND_ADDRESS = 'address_pickup'
    KIND_CHOICES = [
        (KIND_WAREHOUSE, 'Відділення'),
        (KIND_ADDRESS, 'Адресний забір'),
    ]

    name = models.CharField('Назва', max_length=200)
    kind = models.CharField('Тип', max_length=20, choices=KIND_CHOICES, default=KIND_WAREHOUSE)
    city_name = models.CharField('Місто', max_length=200, blank=True)
    city_ref = models.CharField('Ref міста', max_length=64, blank=True)
    warehouse_ref = models.CharField('Ref відділення', max_length=64, blank=True)
    warehouse_name = models.CharField('Відділення', max_length=300, blank=True)
    street_ref = models.CharField('Ref вулиці / адреси забору', max_length=64, blank=True)
    street_name = models.CharField('Вулиця', max_length=200, blank=True)
    building = models.CharField('Будинок', max_length=50, blank=True)
    is_active = models.BooleanField('Активна', default=True)
    is_default = models.BooleanField(
        'Типова точка',
        default=False,
        help_text='Лише одна точка може бути типовою. Щоб змінити, спочатку зніміть позначку з поточної.',
    )

    class Meta:
        verbose_name = 'Точка відправки'
        verbose_name_plural = 'Точки відправки'
        ordering = ['name', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['is_default'],
                condition=models.Q(is_default=True),
                name='shipping_single_default_origin',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.is_default:
            return
        if not self.is_active or self._other_defaults().exists():
            raise ValidationError({'is_default': DEFAULT_ORIGIN_ERROR})

    def _other_defaults(self):
        qs = ShipmentOrigin.objects.filter(is_default=True)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_default and not self.is_active:
                self.is_default = False
            elif self.is_default:
                qs = self._other_defaults()
                if connection.features.has_select_for_update:
                    qs = qs.select_for_update()
                qs.update(is_default=False)
            super().save(*args, **kwargs)


class NPTTNSettings(models.Model):
    PAYER_RECIPIENT = 'Recipient'
    PAYER_SENDER = 'Sender'
    PAYER_CHOICES = [
        (PAYER_RECIPIENT, 'Отримувач'),
        (PAYER_SENDER, 'Відправник'),
    ]
    CARGO_PARCEL = 'Parcel'
    CARGO_CARGO = 'Cargo'
    CARGO_DOCUMENTS = 'Documents'
    CARGO_CHOICES = [
        (CARGO_PARCEL, 'Посилка'),
        (CARGO_CARGO, 'Вантаж'),
        (CARGO_DOCUMENTS, 'Документи'),
    ]
    PAYMENT_CASH = 'Cash'
    PAYMENT_NONCASH = 'NonCash'
    PAYMENT_CHOICES = [
        (PAYMENT_CASH, 'Готівка'),
        (PAYMENT_NONCASH, 'Безготівка'),
    ]
    COD_AFTERPAYMENT = 'afterpayment'
    COD_BACKWARD = 'backward_money'
    COD_CHOICES = [
        (COD_AFTERPAYMENT, 'Контроль оплати'),
        (COD_BACKWARD, 'Грошовий переказ'),
    ]
    SENDER_ORGANIZATION = 'Organization'
    SENDER_PRIVATE = 'PrivatePerson'
    SENDER_CHOICES = [
        (SENDER_ORGANIZATION, 'Організація (ФОП)'),
        (SENDER_PRIVATE, 'Приватна особа'),
    ]

    default_weight = models.DecimalField(
        'Вага за замовчуванням, кг',
        max_digits=7,
        decimal_places=3,
        default=Decimal('1.000'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    length = models.PositiveIntegerField(
        'Довжина, см', default=20, validators=[MinValueValidator(1)],
    )
    width = models.PositiveIntegerField(
        'Ширина, см', default=15, validators=[MinValueValidator(1)],
    )
    height = models.PositiveIntegerField(
        'Висота, см', default=10, validators=[MinValueValidator(1)],
    )
    payer_type = models.CharField(
        'Хто платить за доставку', max_length=20, choices=PAYER_CHOICES, default=PAYER_RECIPIENT,
    )
    cargo_description = models.CharField('Опис вантажу', max_length=200, default='Товари')
    cargo_type = models.CharField(
        'Тип вантажу', max_length=20, choices=CARGO_CHOICES, default=CARGO_PARCEL,
    )
    payment_method = models.CharField(
        'Форма оплати доставки', max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_CASH,
    )
    auto_create_ttn = models.BooleanField(
        'Створювати ТТН автоматично',
        default=False,
        help_text=(
            'Накладений платіж — після оформлення. Онлайн-оплата — лише коли платіж '
            'підтверджено. Помилка ТТН не зупиняє чекаут.'
        ),
    )
    cod_mode = models.CharField(
        'Накладений платіж',
        max_length=20,
        choices=COD_CHOICES,
        default=COD_AFTERPAYMENT,
        help_text='Контроль оплати — комісія від суми. Грошовий переказ — зворотна доставка грошей.',
    )
    cod_payer_type = models.CharField(
        'Хто платить комісію післяплати',
        max_length=20,
        choices=PAYER_CHOICES,
        default=PAYER_RECIPIENT,
        help_text='Хто сплачує комісію контролю оплати або зворотну доставку.',
    )
    sender_ref = models.CharField(
        'Ref відправника',
        max_length=64,
        blank=True,
        help_text='Якщо порожньо — береться з кабінету НП (Counterparty Sender) і кешується.',
    )
    contact_sender_ref = models.CharField('Ref контактної особи', max_length=64, blank=True)
    sender_phone = models.CharField('Телефон відправника', max_length=30, blank=True)
    sender_type = models.CharField(
        'Тип відправника',
        max_length=20,
        choices=SENDER_CHOICES,
        default=SENDER_ORGANIZATION,
        help_text='Organization — ФОП або юридична особа в кабінеті Нової Пошти.',
    )

    class Meta:
        verbose_name = 'Налаштування ТТН Нової Пошти'
        verbose_name_plural = 'Налаштування ТТН Нової Пошти'

    def __str__(self):
        return 'Налаштування ТТН Нової Пошти'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
