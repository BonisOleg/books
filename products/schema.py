import html as html_module
import re

from django.conf import settings
from django.utils.html import strip_tags

_DATA_ATTRS_RE = re.compile(
    r'\s+data-(start|end|section-id)="[^"]*"',
    flags=re.IGNORECASE,
)


def _plain_text(html_content: str, max_len: int = 500) -> str:
    """Return plain text from an HTML string, safe for structured data."""
    if not html_content:
        return ""
    cleaned = html_module.unescape(html_content)
    if "&lt;" in cleaned:
        cleaned = html_module.unescape(cleaned)
    cleaned = _DATA_ATTRS_RE.sub("", cleaned)
    return strip_tags(cleaned)[:max_len]


def get_product_schema(product, request):
    images = [
        request.build_absolute_uri(img.image.url)
        for img in product.images.all()
    ]

    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": _plain_text(product.description),
        "sku": product.sku,
        "image": images,
        "offers": {
            "@type": "Offer",
            "url": request.build_absolute_uri(product.get_absolute_url()),
            "priceCurrency": "UAH",
            "price": str(product.price),
            "availability": product.availability_schema,
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {
                "@type": "Organization",
                "name": getattr(settings, 'SITE_NAME', 'Магазин книжок'),
            }
        }
    }

    if product.manufacturer:
        schema["brand"] = {
            "@type": "Brand",
            "name": product.manufacturer,
        }

    if product.category:
        schema["category"] = product.category.name

    reviews = product.reviews.filter(is_approved=True)
    if reviews.exists():
        from django.db.models import Avg
        avg = reviews.aggregate(avg=Avg('rating'))['avg']
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(round(avg, 1)),
            "reviewCount": str(reviews.count()),
            "bestRating": "5",
            "worstRating": "1",
        }

    return schema


def get_breadcrumb_schema(breadcrumbs, request):
    items = []
    for i, (name, url) in enumerate(breadcrumbs, start=1):
        entry = {
            "@type": "ListItem",
            "position": i,
            "name": name,
        }
        if url:
            entry["item"] = request.build_absolute_uri(url)
        items.append(entry)

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }
