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
    return [
        {
            'ref': item['ref'],
            'name': item['name'],
            'settlement_ref': item.get('settlement_ref', ''),
        }
        for item in search_city_records(query)
    ]


def search_city_records(query):
    """DeliveryCity (ref), Settlement Ref і підпис міста."""
    if len((query or '').strip()) < 2:
        return []

    search_query = resolve_city_query(query)
    records = _fetch_settlement_records(search_query)
    if not records and search_query != query.strip():
        records = _fetch_settlement_records(query.strip())
    return records


def _fetch_settlement_records(city_name):
    results = _call('Address', 'searchSettlements', {
        'CityName': city_name,
        'Limit': '20',
        'Page': '1',
    })
    records = []
    for item in results:
        for addr in item.get('Addresses', []):
            records.append({
                'ref': addr.get('DeliveryCity', ''),
                'settlement_ref': addr.get('Ref', ''),
                'name': addr.get('Present', ''),
            })
    return records


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


def search_streets(settlement_ref, query=''):
    needle = (query or '').strip()
    if not settlement_ref or len(needle) < 2:
        return []

    results = _call('Address', 'searchSettlementStreets', {
        'StreetName': needle,
        'SettlementRef': settlement_ref,
        'Limit': '50',
    })
    streets = []
    for item in results:
        if not isinstance(item, dict):
            continue
        nested = item.get('Addresses')
        rows = nested if isinstance(nested, list) else [item]
        for row in rows:
            if not isinstance(row, dict):
                continue
            ref = row.get('SettlementStreetRef') or row.get('Ref') or ''
            name = (
                row.get('Present')
                or row.get('SettlementStreetDescription')
                or row.get('Description')
                or ''
            )
            if ref or name:
                streets.append({'ref': ref, 'name': name})
    return streets
