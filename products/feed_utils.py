import re
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement

from django.conf import settings

from .models import Product
from .schema import _plain_text

DEFAULT_GOOGLE_CATEGORY = '784'  # Media > Books

AVAILABILITY_MAP = {
    'in_stock': 'in_stock',
    'ready': 'in_stock',
    'order': 'preorder',
    'out': 'out_of_stock',
}

_EXCLUSION_LABELS = {
    'no_image': 'Немає фото',
    'no_price': 'Ціна ≤ 0',
    'no_description': 'Немає опису',
    'inactive': 'Неактивний',
}

_GTIN_RE = re.compile(r'^(\d{13}|\d{9}[\dX])$', re.IGNORECASE)


def _resolved_site_domain() -> str:
    domain = getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
    if domain and domain not in ('localhost:8000', 'localhost', '127.0.0.1'):
        return domain
    custom = getattr(settings, 'CUSTOM_DOMAIN', '')
    if custom:
        return custom
    render_host = getattr(settings, 'RENDER_EXTERNAL_HOSTNAME', '')
    if render_host:
        return render_host
    return domain or 'localhost:8000'


def get_base_url() -> str:
    protocol = getattr(settings, 'SITE_PROTOCOL', 'https')
    domain = _resolved_site_domain()
    return f'{protocol}://{domain}'


def absolute_url(base_url: str, url: str) -> str:
    if url.startswith(('http://', 'https://')):
        return url
    if url.startswith('//'):
        return f'{getattr(settings, "SITE_PROTOCOL", "https")}:{url}'
    if not url.startswith('/'):
        url = f'/{url}'
    return f'{base_url}{url}'


def format_gmc_price(value) -> str:
    return f'{Decimal(str(value)).quantize(Decimal("0.01"))} UAH'


def normalize_gtin(value: str) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r'[\s\-]', '', value.strip())
    if _GTIN_RE.match(cleaned):
        return cleaned.upper()
    return None


def get_site_brand() -> str:
    try:
        from core.models import SiteSettings
        site = SiteSettings.objects.only('site_name').first()
        if site and site.site_name:
            return site.site_name
    except Exception:
        pass
    return getattr(settings, 'SITE_NAME', 'Магазин книжок')


def get_google_category(product) -> str:
    for cat in product.categories.all():
        current = cat
        while current:
            if current.google_product_category:
                return current.google_product_category
            current = current.parent
    return DEFAULT_GOOGLE_CATEGORY


def product_description(product) -> str:
    text = (
        _plain_text(product.short_description, max_len=5000)
        or _plain_text(product.description, max_len=5000)
    )
    return text or product.name[:5000]


def product_type_path(product) -> str:
    primary = product.categories.first()
    if not primary:
        return ''
    parts = [c.name for c in primary.get_ancestors()] + [primary.name]
    return ' > '.join(parts)


def feed_eligible_queryset():
    return (
        Product.objects.filter(is_active=True, price__gt=0, images__isnull=False)
        .distinct()
        .prefetch_related('categories', 'categories__parent', 'images')
        .order_by('-updated_at')
    )


def get_product_exclusion_reasons(product) -> list[str]:
    reasons = []
    if not product.is_active:
        reasons.append('inactive')
    if not product.images.exists():
        reasons.append('no_image')
    if product.price <= 0:
        reasons.append('no_price')
    if not product_description(product).strip():
        reasons.append('no_description')
    return reasons


def build_feed_item(channel: Element, product, base_url: str, site_brand: str) -> None:
    item = SubElement(channel, 'item')

    SubElement(item, 'g:id').text = product.sku
    SubElement(item, 'g:title').text = product.name[:150]
    SubElement(item, 'g:description').text = product_description(product)

    SubElement(item, 'g:link').text = absolute_url(base_url, product.get_absolute_url())

    images = list(product.images.all())
    SubElement(item, 'g:image_link').text = absolute_url(base_url, images[0].image.url)
    for img in images[1:10]:
        SubElement(item, 'g:additional_image_link').text = absolute_url(base_url, img.image.url)

    if product.old_price and product.old_price > product.price:
        SubElement(item, 'g:price').text = format_gmc_price(product.old_price)
        SubElement(item, 'g:sale_price').text = format_gmc_price(product.price)
    else:
        SubElement(item, 'g:price').text = format_gmc_price(product.price)

    SubElement(item, 'g:availability').text = AVAILABILITY_MAP.get(
        product.stock_status, 'in_stock'
    )
    SubElement(item, 'g:condition').text = 'new'

    gtin = normalize_gtin(product.sku_manufacturer)
    brand = product.manufacturer or site_brand

    if gtin:
        SubElement(item, 'g:gtin').text = gtin
    else:
        SubElement(item, 'g:identifier_exists').text = 'false'

    SubElement(item, 'g:brand').text = brand[:70]
    SubElement(item, 'g:mpn').text = product.sku

    SubElement(item, 'g:google_product_category').text = get_google_category(product)

    type_path = product_type_path(product)
    if type_path:
        SubElement(item, 'g:product_type').text = type_path[:750]

    shipping = SubElement(item, 'g:shipping')
    SubElement(shipping, 'g:country').text = 'UA'
    SubElement(shipping, 'g:service').text = 'Standard'
    SubElement(shipping, 'g:price').text = format_gmc_price(0)


def build_google_merchant_xml() -> str:
    base_url = get_base_url()
    site_brand = get_site_brand()

    root = Element('rss')
    root.set('xmlns:g', 'http://base.google.com/ns/1.0')
    root.set('version', '2.0')
    channel = SubElement(root, 'channel')

    SubElement(channel, 'title').text = site_brand
    SubElement(channel, 'link').text = base_url
    SubElement(channel, 'description').text = 'Каталог товарів'

    for product in feed_eligible_queryset():
        build_feed_item(channel, product, base_url, site_brand)

    from xml.etree.ElementTree import tostring
    xml_str = tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str


def get_domain_status() -> dict:
    domain = _resolved_site_domain()
    warnings = []
    if not domain or domain == 'localhost:8000':
        warnings.append('SITE_DOMAIN не налаштовано для продакшену.')
    elif 'localhost' in domain or '127.0.0.1' in domain:
        warnings.append('SITE_DOMAIN вказує на локальний хост.')
    elif domain.endswith('.onrender.com'):
        warnings.append('Використовується тимчасовий домен Render — для GMC краще кастомний домен.')
    return {
        'domain': domain,
        'protocol': getattr(settings, 'SITE_PROTOCOL', 'https'),
        'base_url': get_base_url(),
        'warnings': warnings,
        'is_production_ready': not warnings,
    }


def get_feed_dashboard_context() -> dict:
    base_url = get_base_url()
    active_qs = Product.objects.filter(is_active=True).prefetch_related('images')
    total_active = active_qs.count()
    eligible_qs = feed_eligible_queryset()
    in_feed_count = eligible_qs.count()

    excluded = []
    for product in active_qs.order_by('name')[:200]:
        reasons = get_product_exclusion_reasons(product)
        if reasons:
            excluded.append({
                'product': product,
                'reasons': reasons,
                'reason_labels': [_EXCLUSION_LABELS.get(r, r) for r in reasons],
            })

    preview = []
    for product in eligible_qs[:5]:
        preview.append({
            'product': product,
            'title': product.name[:150],
            'price': format_gmc_price(product.price),
            'image_url': absolute_url(base_url, product.images.first().image.url),
            'link': absolute_url(base_url, product.get_absolute_url()),
        })

    return {
        'domain_status': get_domain_status(),
        'feed_stats': {
            'total_active': total_active,
            'in_feed': in_feed_count,
            'excluded': total_active - in_feed_count,
        },
        'feed_preview': preview,
        'feed_excluded': excluded[:30],
        'excluded_truncated': len(excluded) > 30,
        'site_brand': get_site_brand(),
    }
