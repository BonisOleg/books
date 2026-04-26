from django.conf import settings

from .models import Page, SiteSettings


def site_settings(request):
    try:
        site = SiteSettings.objects.first()
    except Exception:
        site = None

    from django.db.models import Prefetch
    from products.models import Category
    try:
        nav_categories = list(
            Category.objects.filter(
                parent__isnull=True, is_active=True
            ).prefetch_related(
                Prefetch(
                    'children',
                    queryset=Category.objects.filter(is_active=True).order_by('order'),
                )
            ).order_by('order')[:12]
        )
    except Exception:
        nav_categories = []

    try:
        footer_pages = Page.objects.filter(
            is_published=True, show_in_footer=True
        ).order_by('footer_order', 'title')
    except Exception:
        footer_pages = []

    available_languages = [('uk', 'Українська')]
    if site:
        if site.enable_ru:
            available_languages.append(('ru', 'Русский'))
        if site.enable_en:
            available_languages.append(('en', 'English'))

    return {
        'site_settings': site,
        'nav_categories': nav_categories,
        'footer_pages': footer_pages,
        'available_languages': available_languages,
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'Магазин книжок'),
        'PHONE_NUMBERS': getattr(settings, 'PHONE_NUMBERS', []),
        'TELEGRAM_BOT_USERNAME': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
        'VIBER_BOT_URI': getattr(settings, 'VIBER_BOT_URI', ''),
    }
