import re

from shipping.models import ShipmentOrigin
from shipping.novaposhta_api import search_cities, search_streets, search_warehouses

_KIND_PREFIX = re.compile(r'^(м|смт|с)\.\s*', re.IGNORECASE)


def pick_city(cities, city_name):
    needle = (city_name or '').strip().casefold()
    if not needle:
        return None
    exact = []
    partial = []
    for city in cities or []:
        present = (city.get('name') or '').strip()
        short = present.split(',')[0]
        short = _KIND_PREFIX.sub('', short).strip()
        if short.casefold() == needle:
            exact.append(city)
        elif needle in present.casefold():
            partial.append(city)
    if exact:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return None


def pick_warehouse(warehouses, number):
    wanted = str(number).lstrip('0') or '0'
    for item in warehouses or []:
        current = str(item.get('number') or '').lstrip('0') or '0'
        if current == wanted:
            return item
    pattern = re.compile(rf'№\s*0*{re.escape(str(number))}\b')
    for item in warehouses or []:
        if pattern.search(item.get('description') or ''):
            return item
    return None


def pick_street(streets, street_name):
    needle = (street_name or '').strip().casefold()
    if not needle:
        return None
    for street in streets or []:
        name = (street.get('name') or '').casefold()
        name = name.replace('вул.', '').replace('вулиця', '').strip()
        if name == needle or needle in name:
            return street
    return None


def warehouse_number(*labels):
    for label in labels:
        match = re.search(r'№\s*(\d+)', label or '')
        if match:
            return match.group(1)
    return ''


def find_streets(query, settlement_ref='', city_name=''):
    settlement_ref = (settlement_ref or '').strip()
    if not settlement_ref and (city_name or '').strip():
        city = pick_city(search_cities(city_name.strip()), city_name.strip())
        settlement_ref = (city or {}).get('settlement_ref') or ''
    if not settlement_ref:
        return []
    return search_streets(settlement_ref, query)


def fill_missing_refs():
    lines = []
    city_cache = {}
    origins = ShipmentOrigin.objects.all().order_by('id')
    for origin in origins:
        if not _needs_fill(origin):
            lines.append(f'{origin.name}: Ref уже заповнені')
            continue
        city_name = _city_name(origin)
        if not city_name:
            lines.append(f'{origin.name}: не вказано місто')
            continue
        if city_name not in city_cache:
            city_cache[city_name] = pick_city(search_cities(city_name), city_name)
        city = city_cache[city_name]
        changed = False
        if city and not (origin.city_ref or '').strip() and city.get('ref'):
            origin.city_ref = city['ref']
            changed = True
        if origin.kind == ShipmentOrigin.KIND_ADDRESS:
            changed = _fill_street(origin, city) or changed
        else:
            changed = _fill_warehouse(origin) or changed
        if changed:
            origin.save()
        lines.append(_result_line(origin))
    return lines


def _needs_fill(origin):
    if not (origin.city_ref or '').strip():
        return True
    if origin.kind == ShipmentOrigin.KIND_ADDRESS:
        return not (origin.street_ref or '').strip()
    return not (origin.warehouse_ref or '').strip()


def _city_name(origin):
    if (origin.city_name or '').strip():
        return origin.city_name.strip()
    raw = (origin.name or '').split('№')[0].split(',')[0].strip()
    return raw


def _fill_warehouse(origin):
    if (origin.warehouse_ref or '').strip() or not (origin.city_ref or '').strip():
        return False
    number = warehouse_number(origin.name, origin.warehouse_name)
    if not number:
        return False
    match = pick_warehouse(search_warehouses(origin.city_ref, number), number)
    if not match or not match.get('ref'):
        return False
    origin.warehouse_ref = match['ref']
    return True


def _fill_street(origin, city):
    if (origin.street_ref or '').strip():
        return False
    street_name = (origin.street_name or '').strip()
    settlement_ref = (city or {}).get('settlement_ref') or ''
    if not street_name or not settlement_ref:
        return False
    match = pick_street(search_streets(settlement_ref, street_name), street_name)
    if not match or not match.get('ref'):
        return False
    origin.street_ref = match['ref']
    return True


def _result_line(origin):
    if origin.kind == ShipmentOrigin.KIND_ADDRESS:
        if origin.city_ref and origin.street_ref:
            return f'{origin.name}: місто і вулицю заповнено'
        return f'{origin.name}: Ref не знайдено'
    if origin.city_ref and origin.warehouse_ref:
        return f'{origin.name}: місто і відділення заповнено'
    return f'{origin.name}: Ref не знайдено'
