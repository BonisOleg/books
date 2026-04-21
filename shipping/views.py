from django.http import JsonResponse
from django.core.cache import cache
from .novaposhta_api import search_cities, search_warehouses


def _rate_limit(request, key_prefix, limit=30, period=60):
    ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    cache_key = f"ratelimit:{key_prefix}:{ip}"
    count = cache.get(cache_key, 0)
    if count >= limit:
        return True
    cache.set(cache_key, count + 1, period)
    return False


def api_cities(request):
    if _rate_limit(request, 'np_cities'):
        return JsonResponse({'error': 'Too many requests'}, status=429)
    q = request.GET.get('q', '').strip()
    cities = search_cities(q)
    return JsonResponse({'results': cities})


def api_warehouses(request):
    if _rate_limit(request, 'np_warehouses'):
        return JsonResponse({'error': 'Too many requests'}, status=429)
    city_ref = request.GET.get('city_ref', '')
    q = request.GET.get('q', '').strip()
    warehouses = search_warehouses(city_ref, q)
    return JsonResponse({'results': warehouses})
