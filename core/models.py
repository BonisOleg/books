from django.db import models


class SiteSettings(models.Model):
    site_name = models.CharField('Назва сайту', max_length=200, default='Магазин книжок')
    site_description = models.TextField('Опис сайту', blank=True)
    logo = models.ImageField('Логотип', upload_to='site/', blank=True)
    favicon = models.ImageField('Favicon', upload_to='site/', blank=True)
    email = models.EmailField('Email', blank=True)
    address = models.CharField('Адреса', max_length=300, blank=True)
    phone_1 = models.CharField('Телефон 1', max_length=30, blank=True)
    phone_2 = models.CharField('Телефон 2', max_length=30, blank=True)
    phone_3 = models.CharField('Телефон 3', max_length=30, blank=True)
    telegram_url = models.URLField('Telegram', blank=True)
    viber_url = models.URLField('Viber', blank=True)
    facebook_url = models.URLField('Facebook', blank=True)
    instagram_url = models.URLField('Instagram', blank=True)
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

    class Meta:
        verbose_name = 'Налаштування сайту'
        verbose_name_plural = 'Налаштування сайту'

    def __str__(self):
        return self.site_name

    def get_phones(self):
        return [p for p in [self.phone_1, self.phone_2, self.phone_3] if p]


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
