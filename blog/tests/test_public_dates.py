"""Публічні дати блогу й JSON-LD беруть published_at, не created_at."""
import json
import re
from datetime import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import Article, News

_LD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>',
    re.S,
)
_OFFSET_RE = re.compile(r'[+-]\d{2}:\d{2}$')


def _aware(year, month, day, hour=12):
    return timezone.make_aware(datetime(year, month, day, hour, 0))


def _make(model, **kwargs):
    defaults = {
        'title': 'Запис',
        'slug': 'zapys',
        'content': '<p>Текст</p>',
        'is_published': True,
        'published_at': _aware(2024, 3, 17, 16),
    }
    defaults.update(kwargs)
    return model.objects.create(**defaults)


def _json_ld(html):
    return [json.loads(raw) for raw in _LD_RE.findall(html)]


def _schema(html, schema_type):
    found = [item for item in _json_ld(html) if item.get('@type') == schema_type]
    if len(found) != 1:
        raise AssertionError(f'очікувався один {schema_type}, є {len(found)}')
    return found[0]


class PublicPublishedDateTests(TestCase):
    def setUp(self):
        self.created_at = _aware(2010, 1, 2, 8)
        self.published_at = _aware(2024, 3, 17, 16)
        self.older_published_at = _aware(2023, 6, 1, 12)

        self.article = _make(
            Article,
            title='Свіжа стаття',
            slug='svizha-stattia',
            published_at=self.published_at,
            meta_description='SEO опис статті',
            excerpt='Анонс статті',
        )
        Article.objects.filter(pk=self.article.pk).update(
            created_at=self.created_at,
            image='blog/articles/cover.webp',
        )
        self.article.refresh_from_db()
        _make(
            Article,
            title='Давніша стаття',
            slug='davnisha-stattia',
            published_at=self.older_published_at,
        )

        self.news = _make(
            News,
            title='Свіжа новина',
            slug='svizha-novyna',
            published_at=self.published_at,
            excerpt='Анонс новини',
        )
        News.objects.filter(pk=self.news.pk).update(created_at=self.created_at)
        self.news.refresh_from_db()
        _make(
            News,
            title='Давніша новина',
            slug='davnisha-novyna',
            published_at=self.older_published_at,
        )

        self.published_label = timezone.localtime(self.article.published_at).strftime('%d.%m.%Y')
        self.created_label = timezone.localtime(self.article.created_at).strftime('%d.%m.%Y')

    def test_published_queryset_uses_meta_ordering(self):
        expected = ['-published_at', '-created_at']
        self.assertEqual(Article._meta.ordering, expected)
        self.assertEqual(News._meta.ordering, expected)
        self.assertEqual(Article.objects.published().query.order_by, tuple(expected))
        self.assertEqual(News.objects.published().query.order_by, tuple(expected))

        visible = {'is_published': True, 'published_at__lte': timezone.now()}
        self.assertEqual(
            list(Article.objects.published().values_list('pk', flat=True)),
            list(Article.objects.filter(**visible).values_list('pk', flat=True)),
        )
        self.assertEqual(
            list(News.objects.published().values_list('pk', flat=True)),
            list(News.objects.filter(**visible).values_list('pk', flat=True)),
        )

    def test_cards_show_published_at_and_sort_first(self):
        articles = self.client.get(reverse('blog:articles')).content.decode()
        news = self.client.get(reverse('blog:news_list')).content.decode()
        home = self.client.get(reverse('core:home')).content.decode()

        for html, css_class in (
            (articles, 'blog-card__date'),
            (news, 'blog-card__date'),
            (home, 'content-card__date'),
        ):
            self.assertIn(
                f'<div class="{css_class}">{self.published_label}</div>',
                html,
            )
            self.assertNotIn(self.created_label, html)

        self.assertLess(articles.index('Свіжа стаття'), articles.index('Давніша стаття'))
        self.assertLess(news.index('Свіжа новина'), news.index('Давніша новина'))
        self.assertLess(home.index('Свіжа стаття'), home.index('Давніша стаття'))
        self.assertLess(home.index('Свіжа новина'), home.index('Давніша новина'))

        article_page = self.client.get(self.article.get_absolute_url()).content.decode()
        news_page = self.client.get(self.news.get_absolute_url()).content.decode()
        self.assertIn(
            f'<div class="blog-detail__date">{self.published_label}</div>',
            article_page,
        )
        self.assertIn(
            f'<div class="blog-detail__date">{self.published_label}</div>',
            news_page,
        )
        self.assertNotIn(self.created_label, article_page)
        self.assertNotIn(self.created_label, news_page)

    def test_detail_json_ld_uses_local_published_at(self):
        article_page = self.client.get(self.article.get_absolute_url()).content.decode()
        news_page = self.client.get(self.news.get_absolute_url()).content.decode()
        article_ld = _schema(article_page, 'BlogPosting')
        news_ld = _schema(news_page, 'NewsArticle')

        for obj, data in ((self.article, article_ld), (self.news, news_ld)):
            published = timezone.localtime(obj.published_at).isoformat()
            self.assertEqual(data['datePublished'], published)
            self.assertRegex(data['datePublished'], _OFFSET_RE)
            self.assertIn('dateModified', data)
            self.assertEqual(
                data['dateModified'],
                timezone.localtime(obj.updated_at).isoformat(),
            )
            self.assertEqual(
                data['url'],
                f'http://testserver{obj.get_absolute_url()}',
            )
            self.assertEqual(data['headline'], obj.title)

        self.assertEqual(article_ld['description'], 'SEO опис статті')
        self.assertEqual(news_ld['description'], 'Анонс новини')
        self.assertEqual(
            article_ld['image'],
            f'http://testserver{self.article.image.url}',
        )
        self.assertNotIn('image', news_ld)
