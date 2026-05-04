from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from tinymce.models import HTMLField


class Badge(models.Model):
    COLOR_CHOICES = [
        ('red', 'Червоний'),
        ('orange', 'Помаранчевий'),
        ('yellow', 'Жовтий'),
        ('green', 'Зелений'),
        ('blue', 'Синій'),
        ('purple', 'Фіолетовий'),
        ('pink', 'Рожевий'),
        ('gold', 'Золотий'),
        ('black', 'Чорний'),
    ]

    slug = models.SlugField(
        'Код', max_length=40, unique=True,
        help_text='Латиницею, без пробілів. Наприклад: sale, top, new, gift.'
    )
    name = models.CharField('Назва', max_length=100, help_text='Текст, який видно на товарі.')
    color = models.CharField(
        'Колір', max_length=20, choices=COLOR_CHOICES, default='red',
        help_text='Виберіть колір фону бейджа.'
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активний', default=True)

    class Meta:
        verbose_name = 'Бейдж'
        verbose_name_plural = 'Бейджі'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField('Назва', max_length=200)
    slug = models.SlugField('URL', unique=True, max_length=200)
    parent = models.ForeignKey(
        'self', verbose_name='Батьківська категорія',
        null=True, blank=True, on_delete=models.CASCADE,
        related_name='children'
    )
    description = HTMLField('Опис', blank=True)
    image = models.ImageField(
        'Зображення', upload_to='categories/', blank=True,
        help_text='Рекомендований розмір: 600×450 px (співвідношення 4:3), JPG/WEBP.'
    )
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Категорія'
        verbose_name_plural = 'Категорії'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:category', kwargs={'slug': self.slug})

    def get_ancestors(self, max_depth=10):
        ancestors = []
        cat = self.parent
        depth = 0
        while cat and depth < max_depth:
            ancestors.insert(0, cat)
            cat = cat.parent
            depth += 1
        return ancestors


class Product(models.Model):
    STOCK_CHOICES = [
        ('in_stock', 'В наявності'),
        ('ready', 'Готово до відправки'),
        ('order', 'Під замовлення'),
        ('out', 'Немає в наявності'),
    ]
    BADGE_CHOICES = [
        ('', '---'),
        ('sale', 'Акція'),
        ('top', 'Топ продажів'),
        ('new', 'Новинка'),
    ]

    name = models.CharField('Назва', max_length=400)
    slug = models.SlugField('URL', unique=True, max_length=400)
    sku = models.CharField('Артикул', max_length=50, unique=True)
    sku_manufacturer = models.CharField(
        'Артикул виробника', max_length=100, blank=True,
        help_text='Заводський / код постачальника. Бачать лише адміністратори.'
    )
    categories = models.ManyToManyField(
        Category, verbose_name='Категорії',
        blank=True, related_name='products'
    )
    description = HTMLField('Опис')
    short_description = HTMLField('Короткий опис', blank=True)
    price = models.DecimalField('Ціна', max_digits=12, decimal_places=2)
    old_price = models.DecimalField(
        'Стара ціна', max_digits=12, decimal_places=2, null=True, blank=True
    )
    stock_status = models.CharField(
        'Наявність', max_length=20,
        choices=STOCK_CHOICES, default='in_stock'
    )
    badge = models.CharField(
        'Бейдж (старий)', max_length=20,
        choices=BADGE_CHOICES, blank=True, default='',
        help_text='Залишено для зворотної сумісності. Використовуйте поле «Бейдж (новий)».'
    )
    badge_obj = models.ForeignKey(
        Badge, verbose_name='Бейдж',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='products'
    )
    discount_percent = models.PositiveIntegerField('Знижка %', default=0)
    manufacturer = models.CharField('Виробник', max_length=200, blank=True)
    country = models.CharField('Країна', max_length=100, blank=True)
    weight = models.DecimalField(
        'Вага (кг)', max_digits=8, decimal_places=2, null=True, blank=True
    )
    condition = models.CharField('Стан', max_length=50, blank=True, default='')
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)
    is_active = models.BooleanField('Активний', default=True)
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    updated_at = models.DateTimeField('Дата оновлення', auto_now=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товари'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:detail', kwargs={'slug': self.slug})

    @property
    def main_image(self):
        return self.images.first()

    @property
    def has_discount(self):
        return self.old_price and self.old_price > self.price

    @property
    def computed_discount_percent(self):
        if self.has_discount:
            return int(((self.old_price - self.price) / self.old_price) * 100)
        return self.discount_percent

    @property
    def availability_schema(self):
        mapping = {
            'in_stock': 'https://schema.org/InStock',
            'ready': 'https://schema.org/InStock',
            'order': 'https://schema.org/PreOrder',
            'out': 'https://schema.org/OutOfStock',
        }
        return mapping.get(self.stock_status, 'https://schema.org/InStock')


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, verbose_name='Товар',
        related_name='images', on_delete=models.CASCADE
    )
    image = models.ImageField(
        'Зображення', upload_to='products/',
        help_text='Рекомендований розмір: 1000×1000 px (квадрат), JPG/WEBP, до 1.5 МБ.'
    )
    alt_text = models.CharField('Alt текст', max_length=200, blank=True)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Фото товару'
        verbose_name_plural = 'Фото товарів'
        ordering = ['order']

    def __str__(self):
        return f"Фото {self.order} для {self.product.name}"

    def clean(self):
        if not self.pk and self.product_id:
            count = ProductImage.objects.filter(product_id=self.product_id).count()
            if count >= 20:
                raise ValidationError('Максимум 20 фото на товар.')


class ProductVideo(models.Model):
    product = models.ForeignKey(
        Product, verbose_name='Товар',
        related_name='videos', on_delete=models.CASCADE
    )
    video_url = models.URLField('URL відео (YouTube/Vimeo)', blank=True)
    video_file = models.FileField(
        'Файл відео', upload_to='products/videos/', blank=True
    )
    poster = models.ImageField('Постер', upload_to='products/posters/', blank=True)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Відео товару'
        verbose_name_plural = 'Відео товарів'
        ordering = ['order']

    def __str__(self):
        return f"Відео для {self.product.name}"

    def clean(self):
        if not self.video_url and not self.video_file:
            raise ValidationError(
                'Вкажіть URL відео (YouTube/Vimeo) або завантажте файл відео.'
            )


class ProductAttribute(models.Model):
    product = models.ForeignKey(
        Product, verbose_name='Товар',
        related_name='attributes', on_delete=models.CASCADE
    )
    name = models.CharField('Назва', max_length=200)
    value = models.CharField('Значення', max_length=400)
    order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Характеристика'
        verbose_name_plural = 'Характеристики'
        ordering = ['order']

    def __str__(self):
        return f"{self.name}: {self.value}"
