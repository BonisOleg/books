from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView

from core.views import tinymce_upload_image
from core.sitemaps import (
    ArticleSitemap,
    CategorySitemap,
    NewsSitemap,
    ProductSitemap,
    StaticSitemap,
)
from orders.views import liqpay_callback, mono_callback

sitemaps = {
    'static': StaticSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'articles': ArticleSitemap,
    'news': NewsSitemap,
}

urlpatterns = [
    path('healthz', lambda request: HttpResponse('ok', content_type='text/plain'), name='healthz'),
    path('admin/import-export/', include('import_export_app.urls')),
    path('admin/tinymce-upload/', tinymce_upload_image, name='tinymce_upload_image'),
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt', content_type='text/plain'
    ), name='robots'),
    # Payment callbacks — outside i18n_patterns so external servers always
    # hit a language-neutral URL regardless of the user's language session.
    path('orders/callback/liqpay/', liqpay_callback, name='liqpay_webhook'),
    path('orders/callback/mono/', mono_callback, name='mono_webhook'),
]

urlpatterns += i18n_patterns(
    path('', include('core.urls')),
    path('catalog/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
    path('accounts/', include('accounts.urls')),
    path('blog/', include('blog.urls')),
    path('promotions/', include('promotions.urls')),
    path('shipping/', include('shipping.urls')),
    path('reviews/', include('reviews.urls')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
