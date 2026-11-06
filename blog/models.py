from django.db import models
from django.urls import reverse
from django.utils import timezone

from tinymce.models import HTMLField

from blog.cover_link import cover_link_is_external, resolve_cover_href, validate_cover_link


class PublishedQuerySet(models.QuerySet):
    def published(self):
        """Записи з прапорцем «Опубліковано», чия дата вже настала (Київ)."""
        return self.filter(
            is_published=True,
            published_at__lte=timezone.now(),
        ).order_by('-published_at', '-created_at')


class CoverLinkMixin:
    @property
    def cover_href(self):
        return resolve_cover_href(self.cover_link, self.get_absolute_url())

    @property
    def cover_link_is_external(self):
        return cover_link_is_external(self.cover_link)


class Article(CoverLinkMixin, models.Model):
    title = models.CharField('Заголовок', max_length=300)
    slug = models.SlugField(unique=True, max_length=300)
    content = HTMLField('Контент')
    excerpt = models.TextField('Короткий опис', blank=True)
    image = models.ImageField(
        'Зображення', upload_to='blog/articles/', blank=True,
        help_text='Рекомендований розмір: 1200×675 px (співвідношення 16:9), JPG/WEBP.'
    )
    cover_link = models.CharField(
        'Посилання із заставки',
        max_length=500,
        blank=True,
        default='',
        validators=[validate_cover_link],
        help_text='Абсолютне http(s) або відносний шлях (/catalog/). Порожньо — на сторінку запису.',
    )
    is_published = models.BooleanField('Опубліковано', default=True)
    published_at = models.DateTimeField(
        'Дата публікації',
        default=timezone.now,
        db_index=True,
        help_text=(
            'Запис з’явиться на сайті з цієї дати й часу (Київ). '
            'Майбутня дата — заплановано.'
        ),
    )
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    updated_at = models.DateTimeField('Дата оновлення', auto_now=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        verbose_name = 'Стаття'
        verbose_name_plural = 'Статті'
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog:article_detail', kwargs={'slug': self.slug})


class News(CoverLinkMixin, models.Model):
    title = models.CharField('Заголовок', max_length=300)
    slug = models.SlugField(unique=True, max_length=300)
    content = HTMLField('Контент')
    excerpt = models.TextField('Короткий опис', blank=True)
    image = models.ImageField(
        'Зображення', upload_to='blog/news/', blank=True,
        help_text='Рекомендований розмір: 1200×675 px (співвідношення 16:9), JPG/WEBP.'
    )
    cover_link = models.CharField(
        'Посилання із заставки',
        max_length=500,
        blank=True,
        default='',
        validators=[validate_cover_link],
        help_text='Абсолютне http(s) або відносний шлях (/catalog/). Порожньо — на сторінку запису.',
    )
    is_published = models.BooleanField('Опубліковано', default=True)
    published_at = models.DateTimeField(
        'Дата публікації',
        default=timezone.now,
        db_index=True,
        help_text=(
            'Запис з’явиться на сайті з цієї дати й часу (Київ). '
            'Майбутня дата — заплановано.'
        ),
    )
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    updated_at = models.DateTimeField('Дата оновлення', auto_now=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        verbose_name = 'Новина'
        verbose_name_plural = 'Новини'
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog:news_detail', kwargs={'slug': self.slug})
