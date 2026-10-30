"""Відправка замовлень у KeyCRM. Помилки API не піднімаються до checkout."""

from __future__ import annotations

import logging
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = 'https://openapi.keycrm.app/v1'
TIMEOUT = 8

PAYMENT_STATUS_MAP = {
    'pending': 'not_paid',
    'paid': 'paid',
    'failed': 'canceled',
    'refunded': 'refund',
}

PAYMENT_METHOD_NEEDLES = {
    'liqpay': ('liqpay',),
    'monobank': ('monobank', 'монобанк', 'моно'),
    'cod': ('накладен', 'післяплат', 'cod'),
    'manager': ('менеджер', 'manager'),
}

DELIVERY_NEEDLES = ('нова пошта', 'nova poshta', 'novaposhta')

_runtime_cache: dict = {}


def _clear_runtime_cache():
    _runtime_cache.clear()


def sync_order(order) -> None:
    """Створює замовлення в KeyCRM або оновлює статус оплати. Ніколи не кидає виняток."""
    try:
        _sync_order(order)
    except Exception:
        logger.exception(
            'KeyCRM: не вдалося синхронізувати замовлення %s',
            getattr(order, 'id', None),
        )


def _sync_order(order):
    if not _api_key():
        return

    order.refresh_from_db()
    if not order.keycrm_order_id:
        existing = _find_existing(order)
        if existing:
            _store_ids(order, existing)
        else:
            source_id = _resolve_source_id()
            if not source_id:
                return
            created = _request('POST', '/order', json=_build_payload(order, source_id))
            _store_ids(order, _unwrap_order(created))
            if order.keycrm_order_id and not order.keycrm_payment_id:
                remote = _request(
                    'GET',
                    f'/order/{order.keycrm_order_id}',
                    params={'include': 'payments'},
                )
                _store_ids(order, _unwrap_order(remote))
            return

    if order.keycrm_order_id:
        _update_payment(order)


def _api_key():
    return (getattr(settings, 'KEYCRM_API_KEY', '') or '').strip()


def _headers():
    return {
        'Authorization': f'Bearer {_api_key()}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }


def _request(method, path, **kwargs):
    response = requests.request(
        method,
        f'{API_BASE}{path}',
        headers=_headers(),
        timeout=TIMEOUT,
        **kwargs,
    )
    response.raise_for_status()
    if not response.content:
        return {}
    return response.json()


def _extract_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('data', 'items'):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _unwrap_order(data):
    if isinstance(data, dict) and isinstance(data.get('data'), dict):
        return data['data']
    if isinstance(data, dict):
        return data
    return {}


def _as_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _first_payment_id(crm_order):
    payments = crm_order.get('payments')
    if isinstance(payments, dict):
        payments = payments.get('data') or payments.get('items') or []
    if not isinstance(payments, list) or not payments:
        return None
    first = payments[0]
    if isinstance(first, dict):
        return _as_int(first.get('id'))
    return None


def _store_ids(order, crm_order):
    fields = []
    order_id = _as_int(crm_order.get('id'))
    payment_id = _first_payment_id(crm_order)
    if order_id and order.keycrm_order_id != order_id:
        order.keycrm_order_id = order_id
        fields.append('keycrm_order_id')
    if payment_id and order.keycrm_payment_id != payment_id:
        order.keycrm_payment_id = payment_id
        fields.append('keycrm_payment_id')
    if fields:
        order.save(update_fields=fields)


def _find_existing(order):
    source_uuid = order.order_number
    try:
        data = _request(
            'GET',
            '/order',
            params={
                'filter[source_uuid]': source_uuid,
                'include': 'payments',
                'limit': 5,
            },
        )
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (400, 422):
            logger.warning('KeyCRM: фільтр source_uuid недоступний (%s)', status)
            return None
        raise

    for item in _extract_list(data):
        if str(item.get('source_uuid') or '') == source_uuid:
            return item
    return None


def _resolve_source_id():
    explicit = str(getattr(settings, 'KEYCRM_SOURCE_ID', '') or '').strip()
    if explicit:
        source_id = _as_int(explicit)
        if source_id is None:
            logger.error('KEYCRM_SOURCE_ID має бути додатним числом')
        return source_id

    if _runtime_cache.get('source_resolved'):
        return _runtime_cache.get('source_id')

    data = _request('GET', '/order/source', params={'limit': 50})
    items = _extract_list(data)
    _runtime_cache['source_resolved'] = True
    if len(items) == 1:
        source_id = _as_int(items[0].get('id'))
        _runtime_cache['source_id'] = source_id
        if source_id:
            return source_id

    logger.error('KeyCRM: вкажіть KEYCRM_SOURCE_ID (джерел: %s)', len(items))
    _runtime_cache['source_id'] = None
    return None


def _cached_list(path, cache_key):
    if cache_key in _runtime_cache:
        return _runtime_cache[cache_key]
    try:
        data = _request('GET', path, params={'limit': 50})
    except requests.RequestException:
        logger.warning('KeyCRM: не вдалося прочитати %s', path)
        return []
    items = _extract_list(data)
    _runtime_cache[cache_key] = items
    return items


def _match_id(items, needles):
    folded = tuple(needle.casefold() for needle in needles)
    for item in items:
        if not isinstance(item, dict):
            continue
        blob = ' '.join(
            str(item.get(key) or '') for key in ('name', 'alias', 'title')
        ).casefold()
        if any(needle in blob for needle in folded):
            return _as_int(item.get('id'))
    return None


def _payment_method_id(code):
    needles = PAYMENT_METHOD_NEEDLES.get(code)
    if not needles:
        return None
    return _match_id(_cached_list('/order/payment-method', 'payment_methods'), needles)


def _delivery_service_id():
    return _match_id(
        _cached_list('/order/delivery-service', 'delivery_services'),
        DELIVERY_NEEDLES,
    )


def _money(value):
    return float(Decimal(value).quantize(Decimal('0.01')))


def _buyer_name(order):
    parts = [order.first_name, order.patronymic, order.last_name]
    name = ' '.join(part.strip() for part in parts if part and part.strip())
    return name or 'Покупець'


def _build_payload(order, source_id):
    from orders.ads_attribution import click_custom_fields, marketing_from_order

    buyer = {'full_name': _buyer_name(order)}
    if order.email:
        buyer['email'] = order.email
    if order.phone:
        buyer['phone'] = order.phone

    products = [
        {
            'sku': item.product_sku or '',
            'name': item.product_name,
            'price': _money(item.price),
            'quantity': item.quantity,
        }
        for item in order.items.all()
    ]

    shipping = {}
    if order.city:
        shipping['shipping_address_city'] = order.city
    if order.warehouse:
        shipping['shipping_receive_point'] = order.warehouse
    if order.warehouse_ref:
        shipping['warehouse_ref'] = order.warehouse_ref
        delivery_id = _delivery_service_id()
        if delivery_id:
            shipping['delivery_service_id'] = delivery_id

    payment = {
        'amount': _money(order.total),
        'status': PAYMENT_STATUS_MAP.get(order.payment_status, 'not_paid'),
        'payment_method': order.get_payment_method_display(),
    }
    method_id = _payment_method_id(order.payment_method)
    if method_id:
        payment['payment_method_id'] = method_id

    payload = {
        'source_id': source_id,
        'source_uuid': order.order_number,
        'buyer': buyer,
        'products': products,
        'payments': [payment],
    }
    if order.comment:
        payload['buyer_comment'] = order.comment
    if shipping:
        payload['shipping'] = shipping
    marketing = marketing_from_order(order)
    if marketing:
        payload['marketing'] = marketing
    custom_fields = click_custom_fields(order)
    if custom_fields:
        payload['custom_fields'] = custom_fields
    return payload


def _update_payment(order):
    status = PAYMENT_STATUS_MAP.get(order.payment_status, 'not_paid')
    if not order.keycrm_payment_id:
        remote = _request(
            'GET',
            f'/order/{order.keycrm_order_id}',
            params={'include': 'payments'},
        )
        _store_ids(order, _unwrap_order(remote))
    if not order.keycrm_payment_id:
        logger.warning('KeyCRM: немає id оплати для замовлення %s', order.id)
        return
    _request(
        'PUT',
        f'/order/{order.keycrm_order_id}/payment/{order.keycrm_payment_id}',
        json={'status': status},
    )
