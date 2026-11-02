from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Count, Q
from django.urls import reverse

from tinymce.models import HTMLField

from products.youtube import YOUTUBE_URL_ERROR, parse_youtube_url, youtube_embed_url


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
    google_product_category = models.CharField(
        'Google product category ID', max_length=20, blank=True,
        help_text='Числовий ID з Google Taxonomy. Книги: 784. '
                  'Якщо порожньо — успадковується від батьківської категорії або 784.',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)
    exclude_from_feeds = models.BooleanField(
        'Виключити з VIP/Middle фідів',
        default=False,
        help_text='Товари цієї категорії (і підкатегорій) не потрапляють у /feeds/feed_vip.xml '
                  'та /feeds/feed_middle.xml. Старий google-merchant.xml не змінюється.',
    )

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


class ProductQuerySet(models.QuerySet):
    def with_rating(self):
        """Середнє і кількість лише схвалених відгуків, одним annotate."""
        approved = Q(reviews__is_approved=True)
        return self.annotate(
            rating_avg=Avg('reviews__rating', filter=approved),
            rating_count=Count('reviews', distinct=True, filter=approved),
        )


class Product(models.Model):
    objects = ProductQuerySet.as_manager()

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
    order_info = HTMLField(
        'Інформація для замовлення', blank=True,
        help_text='Відображається у вкладці «Інформація для замовлення» на сторінці товару. '
                  'Якщо залишити порожнім — показуватиметься стандартний текст.',
    )
    price = models.DecimalField('Ціна', max_digits=12, decimal_places=2)
    old_price = models.DecimalField(
        'Стара ціна', max_digits=12, decimal_places=2, null=True, blank=True
    )
    stock_status = models.CharField(
        'Наявність', max_length=20,
        choices=STOCK_CHOICES, default='in_stock'
    )
    shipping_time = models.CharField(
        'Час відправки',
        max_length=60,
        blank=True,
        default='',
        help_text='Короткий рядок біля наявності на сторінці товару. '
                  'Якщо порожньо — береться значення з налаштувань сайту. '
                  'Якщо і там порожньо — рядок не показується.',
    )
    show_consult_button = models.BooleanField(
        'Кнопка «Проконсультувати»',
        default=False,
        help_text='Увімкніть, щоб на сторінці цього товару показувати кнопку консультації.',
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
    sale_end_date = models.DateTimeField(
        'Кінець акції (таймер)',
        null=True, blank=True,
        help_text='Встановіть дату завершення — таймер запуститься автоматично. '
                  'Очистіть поле, коли акція закінчується.',
    )
    manufacturer = models.CharField('Виробник', max_length=200, blank=True)
    country = models.CharField('Країна', max_length=100, blank=True)
    weight = models.DecimalField(
        'Вага (кг)', max_digits=8, decimal_places=2, null=True, blank=True
    )
    condition = models.CharField('Стан', max_length=50, blank=True, default='')
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)
    is_active = models.BooleanField('Активний', default=True)
    is_bestseller = models.BooleanField(
        'Топ продажів',
        default=False,
        help_text='Товар потрапляє в групи з автодобором «Топ продажів».',
    )
    exclude_from_feeds = models.BooleanField(
        'Виключити з VIP/Middle фідів',
        default=False,
        help_text='Товар не потрапляє у /feeds/feed_vip.xml та /feeds/feed_middle.xml. '
                  'Старий google-merchant.xml не змінюється.',
    )
    search_name = models.TextField('Індекс назви', editable=False, blank=True, default='')
    search_text = models.TextField('Індекс пошуку', editable=False, blank=True, default='')
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

    def clean(self):
        from core.seo import normalize_product_name
        for fname in ('name', 'name_uk', 'name_en', 'name_ru'):
            if hasattr(self, fname):
                val = getattr(self, fname)
                if isinstance(val, str) and val:
                    setattr(self, fname, normalize_product_name(val))

    def save(self, *args, **kwargs):
        from core.seo import normalize_product_name
        for fname in ('name', 'name_uk', 'name_en', 'name_ru'):
            if hasattr(self, fname):
                val = getattr(self, fname)
                if isinstance(val, str) and val:
                    setattr(self, fname, normalize_product_name(val))
        super().save(*args, **kwargs)

    @property
    def main_image(self):
        return self.images.first()

    @property
    def sale_timer_active(self):
        from django.utils import timezone
        return bool(self.sale_end_date and self.sale_end_date > timezone.now())

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

    @property
    def display_shipping_time(self):
        own = (self.shipping_time or '').strip()
        if own:
            return own
        from core.models import SiteSettings
        site = SiteSettings.objects.first()
        if site is None:
            return ''
        return (site.default_shipping_time or '').strip()


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
        url = (self.video_url or '').strip()
        if not url and not self.video_file:
            raise ValidationError(
                'Вкажіть посилання на YouTube або завантажте файл відео.'
            )
        if url:
            try:
                parse_youtube_url(url)
            except ValueError:
                raise ValidationError({'video_url': YOUTUBE_URL_ERROR}) from None

    @property
    def embed_url(self):
        if not self.video_url:
            return ''
        try:
            return youtube_embed_url(self.video_url)
        except ValueError:
            return ''


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


class FilterGroup(models.Model):
    FILTER_TYPE_CHOICES = [
        ('price_range', 'Діапазон ціни'),
        ('stock', 'Наявність'),
        ('badge', 'Мітки (бейджі)'),
        ('subcategory', 'Підкатегорії'),
    ]

    name = models.CharField(
        'Назва групи', max_length=100,
        help_text='Заголовок блоку фільтру на сайті. Наприклад: «Бюджет», «Наявність».',
    )
    filter_type = models.CharField(
        'Тип фільтру', max_length=20, choices=FILTER_TYPE_CHOICES,
        help_text='Визначає, як цей фільтр застосовується до товарів.',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активний', default=True)
    categories = models.ManyToManyField(
        Category, verbose_name='Категорії', blank=True,
        related_name='filter_groups',
        help_text='Залиш пустим — фільтр показується у всіх категоріях.',
    )

    class Meta:
        verbose_name = 'Група фільтрів'
        verbose_name_plural = 'Групи фільтрів'
        ordering = ['order']

    def __str__(self):
        return self.name


class FilterOption(models.Model):
    group = models.ForeignKey(
        FilterGroup, verbose_name='Група',
        related_name='options', on_delete=models.CASCADE,
    )
    label = models.CharField(
        'Підпис', max_length=100,
        help_text='Текст, що бачить відвідувач. Наприклад: «В наявності», «Акція».',
    )
    value = models.CharField(
        'Значення (value)', max_length=100,
        help_text='Технічний ключ без пробілів. Наприклад: in_stock, sale, new.',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Варіант фільтру'
        verbose_name_plural = 'Варіанти фільтру'
        ordering = ['order']

    def __str__(self):
        return f"{self.group.name}: {self.label}"


class ProductGroupQuerySet(models.QuerySet):
    def visible_now(self, now=None):
        from django.utils import timezone

        moment = timezone.now() if now is None else now
        return self.filter(is_active=True).filter(
            models.Q(date_from__isnull=True) | models.Q(date_from__lte=moment),
        ).filter(
            models.Q(date_to__isnull=True) | models.Q(date_to__gte=moment),
        )


class ProductGroup(models.Model):
    AUTO_MANUAL = ''
    AUTO_BESTSELLER = 'bestseller'
    AUTO_SOURCE_CHOICES = [
        (AUTO_MANUAL, 'Лише вручну'),
        (AUTO_BESTSELLER, 'Товари з прапорцем «Топ продажів»'),
    ]

    name = models.CharField('Назва', max_length=200)
    slug = models.SlugField(
        'URL', unique=True, max_length=200,
        help_text='Латиницею. Адреса сторінки: /group/<slug>/.',
    )
    products = models.ManyToManyField(
        Product, verbose_name='Товари', blank=True, related_name='groups',
    )
    show_in_header = models.BooleanField(
        'Показувати в меню «Усі товари»', default=False,
        help_text='Якщо увімкнено — посилання з’явиться у випадаючому меню «Усі товари» та в мобільному меню.',
    )
    auto_source = models.CharField(
        'Автодобір',
        max_length=20,
        choices=AUTO_SOURCE_CHOICES,
        blank=True,
        default=AUTO_MANUAL,
        help_text='До обраних товарів можна автоматично додати товари з прапорцем «Топ продажів».',
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    date_from = models.DateTimeField(
        'Початок показу', null=True, blank=True,
        help_text='Якщо порожньо — без обмеження початку.',
    )
    date_to = models.DateTimeField(
        'Кінець показу', null=True, blank=True,
        help_text='Якщо порожньо — без обмеження кінця.',
    )
    is_active = models.BooleanField('Активна', default=True)
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)

    objects = ProductGroupQuerySet.as_manager()

    class Meta:
        verbose_name = 'Група товарів'
        verbose_name_plural = 'Групи товарів'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError({
                'date_to': 'Дата завершення має бути не раніше за дату початку.',
            })

    def visible_now(self, now=None):
        from django.utils import timezone

        moment = timezone.now() if now is None else now
        if not self.is_active:
            return False
        if self.date_from is not None and self.date_from > moment:
            return False
        if self.date_to is not None and self.date_to < moment:
            return False
        return True

    def get_absolute_url(self):
        return reverse('product_group', kwargs={'slug': self.slug})

    def get_products(self):
        if self.pk:
            manual = self.products.all()
        else:
            manual = Product.objects.none()
        if self.auto_source != self.AUTO_BESTSELLER:
            return manual
        return Product.objects.filter(
            models.Q(pk__in=manual.values('pk')) | models.Q(is_bestseller=True)
        )


class FilterAttribute(models.Model):
    """Довільний фільтр каталогу, окремо від чотирьох типів FilterGroup.

    M2M до товарів навмисно на FilterValue, а не на Product: модель товару
    паралельно змінюють інші гілки, тож її стан у міграціях не чіпаємо.
    Порожній список категорій означає «показувати скрізь» (каталог і категорії).
    Обрана категорія показується також у всіх її підкатегоріях.
    """

    name = models.CharField('Назва', max_length=100)
    slug = models.SlugField(
        'Код', max_length=80, unique=True,
        help_text='Латиницею, без пробілів. Наприклад: color, cover.',
    )
    position = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активний', default=True)
    categories = models.ManyToManyField(
        Category,
        verbose_name='Категорії',
        blank=True,
        related_name='filter_attributes',
        help_text='Порожньо — фільтр показується в усіх категоріях.',
    )

    class Meta:
        verbose_name = 'Атрибут фільтра'
        verbose_name_plural = 'Атрибути фільтрів'
        ordering = ['position', 'name']

    def __str__(self):
        return self.name


class FilterValue(models.Model):
    attribute = models.ForeignKey(
        FilterAttribute,
        verbose_name='Атрибут',
        related_name='values',
        on_delete=models.CASCADE,
    )
    name = models.CharField('Назва', max_length=100)
    slug = models.SlugField(
        'Код', max_length=80,
        help_text='Латиницею, унікальний у межах атрибута. Наприклад: red.',
    )
    position = models.PositiveIntegerField('Порядок', default=0)
    products = models.ManyToManyField(
        Product,
        verbose_name='Товари',
        related_name='filter_values',
        blank=True,
    )

    class Meta:
        verbose_name = 'Значення фільтра'
        verbose_name_plural = 'Значення фільтрів'
        ordering = ['position', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=('attribute', 'slug'),
                name='uniq_filter_value_attribute_slug',
            ),
        ]

    def __str__(self):
        return f'{self.attribute.name}: {self.name}'


class ConsultationRequest(models.Model):
    product = models.ForeignKey(
        Product, verbose_name='Товар',
        related_name='consultation_requests',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    product_name = models.CharField('Назва товару', max_length=400, blank=True, default='')
    product_url = models.URLField('Посилання на товар', max_length=500, blank=True, default='')
    name = models.CharField('Ім\'я', max_length=150)
    phone = models.CharField('Телефон', max_length=30)
    question = models.TextField('Питання')
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    is_processed = models.BooleanField('Опрацьовано', default=False)

    class Meta:
        verbose_name = 'Заявка на консультацію'
        verbose_name_plural = 'Заявки на консультацію'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.phone}'
