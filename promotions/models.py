from django.db import models
from django.utils import timezone
from products.models import Product


class Promotion(models.Model):
    product = models.ForeignKey(
        Product, verbose_name='Товар',
        related_name='promotions', on_delete=models.CASCADE
    )
    title = models.CharField('Назва акції', max_length=200)
    description = models.TextField('Опис', blank=True)
    start_date = models.DateTimeField('Початок')
    end_date = models.DateTimeField('Кінець')
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Акція'
        verbose_name_plural = 'Акції'
        ordering = ['-end_date']

    def __str__(self):
        return self.title

    @property
    def is_running(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    @property
    def time_remaining(self):
        now = timezone.now()
        if now < self.end_date:
            return (self.end_date - now).total_seconds()
        return 0


class UpsellGroup(models.Model):
    name = models.CharField('Назва групи', max_length=200)
    trigger_product = models.ForeignKey(
        Product, verbose_name='Товар-тригер',
        related_name='upsell_triggers', on_delete=models.CASCADE
    )
    suggested_products = models.ManyToManyField(
        Product, verbose_name='Рекомендовані товари',
        related_name='upsell_suggestions', blank=True
    )
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Upsell група'
        verbose_name_plural = 'Upsell групи'

    def __str__(self):
        return self.name


class GiftPickerQuestion(models.Model):
    text = models.CharField('Питання', max_length=300)
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активне', default=True)

    class Meta:
        verbose_name = 'Питання підбору подарунку'
        verbose_name_plural = 'Питання підбору подарунку'
        ordering = ['order']

    def __str__(self):
        return self.text


class GiftPickerOption(models.Model):
    question = models.ForeignKey(
        GiftPickerQuestion, verbose_name='Питання',
        related_name='options', on_delete=models.CASCADE
    )
    text = models.CharField('Варіант відповіді', max_length=200)
    categories = models.ManyToManyField(
        'products.Category', verbose_name='Категорії',
        blank=True
    )
    price_min = models.DecimalField(
        'Мін. ціна', max_digits=12, decimal_places=2,
        null=True, blank=True
    )
    price_max = models.DecimalField(
        'Макс. ціна', max_digits=12, decimal_places=2,
        null=True, blank=True
    )

    class Meta:
        verbose_name = 'Варіант відповіді'
        verbose_name_plural = 'Варіанти відповідей'

    def __str__(self):
        return self.text
