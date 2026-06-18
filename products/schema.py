import html as html_module
import re

from django.conf import settings
from django.utils.html import strip_tags

_DATA_ATTRS_RE = re.compile(
    r'\s+data-(start|end|section-id)="[^"]*"',
    flags=re.IGNORECASE,
)

_SHIPPING_DETAILS = {
    "@type": "OfferShippingDetails",
    "shippingRate": {
        "@type": "MonetaryAmount",
        "value": 0,
        "currency": "UAH",
    },
    "shippingDestination": {
        "@type": "DefinedRegion",
        "addressCountry": "UA",
    },
    "deliveryTime": {
        "@type": "ShippingDeliveryTime",
        "handlingTime": {
            "@type": "QuantitativeValue",
            "minValue": 0,
            "maxValue": 1,
            "unitCode": "DAY",
        },
        "transitTime": {
            "@type": "QuantitativeValue",
            "minValue": 1,
            "maxValue": 3,
            "unitCode": "DAY",
        },
    },
}


def _plain_text(html_content: str, max_len: int = 500) -> str:
    """Return plain text from an HTML string, safe for structured data and meta tags.

    Handles both normal HTML and double-encoded HTML (e.g. content pasted via
    TinyMCE source view or copied from AI tools that emit &lt;h1&gt; entities).
    Also strips AI-injected data-start / data-end / data-section-id attributes.
    """
    if not html_content:
        return ""
    # first pass: &lt; → <, &amp; → &
    cleaned = html_module.unescape(html_content)
    # second pass for double-encoding (&amp;lt; → &lt; → <)
    if "&lt;" in cleaned:
        cleaned = html_module.unescape(cleaned)
    cleaned = _DATA_ATTRS_RE.sub("", cleaned)
    # strip HTML tags, then resolve any remaining named entities (e.g. &mdash;)
    plain = html_module.unescape(strip_tags(cleaned))
    return plain[:max_len]


def _return_policy_schema(return_policy_text: str) -> dict:
    return {
        "@type": "MerchantReturnPolicy",
        "applicableCountry": "UA",
        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
        "merchantReturnDays": 14,
        "returnMethod": "https://schema.org/ReturnByMail",
        "returnFees": "https://schema.org/FreeReturn",
        **({"description": return_policy_text[:500]} if return_policy_text else {}),
    }


def get_product_schema(product, request):
    images = [
        request.build_absolute_uri(img.image.url)
        for img in product.images.all()
    ]

    description = _plain_text(product.description) or _plain_text(product.short_description)

    try:
        from core.models import SiteSettings
        site = SiteSettings.objects.only('site_name', 'return_policy').first()
        seller_name = site.site_name if site else getattr(settings, 'SITE_NAME', 'OFION')
        return_policy_text = site.return_policy if site else ""
    except Exception:
        seller_name = getattr(settings, 'SITE_NAME', 'OFION')
        return_policy_text = ""

    offer = {
        "@type": "Offer",
        "url": request.build_absolute_uri(product.get_absolute_url()),
        "priceCurrency": "UAH",
        "price": float(product.price),
        "availability": product.availability_schema,
        "itemCondition": "https://schema.org/NewCondition",
        "seller": {
            "@type": "Organization",
            "name": seller_name,
        },
        "shippingDetails": _SHIPPING_DETAILS,
        "hasMerchantReturnPolicy": _return_policy_schema(return_policy_text),
    }

    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "sku": product.sku,
        "mpn": product.sku,
        "image": images,
        "offers": offer,
    }

    if description:
        schema["description"] = description

    if product.manufacturer:
        schema["brand"] = {
            "@type": "Brand",
            "name": product.manufacturer,
        }

    primary_cat = product.categories.first()
    if primary_cat:
        schema["category"] = primary_cat.name

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
