import io
from decimal import Decimal
from pathlib import Path

from products.models import Product

from suppliers.models import Supplier

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'kupola_sample.xml'


def make_product(**kwargs):
    defaults = {
        'name': 'Товар',
        'slug': 'tovar',
        'sku': 'SKU-1',
        'description': '<p>Опис</p>',
        'price': Decimal('100.00'),
        'old_price': Decimal('150.00'),
        'stock_status': 'in_stock',
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


def make_supplier(**kwargs):
    defaults = {
        'name': 'Купола',
        'feed_url': 'https://example.com/kupola.xml',
        'feed_format': Supplier.FeedFormat.GOOGLE_MERCHANT_RSS,
        'is_active': True,
    }
    defaults.update(kwargs)
    return Supplier.objects.create(**defaults)


def feed_bytes(items):
    rows = []
    for item in items:
        rows.append(
            '<item>'
            f'<g:id>{item["id"]}</g:id>'
            f'<title>{item.get("title", "Товар")}</title>'
            f'<g:price>{item["price"]}</g:price>'
            f'<g:availability>{item.get("availability", "in_stock")}</g:availability>'
            '</item>'
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">'
        '<channel><title>Тест</title>'
        + ''.join(rows)
        + '</channel></rss>'
    )
    return io.BytesIO(xml.encode('utf-8'))
