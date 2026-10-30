"""Middleware атрибуції Google Ads (cookie ofion_ads)."""

from __future__ import annotations

from orders.ads_attribution import (
    merge_ads,
    params_from_query,
    read_ads_cookie,
    set_ads_cookie,
)


class AdsAttributionMiddleware:
    """Зберігає gclid/gbraid/wbraid/utm_* у first-party cookie на 90 днів.

    Оновлює cookie лише коли в URL є нові параметри атрибуції.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = params_from_query(request)
        response = self.get_response(request)
        if incoming:
            merged = merge_ads(read_ads_cookie(request), incoming)
            set_ads_cookie(response, merged)
        return response
