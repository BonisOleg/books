from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from products.models import Product, Category
from blog.models import Article, News


class AbsoluteSitemap(Sitemap):
    """Sitemap з фіксованим SITE_DOMAIN (не залежить від Host запиту)."""

    protocol = None

    def get_urls(self, page=1, site=None, protocol=None):
        from types import SimpleNamespace

        from core.public_urls import canonical_host

        host = canonical_host()
        site = SimpleNamespace(domain=host, name=host)
        protocol = (
            protocol
            or self.protocol
            or getattr(settings, 'SITE_PROTOCOL', None)
            or 'https'
        )
        return super().get_urls(page=page, site=site, protocol=protocol)


class StaticSitemap(AbsoluteSitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['core:home']

    def location(self, item):
        return reverse(item)


class ProductSitemap(AbsoluteSitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return Product.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(AbsoluteSitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Category.objects.filter(is_active=True)


class ArticleSitemap(AbsoluteSitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Article.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:article_detail', kwargs={'slug': obj.slug})


class NewsSitemap(AbsoluteSitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        return News.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:news_detail', kwargs={'slug': obj.slug})
