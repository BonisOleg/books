from django.http import HttpResponse
from django.views.decorators.http import require_GET

from .feed_segments import get_cached_segment_feed_xml
from .feed_utils import build_google_merchant_xml


@require_GET
def google_merchant_feed(request):
    xml = build_google_merchant_xml()
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


@require_GET
def feed_vip(request):
    xml = get_cached_segment_feed_xml('VIP')
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


@require_GET
def feed_middle(request):
    xml = get_cached_segment_feed_xml('Middle')
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')
