from django.conf import settings
from django.utils.translation import get_language_from_path

from .models import Page, ProfileCabinetTexts, SiteSettings


def site_settings(request):
    try:
        site = SiteSettings.objects.first()
    except Exception:
        site = None

    from products.models import Category
    try:
        nav_categories = list(
            Category.objects.filter(
                parent__isnull=True, is_active=True
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

    try:
        header_pages = Page.objects.filter(
            is_published=True, show_in_header=True
        ).order_by('header_order', 'title')
    except Exception:
        header_pages = []

    available_languages = [('uk', 'Українська')]
    if site:
        if site.enable_ru:
            available_languages.append(('ru', 'Русский'))
        if site.enable_en:
            available_languages.append(('en', 'English'))

    lang_prefix = get_language_from_path(request.path)
    if lang_prefix:
        _stripped = request.path[len(lang_prefix) + 1:]
        path_without_lang = _stripped if _stripped.startswith('/') else '/' + _stripped
    else:
        path_without_lang = request.path

    site_name = getattr(settings, 'SITE_NAME', 'OFION')
    site_home_title = getattr(
        settings, 'SITE_HOME_TITLE',
        'OFION – статусні подарунки для керівників, партнерів і близьких',
    )
    if site:
        if site.site_name:
            site_name = site.site_name
        if site.seo_home_title:
            site_home_title = site.seo_home_title

    return {
        'site_settings': site,
        'nav_categories': nav_categories,
        'footer_pages': footer_pages,
        'header_pages': header_pages,
        'available_languages': available_languages,
        'path_without_lang': path_without_lang,
        'SITE_NAME': site_name,
        'SITE_HOME_TITLE': site_home_title,
        'PHONE_NUMBERS': getattr(settings, 'PHONE_NUMBERS', []),
        'TELEGRAM_BOT_USERNAME': getattr(settings, 'TELEGRAM_BOT_USERNAME', ''),
        'VIBER_BOT_URI': getattr(settings, 'VIBER_BOT_URI', ''),
        'profile_cabinet': ProfileCabinetTexts.get_merged_safe(),
    }
