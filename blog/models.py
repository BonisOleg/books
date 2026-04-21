from django.db import models
from django.urls import reverse


class Article(models.Model):
    title = models.CharField('Заголовок', max_length=300)
    slug = models.SlugField(unique=True, max_length=300)
    content = models.TextField('Контент')
    excerpt = models.TextField('Короткий опис', blank=True)
    image = models.ImageField('Зображення', upload_to='blog/articles/', blank=True)
    is_published = models.BooleanField('Опубліковано', default=True)
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    updated_at = models.DateTimeField('Дата оновлення', auto_now=True)

    class Meta:
        verbose_name = 'Стаття'
        verbose_name_plural = 'Статті'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog:article_detail', kwargs={'slug': self.slug})


class News(models.Model):
    title = models.CharField('Заголовок', max_length=300)
    slug = models.SlugField(unique=True, max_length=300)
    content = models.TextField('Контент')
    excerpt = models.TextField('Короткий опис', blank=True)
    image = models.ImageField('Зображення', upload_to='blog/news/', blank=True)
    is_published = models.BooleanField('Опубліковано', default=True)
    meta_title = models.CharField('SEO Title', max_length=200, blank=True)
    meta_description = models.TextField('SEO Description', blank=True)
    created_at = models.DateTimeField('Дата створення', auto_now_add=True)
    updated_at = models.DateTimeField('Дата оновлення', auto_now=True)

    class Meta:
        verbose_name = 'Новина'
        verbose_name_plural = 'Новини'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog:news_detail', kwargs={'slug': self.slug})
