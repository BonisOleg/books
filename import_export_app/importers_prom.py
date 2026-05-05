"""Імпорт товарів у форматі експорту Prom.ua / Бірка.

Очікувані заголовки (з підкресленням, як у Prom):
Код_товару, Назва_позиції, Назва_позиції_укр, Опис, Опис_укр, Ціна,
Виробник, Країна_виробник, Вага,кг, Назва_групи, Наявність,
Посилання_зображення, HTML_заголовок(_укр), HTML_опис(_укр),
+ повторювані трійки: Назва_Характеристики / Одиниця_виміру_Характеристики /
                       Значення_Характеристики
"""
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import requests
from django.core.files.base import ContentFile
from django.utils.text import slugify

from products.models import Category, Product, ProductAttribute, ProductImage

logger = logging.getLogger(__name__)


PROM_DETECT_HEADERS = {'код_товару'}

PROM_BASE_MAPPING = {
    'код_товару': 'sku',
    'ціна': 'price',
    'знижка': 'discount_percent',
    'виробник': 'manufacturer',
    'країна_виробник': 'country',
    'вага,кг': 'weight',
    'назва_групи': 'category',
    'наявність': 'stock_status',
    'посилання_зображення': '_image_urls',
}

PROM_LANG_MAPPING = {
    'uk': {
        'назва_позиції_укр': 'name',
        'опис_укр': 'description',
        'html_заголовок_укр': 'meta_title',
        'html_опис_укр': 'meta_description',
    },
    'ru': {
        'назва_позиції': 'name',
        'опис': 'description',
        'html_заголовок': 'meta_title',
        'html_опис': 'meta_description',
    },
}

PROM_LANG_FALLBACK = {
    'uk': {
        'назва_позиції': 'name',
        'опис': 'description',
        'html_заголовок': 'meta_title',
        'html_опис': 'meta_description',
    },
    'ru': {
        'назва_позиції_укр': 'name',
        'опис_укр': 'description',
        'html_заголовок_укр': 'meta_title',
        'html_опис_укр': 'meta_description',
    },
}

# stock_status — згідно Product.STOCK_CHOICES: in_stock | ready | order | out
PROM_STOCK_MAPPING = {
    '+': 'in_stock',
    '-': 'out',
    'true': 'in_stock',
    'false': 'out',
    'in stock': 'in_stock',
    'out of stock': 'out',
}

ATTR_HEADER = 'назва_характеристики'
ATTR_UNIT_HEADER = 'одиниця_виміру_характеристики'
ATTR_VALUE_HEADER = 'значення_характеристики'

MAX_IMAGES_PER_PRODUCT = 10
MAX_ATTRIBUTES_PER_PRODUCT = 50
IMAGE_DOWNLOAD_TIMEOUT = 8
IMAGE_MAX_BYTES = 5 * 1024 * 1024


def is_prom_format(headers_lower):
    return any(h in PROM_DETECT_HEADERS for h in headers_lower)


def _coerce_decimal(value, default=None):
    if value in (None, ''):
        return default
    try:
        s = str(value).replace(',', '.').strip()
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return default


def _coerce_int(value, default=0):
    if value in (None, ''):
        return default
    try:
        return int(Decimal(str(value).replace(',', '.').strip()))
    except (InvalidOperation, ValueError):
        return default


def _coerce_stock(value):
    if value in (None, ''):
        return 'in_stock'
    s = str(value).strip().lower()
    return PROM_STOCK_MAPPING.get(s, 'in_stock')


def _str_or_empty(v):
    return '' if v is None else str(v).strip()


def parse_prom_attributes(headers_lower, row_values):
    """Збирає характеристики з повторюваних трійок Назва/Одиниця/Значення."""
    attrs = []
    n = len(row_values)
    for i, h in enumerate(headers_lower):
        if h != ATTR_HEADER:
            continue
        if i >= n:
            continue
        name = _str_or_empty(row_values[i])
        if not name:
            continue
        unit = ''
        value = ''
        if i + 1 < n and i + 1 < len(headers_lower) and headers_lower[i + 1] == ATTR_UNIT_HEADER:
            unit = _str_or_empty(row_values[i + 1])
        if i + 2 < n and i + 2 < len(headers_lower) and headers_lower[i + 2] == ATTR_VALUE_HEADER:
            value = _str_or_empty(row_values[i + 2])
        if unit and unit.lower() not in ('-', 'none'):
            value = f'{value} {unit}'.strip()
        if not value:
            continue
        attrs.append((name[:200], value[:400]))
    return attrs


def parse_image_urls(raw):
    if not raw:
        return []
    urls = []
    for u in str(raw).replace('\n', ',').split(','):
        u = u.strip()
        if u and (u.startswith('http://') or u.startswith('https://')):
            urls.append(u)
    return urls


def build_prom_row(headers_lower, row_values, language):
    """Будує канонічний dict канонічних полів з рядка Prom-формату."""
    primary = PROM_LANG_MAPPING.get(language, PROM_LANG_MAPPING['uk'])
    fallback = PROM_LANG_FALLBACK.get(language, PROM_LANG_FALLBACK['uk'])

    result = {}
    fb_values = {}
    n = len(row_values)
    for i, h in enumerate(headers_lower):
        if i >= n:
            break
        v_str = _str_or_empty(row_values[i])

        canonical = PROM_BASE_MAPPING.get(h)
        if canonical:
            if v_str or canonical not in result:
                result[canonical] = v_str
            continue

        if h in primary:
            field = primary[h]
            if v_str:
                result[field] = v_str
            continue

        if h in fallback:
            field = fallback[h]
            if v_str:
                fb_values[field] = v_str

    for field, val in fb_values.items():
        if not result.get(field):
            result[field] = val

    return result


def _ensure_unique_slug(name, sku):
    base = slugify(name, allow_unicode=True)[:400] or sku.lower()
    slug = base
    counter = 1
    while Product.objects.filter(slug=slug).exclude(sku=sku).exists():
        slug = f'{base[:395]}-{counter}'
        counter += 1
    return slug


def _download_image(url):
    """Завантажує зображення по URL. Повертає ContentFile або None."""
    try:
        url = url.strip()
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return None
        resp = requests.get(url, timeout=IMAGE_DOWNLOAD_TIMEOUT, stream=True)
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get('Content-Type', '').lower()
        if 'image' not in content_type:
            return None
        content = b''
        for chunk in resp.iter_content(chunk_size=8192):
            if not chunk:
                continue
            content += chunk
            if len(content) > IMAGE_MAX_BYTES:
                return None
        if not content:
            return None
        path = parsed.path or '/img.jpg'
        name = path.rsplit('/', 1)[-1] or 'img.jpg'
        if '.' not in name:
            name += '.jpg'
        return ContentFile(content, name=name[-100:])
    except requests.RequestException as exc:
        logger.warning('Не вдалось завантажити %s: %s', url, exc)
        return None
    except Exception as exc:
        logger.exception('Неочікувана помилка завантаження %s: %s', url, exc)
        return None


def _attach_categories(product, cat_name, sku):
    if not cat_name:
        return
    cat, _ = Category.objects.get_or_create(
        name=cat_name,
        defaults={'slug': slugify(cat_name, allow_unicode=True) or sku.lower()},
    )
    product.categories.set([cat])


def _replace_attributes(product, attributes):
    if not attributes:
        return
    product.attributes.all().delete()
    bulk = [
        ProductAttribute(product=product, name=name, value=value, order=order)
        for order, (name, value) in enumerate(attributes[:MAX_ATTRIBUTES_PER_PRODUCT])
    ]
    ProductAttribute.objects.bulk_create(bulk)


def _attach_images(product, image_urls):
    if not image_urls:
        return
    if product.images.count() > 0:
        return
    for order, url in enumerate(image_urls[:MAX_IMAGES_PER_PRODUCT]):
        cf = _download_image(url)
        if cf is None:
            continue
        try:
            ProductImage.objects.create(
                product=product,
                image=cf,
                alt_text=product.name[:200],
                order=order,
            )
        except Exception as exc:
            logger.warning('Не зберегли фото %s для %s: %s', url, product.sku, exc)


def process_prom_row(row_dict, attributes, image_urls, *, fetch_images=True):
    sku = row_dict.get('sku', '').strip()
    name = row_dict.get('name', '').strip()
    if not sku or not name:
        return None, 'Відсутній SKU або назва'

    sku = sku[:50]
    name = name[:400]

    price = _coerce_decimal(row_dict.get('price'), default=Decimal('0')) or Decimal('0')
    weight = _coerce_decimal(row_dict.get('weight'))
    discount = max(0, _coerce_int(row_dict.get('discount_percent'), default=0))
    stock = _coerce_stock(row_dict.get('stock_status'))
    slug = _ensure_unique_slug(name, sku)

    defaults = {
        'name': name,
        'slug': slug,
        'price': price,
        'stock_status': stock,
        'discount_percent': discount,
        'manufacturer': (row_dict.get('manufacturer') or '')[:200],
        'country': (row_dict.get('country') or '')[:100],
        'weight': weight,
        'description': row_dict.get('description', ''),
        'meta_title': (row_dict.get('meta_title') or '')[:200],
        'meta_description': row_dict.get('meta_description', ''),
        'is_active': True,
    }

    product, created = Product.objects.update_or_create(sku=sku, defaults=defaults)

    _attach_categories(product, (row_dict.get('category') or '').strip(), sku)
    _replace_attributes(product, attributes)
    if fetch_images:
        _attach_images(product, image_urls)

    return product, 'створено' if created else 'оновлено'
