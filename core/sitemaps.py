from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from products.models import Product, Category
from blog.models import Article, News


class StaticSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['core:home']

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return Product.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Category.objects.filter(is_active=True)


class ArticleSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Article.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:article_detail', kwargs={'slug': obj.slug})


class NewsSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        return News.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog:news_detail', kwargs={'slug': obj.slug})
