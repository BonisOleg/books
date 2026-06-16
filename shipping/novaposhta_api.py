import requests
from django.conf import settings

from .city_aliases import resolve_city_query

NP_API_URL = 'https://api.novaposhta.ua/v2.0/json/'


def _call(model, method, properties=None):
    api_key = settings.NOVAPOSHTA_API_KEY
    if not api_key:
        return []

    payload = {
        'apiKey': api_key,
        'modelName': model,
        'calledMethod': method,
        'methodProperties': properties or {},
    }

    try:
        resp = requests.post(NP_API_URL, json=payload, timeout=10)
        data = resp.json()
        if data.get('success'):
            return data.get('data', [])
    except Exception:
        pass
    return []


def search_cities(query):
    if len(query) < 2:
        return []

    search_query = resolve_city_query(query)
    cities = _fetch_settlements(search_query)

    if not cities and search_query != query.strip():
        cities = _fetch_settlements(query.strip())

    return cities


def _fetch_settlements(city_name):
    results = _call('Address', 'searchSettlements', {
        'CityName': city_name,
        'Limit': '20',
        'Page': '1',
    })
    cities = []
    for item in results:
        for addr in item.get('Addresses', []):
            cities.append({
                'ref': addr.get('DeliveryCity', ''),
                'name': addr.get('Present', ''),
            })
    return cities


def search_warehouses(city_ref, query=''):
    props = {
        'CityRef': city_ref,
        'Limit': '50',
        'Page': '1',
    }
    if query:
        props['FindByString'] = query

    results = _call('Address', 'getWarehouses', props)
    warehouses = []
    for item in results:
        warehouses.append({
            'ref': item.get('Ref', ''),
            'number': item.get('Number', ''),
            'description': item.get('Description', ''),
            'short_address': item.get('ShortAddress', ''),
        })
    return warehouses
