import csv
import io
from xml.etree.ElementTree import Element, SubElement, tostring
from django.http import HttpResponse
from django.conf import settings
from openpyxl import Workbook
from products.models import Product


FIELDS = [
    'id', 'sku', 'name', 'category', 'price', 'old_price',
    'stock_status', 'badge', 'discount_percent',
    'manufacturer', 'country', 'weight', 'condition',
    'description', 'short_description',
    'meta_title', 'meta_description', 'is_active',
]


def _get_rows():
    products = Product.objects.select_related('category').all()
    rows = []
    for p in products:
        rows.append([
            p.id, p.sku, p.name,
            p.category.name if p.category else '',
            str(p.price), str(p.old_price or ''),
            p.stock_status, p.badge, p.discount_percent,
            p.manufacturer, p.country,
            str(p.weight or ''), p.condition,
            p.description, p.short_description,
            p.meta_title, p.meta_description, p.is_active,
        ])
    return rows


def export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="products.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(FIELDS)
    for row in _get_rows():
        writer.writerow(row)
    return response


def export_excel(request):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Товари'
    ws.append(FIELDS)
    for row in _get_rows():
        ws.append(row)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="products.xlsx"'
    wb.save(response)
    return response


def export_xml(request):
    root = Element('products')
    products = Product.objects.select_related('category').prefetch_related('images').all()
    base_url = f"{getattr(settings, 'SITE_PROTOCOL', 'http')}://{getattr(settings, 'SITE_DOMAIN', 'localhost')}"

    for p in products:
        item = SubElement(root, 'product')
        SubElement(item, 'id').text = str(p.id)
        SubElement(item, 'sku').text = p.sku
        SubElement(item, 'name').text = p.name
        SubElement(item, 'category').text = p.category.name if p.category else ''
        SubElement(item, 'price').text = str(p.price)
        SubElement(item, 'old_price').text = str(p.old_price or '')
        SubElement(item, 'stock_status').text = p.stock_status
        SubElement(item, 'url').text = f"{base_url}{p.get_absolute_url()}"

        main_img = p.main_image
        if main_img:
            SubElement(item, 'image').text = f"{base_url}{main_img.image.url}"

        SubElement(item, 'manufacturer').text = p.manufacturer
        SubElement(item, 'description').text = p.description[:2000]

    xml_str = tostring(root, encoding='unicode', xml_declaration=False)
    response = HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str,
        content_type='application/xml; charset=utf-8'
    )
    response['Content-Disposition'] = 'attachment; filename="products.xml"'
    return response
