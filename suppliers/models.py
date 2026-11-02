from decimal import Decimal

from django.db import models
from django.utils import timezone

from suppliers.constants import (
    FEED_GOOGLE_MERCHANT_RSS,
    PRICE_AS_IS,
    PRICE_MARKUP,
    ROUND_NONE,
    ROUND_ONE,
    ROUND_TEN,
)


class Supplier(models.Model):
    class FeedFormat(models.TextChoices):
        GOOGLE_MERCHANT_RSS = FEED_GOOGLE_MERCHANT_RSS, 'Google Merchant RSS'

    class PriceRule(models.TextChoices):
        AS_IS = PRICE_AS_IS, 'Як у фіді'
        MARKUP = PRICE_MARKUP, 'Націнка %'

    class Rounding(models.TextChoices):
        NONE = ROUND_NONE, 'До копійок'
        ONE = ROUND_ONE, 'До гривні'
        TEN = ROUND_TEN, 'До десятків'

    name = models.CharField('Назва', max_length=200)
    feed_url = models.URLField(
        'URL фіду',
        max_length=500,
        help_text='http або https. Для перевірки файлом команду можна запустити з --file.',
    )
    feed_format = models.CharField(
        'Формат фіду',
        max_length=32,
        choices=FeedFormat.choices,
        default=FeedFormat.GOOGLE_MERCHANT_RSS,
    )
    price_rule = models.CharField(
        'Правило ціни',
        max_length=16,
        choices=PriceRule.choices,
        default=PriceRule.AS_IS,
    )
    markup_percent = models.DecimalField(
        'Націнка, %',
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Враховується, якщо правило ціни — «Націнка %».',
    )
    rounding = models.CharField(
        'Округлення',
        max_length=8,
        choices=Rounding.choices,
        default=Rounding.NONE,
        help_text='До копійок (0,01), до гривні або до десятків. Половина округлюється вгору.',
    )
    update_price = models.BooleanField(
        'Оновлювати ціну',
        default=True,
        help_text='Змінюється лише ціна продажу. Стара ціна лишається як є.',
    )
    mark_missing_out_of_stock = models.BooleanField(
        'Товари, яких немає у фіді — ставити «Немає в наявності»',
        default=False,
    )
    is_active = models.BooleanField('Активний', default=True)
    created_at = models.DateTimeField('Створено', auto_now_add=True)
    updated_at = models.DateTimeField('Оновлено', auto_now=True)

    class Meta:
        verbose_name = 'Постачальник'
        verbose_name_plural = 'Постачальники'
        ordering = ['name']

    def __str__(self):
        return self.name


class SupplierSyncRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = 'running', 'Виконується'
        OK = 'ok', 'Успішно'
        FAILED = 'failed', 'Помилка'

    supplier = models.ForeignKey(
        Supplier,
        verbose_name='Постачальник',
        related_name='sync_runs',
        on_delete=models.CASCADE,
    )
    started_at = models.DateTimeField('Початок', default=timezone.now)
    finished_at = models.DateTimeField('Завершення', null=True, blank=True)
    dry_run = models.BooleanField('Пробний запуск', default=False)
    status = models.CharField(
        'Статус',
        max_length=16,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    items_in_feed = models.PositiveIntegerField('Товарів у фіді', default=0)
    matched = models.PositiveIntegerField('Збігів', default=0)
    price_changed = models.PositiveIntegerField('Змінено цін', default=0)
    not_in_feed = models.PositiveIntegerField('Немає у фіді', default=0)
    not_in_catalog = models.PositiveIntegerField('Немає в каталозі', default=0)
    marked_out = models.PositiveIntegerField('Позначено відсутніми', default=0)
    errors = models.PositiveIntegerField('Помилки', default=0)
    report = models.TextField('Звіт', blank=True, default='')
    report_json = models.JSONField('Звіт (JSON)', blank=True, default=dict)

    class Meta:
        verbose_name = 'Запуск синхронізації'
        verbose_name_plural = 'Запуски синхронізації'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['supplier', 'started_at']),
        ]

    def __str__(self):
        moment = timezone.localtime(self.started_at).strftime('%Y-%m-%d %H:%M')
        return f'{self.supplier} — {moment} ({self.get_status_display()})'
