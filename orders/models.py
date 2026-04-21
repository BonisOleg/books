from django.db import models
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
    warehouse = models.CharField('Відділення НП', max_length=300)
    warehouse_ref = models.CharField('Ref відділення', max_length=100, blank=True)
    comment = models.TextField('Коментар', blank=True)
    payment_method = models.CharField(
        'Спосіб оплати', max_length=20, choices=PAYMENT_CHOICES, default='cod'
    )
    payment_status = models.CharField(
        'Статус оплати', max_length=20,
        choices=PAYMENT_STATUS_CHOICES, default='pending'
    )
    payment_id = models.CharField('ID платежу', max_length=200, blank=True)
    status = models.CharField(
        'Статус', max_length=20, choices=STATUS_CHOICES, default='new'
    )
    total = models.DecimalField('Сума', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    updated_at = models.DateTimeField('Дата оновлення', auto_now=True)

    class Meta:
        verbose_name = 'Замовлення'
        verbose_name_plural = 'Замовлення'
        ordering = ['-created_at']

    def __str__(self):
        return f"Замовлення #{self.id}"

    @property
    def order_number(self):
        return f"{self.id:06d}"


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
