import json
import re

from django import template
from django.db.models import Q
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def uah(value):
    try:
        val = float(value)
        formatted = f"{val:,.0f}".replace(",", " ")
        return f"{formatted} ₴"
    except (ValueError, TypeError):
        return value


@register.filter
def phone_raw(value):
    return ''.join(c for c in str(value) if c.isdigit() or c == '+')


@register.simple_tag
def json_ld(data):
    serialized = json.dumps(data, ensure_ascii=False).replace('</script>', '<\\/script>')
    return mark_safe(
        f'<script type="application/ld+json">{serialized}</script>'
    )


@register.filter
def discount_amount(product):
    if product.old_price and product.old_price > product.price:
        return product.old_price - product.price
    return 0


@register.filter
def calc_discount_percent(product):
    if product.old_price and product.old_price > 0:
        return int(((product.old_price - product.price) / product.old_price) * 100)
    return 0


@register.filter
def clean_richtext(value):
    """
    Strip inline margin/padding from TinyMCE HTML so frontend CSS controls layout.
    Preserves other inline styles (color, font-weight, text-decoration, etc.).
    """
    if not value:
        return value

    _STRIP_PROPS = re.compile(
        r'(?:^|(?<=;))\s*(?:margin|padding)(?:-\w+)?\s*:[^;]*;?',
        re.IGNORECASE,
    )

    def _clean_style_attr(match):
        cleaned = _STRIP_PROPS.sub('', match.group(1)).strip().strip(';')
        return f'style="{cleaned}"' if cleaned else ''

    result = re.sub(r'\bstyle="([^"]*)"', _clean_style_attr, value)
    return mark_safe(result)


@register.simple_tag
def analytics_payload(site_settings):
    if not site_settings:
        return {}
    return {
        'gtm': site_settings.google_tag_manager_id or '',
        'ga': site_settings.google_analytics_id or '',
        'ads': site_settings.google_ads_conversion_id or '',
        'pixel': site_settings.facebook_pixel_id or '',
        'consultant': site_settings.online_consultant_code or '',
    }


def _first_banner_size(banner):
    from core.imaging.variants import field_local_path, read_meta

    path = field_local_path(getattr(banner, 'image', None))
    if path is None or not path.is_file():
        return None
    meta = read_meta(path)
    if meta and meta.get('width') and meta.get('height'):
        return int(meta['width']), int(meta['height'])
    try:
        from PIL import Image
        with Image.open(path) as image:
            return image.size
    except Exception:
        return None


@register.inclusion_tag('includes/banners.html')
def banners(position, limit=None):
    from core.models import Banner

    now = timezone.now()
    qs = Banner.objects.filter(position=position, is_active=True).filter(
        Q(start_date__isnull=True) | Q(start_date__lte=now)
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=now)
    )
    if limit:
        qs = qs[:limit]
    items = list(qs)
    banner_ratio = None
    if items:
        size = _first_banner_size(items[0])
        if size and size[0] and size[1]:
            banner_ratio = {'w': size[0], 'h': size[1]}
    return {'banners': items, 'position': position, 'banner_ratio': banner_ratio}


@register.inclusion_tag('includes/faq.html')
def faq(scope='global', limit=None):
    from core.models import FAQ

    qs = FAQ.objects.filter(
        is_published=True, scope__in=[scope, 'global']
    ).order_by('order', 'id')
    if limit:
        qs = qs[:limit]
    return {'items': qs, 'scope': scope}
