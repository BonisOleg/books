from django.conf import settings
from django.http import JsonResponse

from core.ratelimit import is_rate_limited

from .novaposhta_api import search_cities, search_warehouses


def _np_limited(request, action):
    ip_limit, ip_period = getattr(settings, 'ABUSE_NP_API_IP', (30, 60))
    return is_rate_limited(
        request,
        action,
        ip_limit=ip_limit,
        ip_period=ip_period,
    )


def api_cities(request):
    if _np_limited(request, 'np_cities'):
        return JsonResponse({'error': 'Too many requests'}, status=429)
    q = request.GET.get('q', '').strip()
    cities = search_cities(q)
    return JsonResponse({'results': cities})


def api_warehouses(request):
    if _np_limited(request, 'np_warehouses'):
        return JsonResponse({'error': 'Too many requests'}, status=429)
    city_ref = request.GET.get('city_ref', '')
    q = request.GET.get('q', '').strip()
    warehouses = search_warehouses(city_ref, q)
    return JsonResponse({'results': warehouses})
