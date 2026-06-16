from django.http import HttpResponse

from .feed_utils import build_google_merchant_xml


def google_merchant_feed(request):
    xml = build_google_merchant_xml()
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')
