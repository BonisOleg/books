"""Відкладена публікація статей і новин та посилання з обкладинки."""
import importlib
import re
import tempfile
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import migrations
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from blog.models import Article, News

_backfill = importlib.import_module('blog.migrations.0007_backfill_published_at')
backfill_published_at = _backfill.backfill_published_at
BackfillMigration = _backfill.Migration


def _png(name='cover.png'):
    buffer = BytesIO()
    Image.new('RGB', (40, 24), (20, 40, 80)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def _make(model, **kwargs):
    defaults = {
        'title': 'Запис',
        'slug': 'zapys',
        'content': '<p>Текст</p>',
        'is_published': True,
        'published_at': timezone.now() - timedelta(days=1),
    }
    defaults.update(kwargs)
    return model.objects.create(**defaults)


def _image_anchor(html, href):
    pattern = re.compile(
        r'<a href="' + re.escape(href) + r'" class="[^"]*" tabindex="-1" aria-hidden="true"[^>]*>'
        r'.*?</a>',
        re.S,
    )
    match = pattern.search(html)
    return match.group(0) if match else ''


def _content_card(html, href):
    pattern = re.compile(
        r'<a href="' + re.escape(href) + r'" class="content-card"[^>]*>.*?</a>',
        re.S,
    )
    match = pattern.search(html)
    return match.group(0) if match else ''


class PublishingVisibilityTests(TestCase):
    def setUp(self):
        self.past_article = _make(
            Article, title='Видима стаття', slug='vydyma-stattia',
        )
        self.future_article = _make(
            Article,
            title='Запланована стаття',
            slug='zaplanovana-stattia',
            published_at=timezone.now() + timedelta(days=3),
        )
        self.draft_article = _make(
            Article,
            title='Чернетка статті',
            slug='chernetka-statti',
            is_published=False,
        )
        self.past_news = _make(News, title='Видима новина', slug='vydyma-novyna')
        self.future_news = _make(
            News,
            title='Запланована новина',
            slug='zaplanovana-novyna',
            published_at=timezone.now() + timedelta(days=3),
        )
        self.draft_news = _make(
            News,
            title='Чернетка новини',
            slug='chernetka-novyny',
            is_published=False,
        )

    def test_future_and_draft_hidden_from_public_surfaces(self):
        article_list = self.client.get(reverse('blog:articles'))
        self.assertContains(article_list, 'Видима стаття')
        self.assertNotContains(article_list, 'Запланована стаття')
        self.assertNotContains(article_list, 'Чернетка статті')

        news_list = self.client.get(reverse('blog:news_list'))
        self.assertContains(news_list, 'Видима новина')
        self.assertNotContains(news_list, 'Запланована новина')
        self.assertNotContains(news_list, 'Чернетка новини')

        self.assertEqual(self.client.get(self.past_article.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.future_article.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(self.draft_article.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(self.past_news.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.future_news.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(self.draft_news.get_absolute_url()).status_code, 404)

        sitemap = self.client.get('/sitemap.xml').content.decode()
        self.assertIn(self.past_article.get_absolute_url(), sitemap)
        self.assertIn(self.past_news.get_absolute_url(), sitemap)
        self.assertNotIn(self.future_article.get_absolute_url(), sitemap)
        self.assertNotIn(self.future_news.get_absolute_url(), sitemap)
        self.assertNotIn(self.draft_article.get_absolute_url(), sitemap)
        self.assertNotIn(self.draft_news.get_absolute_url(), sitemap)

        home = self.client.get(reverse('core:home'))
        self.assertContains(home, 'Видима стаття')
        self.assertContains(home, 'Видима новина')
        self.assertNotContains(home, 'Запланована стаття')
        self.assertNotContains(home, 'Запланована новина')
        self.assertNotContains(home, 'Чернетка статті')
        self.assertNotContains(home, 'Чернетка новини')

    def test_visible_when_clock_passes_published_at(self):
        moment = timezone.now() + timedelta(days=10)
        article = _make(
            Article,
            title='Стаття на межі',
            slug='stattia-na-mezhi',
            published_at=moment,
        )
        news = _make(
            News,
            title='Новина на межі',
            slug='novyna-na-mezhi',
            published_at=moment,
        )
        before = moment - timedelta(minutes=1)
        after = moment + timedelta(minutes=1)

        with patch('blog.models.timezone.now', return_value=before):
            self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 404)
            self.assertEqual(self.client.get(news.get_absolute_url()).status_code, 404)
            self.assertNotContains(self.client.get(reverse('blog:articles')), 'Стаття на межі')
            self.assertNotContains(self.client.get(reverse('blog:news_list')), 'Новина на межі')
            self.assertNotContains(self.client.get(reverse('core:home')), 'Стаття на межі')
            self.assertNotContains(self.client.get(reverse('core:home')), 'Новина на межі')
            sitemap = self.client.get('/sitemap.xml').content.decode()
            self.assertNotIn(article.get_absolute_url(), sitemap)
            self.assertNotIn(news.get_absolute_url(), sitemap)

        with patch('blog.models.timezone.now', return_value=after):
            self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 200)
            self.assertEqual(self.client.get(news.get_absolute_url()).status_code, 200)
            self.assertContains(self.client.get(reverse('blog:articles')), 'Стаття на межі')
            self.assertContains(self.client.get(reverse('blog:news_list')), 'Новина на межі')
            self.assertContains(self.client.get(reverse('core:home')), 'Стаття на межі')
            self.assertContains(self.client.get(reverse('core:home')), 'Новина на межі')
            sitemap = self.client.get('/sitemap.xml').content.decode()
            self.assertIn(article.get_absolute_url(), sitemap)
            self.assertIn(news.get_absolute_url(), sitemap)

    def test_public_lists_order_by_published_at(self):
        now = timezone.now()
        _make(
            Article,
            title='Новіша дата статті',
            slug='novisha-stattia',
            published_at=now - timedelta(hours=2),
        )
        _make(
            Article,
            title='Старіша дата статті',
            slug='starisha-stattia',
            published_at=now - timedelta(days=4),
        )
        _make(
            News,
            title='Новіша дата новини',
            slug='novisha-novyna',
            published_at=now - timedelta(hours=2),
        )
        _make(
            News,
            title='Старіша дата новини',
            slug='starisha-novyna',
            published_at=now - timedelta(days=4),
        )

        articles = self.client.get(reverse('blog:articles')).content.decode()
        self.assertLess(articles.index('Новіша дата статті'), articles.index('Старіша дата статті'))
        news = self.client.get(reverse('blog:news_list')).content.decode()
        self.assertLess(news.index('Новіша дата новини'), news.index('Старіша дата новини'))
        home = self.client.get(reverse('core:home')).content.decode()
        self.assertLess(home.index('Новіша дата статті'), home.index('Старіша дата статті'))
        self.assertLess(home.index('Новіша дата новини'), home.index('Старіша дата новини'))

    def test_backfill_copies_created_at_for_every_row(self):
        article = self.past_article
        news = self.past_news
        shifted = timezone.now() + timedelta(days=12)
        Article.objects.filter(pk=article.pk).update(published_at=shifted)
        News.objects.filter(pk=news.pk).update(published_at=shifted)

        backfill_published_at(apps, None)

        article.refresh_from_db()
        news.refresh_from_db()
        self.assertEqual(article.published_at, article.created_at)
        self.assertEqual(news.published_at, news.created_at)
        operation = BackfillMigration.operations[0]
        self.assertIs(operation.reverse_code, migrations.RunPython.noop)


class AdminPublishStatusTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username='publisher',
            email='publisher@example.com',
            password='publisher-pass',
        )
        self.assertTrue(self.client.login(username='publisher', password='publisher-pass'))
        _make(
            Article,
            title='Майбутня в адмінці',
            slug='maibutnia-admin',
            published_at=timezone.now() + timedelta(days=2),
        )
        _make(
            News,
            title='Майбутня новина в адмінці',
            slug='maibutnia-novyna-admin',
            published_at=timezone.now() + timedelta(days=2),
        )

    def test_changelist_shows_scheduled_status(self):
        article_list = self.client.get(reverse('admin:blog_article_changelist'))
        self.assertEqual(article_list.status_code, 200)
        self.assertContains(article_list, 'Статус')
        self.assertContains(article_list, 'Дата публікації')
        self.assertContains(article_list, 'Заплановано')
        self.assertContains(article_list, 'Майбутня в адмінці')

        news_list = self.client.get(reverse('admin:blog_news_changelist'))
        self.assertEqual(news_list.status_code, 200)
        self.assertContains(news_list, 'Заплановано')
        self.assertContains(news_list, 'Майбутня новина в адмінці')


class CoverLinkTests(TestCase):
    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self._override = override_settings(
            MEDIA_ROOT=self._media.name,
            STORAGES={
                'default': {
                    'BACKEND': 'django.core.files.storage.FileSystemStorage',
                    'OPTIONS': {'location': self._media.name},
                },
                'staticfiles': {
                    'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
                },
            },
        )
        self._override.enable()
        self.article = _make(
            Article,
            title='Стаття з фото',
            slug='stattia-z-foto',
            image=_png('article-cover.png'),
        )
        self.news = _make(
            News,
            title='Новина з фото',
            slug='novyna-z-foto',
            image=_png('news-cover.png'),
        )

    def tearDown(self):
        self._override.disable()
        self._media.cleanup()

    def test_list_and_home_cover_links_to_detail(self):
        article_url = self.article.get_absolute_url()
        news_url = self.news.get_absolute_url()

        articles = self.client.get(reverse('blog:articles')).content.decode()
        article_block = _image_anchor(articles, article_url)
        self.assertIn('<img', article_block)
        self.assertIn('alt="Стаття з фото"', article_block)
        self.assertIn(f'<a href="{article_url}">Стаття з фото</a>', articles)
        self.assertEqual(articles.count('tabindex="-1"'), 1)
        self.assertNotIn('target="_blank"', article_block)

        news = self.client.get(reverse('blog:news_list')).content.decode()
        news_block = _image_anchor(news, news_url)
        self.assertIn('<img', news_block)
        self.assertIn('alt="Новина з фото"', news_block)
        self.assertIn(f'<a href="{news_url}">Новина з фото</a>', news)
        self.assertEqual(news.count('tabindex="-1"'), 1)
        self.assertNotIn('target="_blank"', news_block)

        home = self.client.get(reverse('core:home')).content.decode()
        home_article = _content_card(home, article_url)
        home_news = _content_card(home, news_url)
        self.assertIn('<img', home_article)
        self.assertIn('alt="Ілюстрація: Стаття з фото"', home_article)
        self.assertIn('<img', home_news)
        self.assertIn('alt="Ілюстрація: Новина з фото"', home_news)
        self.assertNotIn('target="_blank"', home_article)
        self.assertNotIn('target="_blank"', home_news)

    def test_absolute_cover_link_opens_new_tab(self):
        external = 'https://example.com/promo'
        self.article.cover_link = external
        self.article.save()
        self.news.cover_link = external
        self.news.save()

        articles = self.client.get(reverse('blog:articles')).content.decode()
        article_block = _image_anchor(articles, external)
        self.assertIn('target="_blank"', article_block)
        self.assertIn('rel="noopener noreferrer"', article_block)
        self.assertIn(
            f'<a href="{self.article.get_absolute_url()}">Стаття з фото</a>',
            articles,
        )

        news = self.client.get(reverse('blog:news_list')).content.decode()
        news_block = _image_anchor(news, external)
        self.assertIn('target="_blank"', news_block)
        self.assertIn('rel="noopener noreferrer"', news_block)

        home = self.client.get(reverse('core:home')).content.decode()
        self.assertIn('target="_blank"', _content_card(home, external))
        self.assertIn('rel="noopener noreferrer"', _content_card(home, external))

    def test_relative_cover_link_same_tab(self):
        relative = '/catalog/'
        self.article.cover_link = relative
        self.article.save()
        self.news.cover_link = relative
        self.news.save()

        articles = self.client.get(reverse('blog:articles')).content.decode()
        article_block = _image_anchor(articles, relative)
        self.assertTrue(article_block)
        self.assertNotIn('target="_blank"', article_block)

        news = self.client.get(reverse('blog:news_list')).content.decode()
        news_block = _image_anchor(news, relative)
        self.assertTrue(news_block)
        self.assertNotIn('target="_blank"', news_block)

        home = self.client.get(reverse('core:home')).content.decode()
        home_cards = re.findall(
            r'<a href="' + re.escape(relative) + r'" class="content-card"[^>]*>',
            home,
        )
        self.assertEqual(len(home_cards), 2)
        self.assertTrue(all('target="_blank"' not in tag for tag in home_cards))
