from django.conf import settings


def get_product_schema(product, request):
    images = [
        request.build_absolute_uri(img.image.url)
        for img in product.images.all()
    ]

    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product.description[:500],
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
