from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from core.sitemaps import (
    StaticSitemap, ProductSitemap, CategorySitemap,
    ArticleSitemap, NewsSitemap,
)

sitemaps = {
    'static': StaticSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'articles': ArticleSitemap,
    'news': NewsSitemap,
}

urlpatterns = [
    path('healthz', lambda request: HttpResponse('ok', content_type='text/plain'), name='healthz'),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('catalog/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
    path('accounts/', include('accounts.urls')),
    path('blog/', include('blog.urls')),
    path('promotions/', include('promotions.urls')),
    path('shipping/', include('shipping.urls')),
    path('reviews/', include('reviews.urls')),
    path('import-export/', include('import_export_app.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt', content_type='text/plain'
    ), name='robots'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
