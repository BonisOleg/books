from django import template
from django.utils.safestring import mark_safe
import json

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
