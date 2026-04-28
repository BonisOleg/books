from django.db import models
from django.urls import reverse

from tinymce.models import HTMLField


class SiteSettings(models.Model):
    site_name = models.CharField('Назва сайту', max_length=200, default='Магазин книжок')
    site_description = HTMLField('Опис сайту (головна)', blank=True)
    logo = models.ImageField(
        'Логотип', upload_to='site/', blank=True,
        help_text='Рекомендований розмір: 200×80 px (PNG/SVG, прозорий фон).'
    )
    favicon = models.ImageField(
        'Favicon', upload_to='site/', blank=True,
        help_text='Рекомендований розмір: 64×64 px або 32×32 px (PNG/ICO).'
    )
    email = models.EmailField('Email', blank=True)
    address = models.CharField('Адреса', max_length=300, blank=True)
    phone_1 = models.CharField('Телефон 1', max_length=30, blank=True)
    phone_2 = models.CharField('Телефон 2', max_length=30, blank=True)
    phone_3 = models.CharField('Телефон 3', max_length=30, blank=True)
    telegram_url = models.URLField('Telegram', blank=True)
    viber_url = models.URLField('Viber', blank=True)
    facebook_url = models.URLField('Facebook', blank=True)
    instagram_url = models.URLField('Instagram', blank=True)
    youtube_url = models.URLField('YouTube', blank=True)
    tiktok_url = models.URLField('TikTok', blank=True)
    promo_banner_text = models.CharField('Промо-банер текст', max_length=300, blank=True)
    promo_banner_url = models.URLField('Промо-банер посилання', blank=True)
    seo_home_title = models.CharField('SEO title головної', max_length=200, blank=True)
    seo_home_description = models.TextField('SEO description головної', blank=True)
    work_schedule = models.TextField('Графік роботи', blank=True,
                                     default='Пн-Пт: 09:00-19:00\nСб-Нд: 10:00-18:00')
    contact_person = models.CharField('Контактна особа', max_length=100, blank=True)
    return_policy = models.TextField(
        'Умови повернення та обміну', blank=True,
        default='Повернення можливе протягом 14 днів після отримання (для товарів належної якості).'
    )
    online_consultant_code = models.TextField(
        'Код онлайн-консультанта', blank=True,
        help_text='Вставте скрипт-код від Tawk.to, JivoSite, Crisp або іншого чат-сервісу'
    )

    primary_color = models.CharField(
        'Основний колір', max_length=20, blank=True,
        help_text='HEX, наприклад #0d0d0d. Якщо порожньо — використовується дефолт.'
    )
    accent_color = models.CharField(
        'Акцентний колір', max_length=20, blank=True,
        help_text='HEX, наприклад #c9a25b. Кнопки, ціни, акценти.'
    )
    bg_color = models.CharField(
        'Колір фону сайту', max_length=20, blank=True,
        help_text='HEX, наприклад #0a0a0a.'
    )
    text_color = models.CharField(
        'Колір тексту', max_length=20, blank=True,
        help_text='HEX, наприклад #ececec.'
    )

    google_tag_manager_id = models.CharField(
        'Google Tag Manager ID', max_length=50, blank=True,
        help_text='Наприклад: GTM-XXXXXXX. Якщо задано — підключається GTM скрипт.'
    )
    google_analytics_id = models.CharField(
        'Google Analytics ID', max_length=50, blank=True,
        help_text='Наприклад: G-XXXXXXXXXX. Якщо задано — підключається gtag.js.'
    )
    google_ads_conversion_id = models.CharField(
        'Google Ads Conversion ID', max_length=50, blank=True,
        help_text='Наприклад: AW-123456789. Для відстеження конверсій реклами.'
    )
    facebook_pixel_id = models.CharField(
        'Facebook Pixel ID', max_length=50, blank=True
    )

    enable_ru = models.BooleanField('Увімкнути російську', default=False)
    enable_en = models.BooleanField('Увімкнути англійську', default=False)

    class Meta:
        verbose_name = 'Налаштування сайту'
        verbose_name_plural = 'Налаштування сайту'

    def __str__(self):
        return self.site_name

    def get_phones(self):
        return [p for p in [self.phone_1, self.phone_2, self.phone_3] if p]


class FAQ(models.Model):
    SCOPE_CHOICES = [
        ('global', 'Глобальний (на всіх сторінках товарів та статей)'),
        ('product', 'Лише на сторінках товарів'),
        ('blog', 'Лише на сторінках статей/новин'),
        ('page', 'Лише на текстових сторінках'),
    ]

    question = models.CharField('Питання', max_length=400)
    answer = HTMLField('Відповідь')
    scope = models.CharField(
        'Розташування', max_length=20, choices=SCOPE_CHOICES, default='global'
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    is_published = models.BooleanField('Опубліковано', default=True)
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)

    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQ'
        ordering = ['order', 'id']

    def __str__(self):
        return self.question


class Banner(models.Model):
    POSITION_CHOICES = [
        ('home_hero', 'Головна — головний банер'),
        ('home_middle', 'Головна — посередині сторінки'),
        ('home_bottom', 'Головна — унизу сторінки'),
        ('catalog_top', 'Каталог — над списком товарів'),
        ('product_bottom', 'Сторінка товару — унизу'),
        ('footer_top', 'Над футером'),
    ]

    title = models.CharField('Назва (для адмінки)', max_length=200)
    image = models.ImageField(
        'Зображення', upload_to='banners/',
        help_text='Десктоп: 1280×360 px (або 1920×540 px); мобільний: 720×360 px. JPG/WEBP.'
    )
    image_mobile = models.ImageField(
        'Зображення (моб.)', upload_to='banners/', blank=True,
        help_text='Необов\'язково. Якщо порожньо — використовується основне зображення.'
    )
    alt_text = models.CharField('Alt текст', max_length=200, blank=True)
    link = models.URLField('Посилання', blank=True)
    open_in_new_tab = models.BooleanField('Відкривати в новій вкладці', default=False)
    position = models.CharField(
        'Розташування', max_length=30, choices=POSITION_CHOICES, default='home_hero'
    )
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активний', default=True)
    start_date = models.DateTimeField(
        'Початок показу', null=True, blank=True,
        help_text='Якщо порожньо — показується одразу.'
    )
    end_date = models.DateTimeField(
        'Кінець показу', null=True, blank=True,
        help_text='Якщо порожньо — показується без обмеження часу.'
    )
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)

    class Meta:
        verbose_name = 'Банер'
        verbose_name_plural = 'Банери'
        ordering = ['position', 'order', '-created_at']

    def __str__(self):
        return self.title


class Page(models.Model):
    title = models.CharField('Заголовок', max_length=200)
    slug = models.SlugField(
        'URL', unique=True, max_length=100,
        help_text='Наприклад: about, delivery, payment, returns. Використовується у посиланнях.'
    )
    content = HTMLField(
        'Контент', blank=True,
        help_text='Підтримує форматування: абзаци, списки, акценти, посилання.'
    )
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)
    show_in_footer = models.BooleanField(
        'Показувати у футері', default=True,
        help_text='Якщо увімкнено — посилання з\'явиться у блоці «Інформація» у футері.'
    )
    footer_order = models.PositiveIntegerField('Порядок у футері', default=0)
    is_published = models.BooleanField('Опубліковано', default=True)
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    updated_at = models.DateTimeField('Дата оновлення', auto_now=True)

    class Meta:
        verbose_name = 'Сторінка'
        verbose_name_plural = 'Сторінки'
        ordering = ['footer_order', 'title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('core:page', kwargs={'slug': self.slug})


class SEOTemplate(models.Model):
    name = models.CharField('Назва шаблону', max_length=100, unique=True)
    meta_title_template = models.CharField(
        'Шаблон title', max_length=300,
        help_text='Доступні змінні: {name}, {category}, {price}, {site_name}'
    )
    meta_description_template = models.TextField(
        'Шаблон description',
        help_text='Доступні змінні: {name}, {category}, {price}, {site_name}'
    )

    class Meta:
        verbose_name = 'SEO шаблон'
        verbose_name_plural = 'SEO шаблони'

    def __str__(self):
        return self.name
