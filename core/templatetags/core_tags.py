import json

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
    return {'banners': qs, 'position': position}


@register.inclusion_tag('includes/faq.html')
def faq(scope='global', limit=None):
    from core.models import FAQ

    qs = FAQ.objects.filter(
        is_published=True, scope__in=[scope, 'global']
    ).order_by('order', 'id')
    if limit:
        qs = qs[:limit]
    return {'items': qs, 'scope': scope}
