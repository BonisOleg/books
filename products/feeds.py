from django.http import HttpResponse
from django.conf import settings
from xml.etree.ElementTree import Element, SubElement, tostring
from .models import Product


def google_merchant_feed(request):
    root = Element('rss')
    root.set('xmlns:g', 'http://base.google.com/ns/1.0')
    root.set('version', '2.0')
    channel = SubElement(root, 'channel')

    SubElement(channel, 'title').text = getattr(settings, 'SITE_NAME', 'Магазин книжок')
    SubElement(channel, 'link').text = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}"
    SubElement(channel, 'description').text = 'Каталог товарів'

    products = Product.objects.filter(is_active=True).select_related(
        'category'
    ).prefetch_related('images')

    base_url = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}"

    for product in products:
        item = SubElement(channel, 'item')

        SubElement(item, 'g:id').text = str(product.id)
        SubElement(item, 'g:title').text = product.name[:150]
        SubElement(item, 'g:description').text = (
            product.short_description or product.description
        )[:5000]
        SubElement(item, 'g:link').text = f"{base_url}{product.get_absolute_url()}"

        main_img = product.main_image
        if main_img:
            SubElement(item, 'g:image_link').text = f"{base_url}{main_img.image.url}"

        for img in list(product.images.all())[1:10]:
            SubElement(item, 'g:additional_image_link').text = f"{base_url}{img.image.url}"

        if product.old_price and product.old_price > product.price:
            SubElement(item, 'g:price').text = f"{product.old_price} UAH"
            SubElement(item, 'g:sale_price').text = f"{product.price} UAH"
        else:
            SubElement(item, 'g:price').text = f"{product.price} UAH"

        availability_map = {
            'in_stock': 'in_stock',
            'ready': 'in_stock',
            'order': 'preorder',
            'out': 'out_of_stock',
        }
        SubElement(item, 'g:availability').text = availability_map.get(
            product.stock_status, 'in_stock'
        )

        SubElement(item, 'g:condition').text = 'new'

        if product.manufacturer:
            SubElement(item, 'g:brand').text = product.manufacturer

        SubElement(item, 'g:mpn').text = product.sku

        if product.category:
            SubElement(item, 'g:product_type').text = product.category.name

    xml_str = tostring(root, encoding='unicode', xml_declaration=False)
    response = HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str,
        content_type='application/xml; charset=utf-8'
    )
    return response
