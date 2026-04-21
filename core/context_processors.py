from django.conf import settings
from .models import SiteSettings


def site_settings(request):
    try:
        site = SiteSettings.objects.first()
    except Exception:
        site = None

    from products.models import Category
    try:
        nav_categories = Category.objects.filter(
            parent__isnull=True, is_active=True
        ).order_by('order')[:10]
    except Exception:
        nav_categories = []

    return {
        'site_settings': site,
        'nav_categories': nav_categories,
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'Магазин книжок'),
        'PHONE_NUMBERS': getattr(settings, 'PHONE_NUMBERS', []),
        'TELEGRAM_BOT_USERNAME': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
        'VIBER_BOT_URI': getattr(settings, 'VIBER_BOT_URI', ''),
    }
