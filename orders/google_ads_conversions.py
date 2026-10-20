"""Вивантаження виконаних замовлень KeyCRM у Google Ads (offline conversions)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.conf import settings
from django.utils import timezone as dj_timezone

from orders.google_ads_conversions1 import (
    build_conversion,
    format_conversion_datetime,
    normalize_and_hash_email,
    normalize_and_hash_phone,
    order_id_of,
    order_time,
    sha256_hash,
)
from orders.models import OfflineConversionLog

logger = logging.getLogger(__name__)

KEYCRM_API = 'https://openapi.keycrm.app/v1'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
LOOKBACK = timedelta(hours=48)
PAGE_LIMIT = 50
MAX_PAGES = 20
UPLOAD_CHUNK = 200
TIMEOUT = 20

__all__ = [
    'build_conversion',
    'format_conversion_datetime',
    'normalize_and_hash_email',
    'normalize_and_hash_phone',
    'sha256_hash',
    'upload_completed_orders',
]


def upload_completed_orders() -> dict:
    missing = _missing_settings()
    if missing:
        message = 'Офлайн-конверсії вимкнено, не задано: ' + ', '.join(missing)
        logger.warning(message)
        return {
            'not_configured': True,
            'message': message,
            'fetched': 0,
            'uploaded': 0,
            'skipped': 0,
            'failed': 0,
        }

    orders = fetch_completed_orders()
    customer_id = _digits(settings.GOOGLE_ADS_CUSTOMER_ID)
    action_id = _digits(settings.GOOGLE_ADS_CONVERSION_ACTION_ID)
    now = datetime.now(dt_timezone.utc)
    pending = []
    skipped = 0
    order_ids = []
    for order in orders:
        order_id = order_id_of(order)
        if order_id is None:
            skipped += 1
            continue
        order_ids.append(order_id)

    already = set(
        OfflineConversionLog.objects.filter(
            keycrm_order_id__in=order_ids,
            status=OfflineConversionLog.STATUS_UPLOADED,
        ).values_list('keycrm_order_id', flat=True)
    )

    for order in orders:
        order_id = order_id_of(order)
        if order_id is None:
            continue
        if order_id in already:
            skipped += 1
            continue
        conversion = build_conversion(
            order,
            customer_id=customer_id,
            action_id=action_id,
            now=now,
        )
        if conversion is None:
            skipped += 1
            logger.info('KeyCRM %s: немає телефону й email для хешу', order_id)
            continue
        pending.append((order_id, conversion))

    uploaded = 0
    failed = 0
    if pending:
        uploaded, failed = _upload_pending(pending)

    summary = {
        'not_configured': False,
        'message': '',
        'fetched': len(orders),
        'uploaded': uploaded,
        'skipped': skipped,
        'failed': failed,
    }
    logger.info(
        'Офлайн-конверсії: отримано %s, вивантажено %s, пропущено %s, помилки %s',
        summary['fetched'], uploaded, skipped, failed,
    )
    return summary


def fetch_completed_orders() -> list:
    start, end = _window()
    between = (
        f"{start.strftime('%Y-%m-%d %H:%M:%S')},"
        f"{end.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    modes = ('dated', 'sorted', 'plain')
    for index, mode in enumerate(modes):
        try:
            return _collect_pages(mode, between, start)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in (400, 422) or index == len(modes) - 1:
                raise
            logger.warning(
                'KeyCRM: режим %s відхилено (%s), спроба простішого фільтра',
                mode, status,
            )
    return []


def _upload_pending(pending) -> tuple[int, int]:
    token = _google_access_token()
    uploaded = 0
    failed = 0
    for offset in range(0, len(pending), UPLOAD_CHUNK):
        chunk = pending[offset:offset + UPLOAD_CHUNK]
        body = {
            'conversions': [item[1] for item in chunk],
            'partialFailure': True,
        }
        response = requests.post(
            _upload_url(),
            headers=_google_headers(token),
            json=body,
            timeout=TIMEOUT,
        )
        if response.status_code >= 400:
            message = _safe_error(response)
            logger.error('Google Ads HTTP %s: %s', response.status_code, message)
            _mark_many(
                [item[0] for item in chunk],
                OfflineConversionLog.STATUS_FAILED,
                message,
            )
            raise requests.HTTPError(message, response=response)

        payload = _json_body(response)
        ok_indexes, bad = _classify_upload(payload, len(chunk))
        ok_ids = [chunk[index][0] for index in ok_indexes]
        _mark_many(ok_ids, OfflineConversionLog.STATUS_UPLOADED, '')
        uploaded += len(ok_ids)
        for index, message in bad.items():
            _mark_many(
                [chunk[index][0]],
                OfflineConversionLog.STATUS_FAILED,
                message,
            )
            failed += 1
    return uploaded, failed


def _collect_pages(mode, between, start) -> list:
    found = []
    status_id = getattr(settings, 'KEYCRM_COMPLETED_STATUS_ID', 12)
    for page in range(1, MAX_PAGES + 1):
        params = {
            'include': 'buyer',
            'filter[status_id]': status_id,
            'limit': PAGE_LIMIT,
            'page': page,
        }
        if mode == 'dated':
            params['filter[updated_between]'] = between
        if mode in ('dated', 'sorted'):
            params['sort'] = '-updated_at'
        data = _keycrm_get(params)
        batch = _extract_list(data)
        if mode == 'dated':
            found.extend(batch)
        else:
            older = False
            for item in batch:
                moment = order_time(item)
                if moment is None or moment >= start:
                    found.append(item)
                else:
                    older = True
            if older and mode == 'sorted':
                break
        if not batch:
            break
        last_page = _page_last(data)
        if (last_page and page >= last_page) or len(batch) < PAGE_LIMIT:
            break
    return found


def _keycrm_get(params) -> dict:
    response = requests.get(
        f'{KEYCRM_API}/order',
        headers={
            'Authorization': f'Bearer {_setting("KEYCRM_API_KEY")}',
            'Accept': 'application/json',
        },
        params=params,
        timeout=TIMEOUT,
    )
    if response.status_code >= 400:
        logger.error('KeyCRM HTTP %s: %s', response.status_code, response.text[:300])
        response.raise_for_status()
    return _json_body(response)


def _google_access_token() -> str:
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'client_id': _setting('GOOGLE_ADS_CLIENT_ID'),
            'client_secret': _setting('GOOGLE_ADS_CLIENT_SECRET'),
            'refresh_token': _setting('GOOGLE_ADS_REFRESH_TOKEN'),
            'grant_type': 'refresh_token',
        },
        timeout=TIMEOUT,
    )
    if response.status_code >= 400:
        logger.error('Google OAuth HTTP %s', response.status_code)
        response.raise_for_status()
    token = _json_body(response).get('access_token')
    if not token:
        raise requests.HTTPError('Google OAuth не повернув access_token')
    return token


def _google_headers(token) -> dict:
    headers = {
        'Authorization': f'Bearer {token}',
        'developer-token': _setting('GOOGLE_ADS_DEVELOPER_TOKEN'),
        'Content-Type': 'application/json',
    }
    login_id = _digits(getattr(settings, 'GOOGLE_ADS_LOGIN_CUSTOMER_ID', ''))
    if login_id:
        headers['login-customer-id'] = login_id
    return headers


def _upload_url() -> str:
    version = (_setting('GOOGLE_ADS_API_VERSION') or 'v23').strip()
    customer_id = _digits(settings.GOOGLE_ADS_CUSTOMER_ID)
    return (
        f'https://googleads.googleapis.com/{version}'
        f'/customers/{customer_id}:uploadClickConversions'
    )


def _classify_upload(payload, count) -> tuple[set, dict]:
    results = payload.get('results') or []
    error = payload.get('partialFailureError') or {}
    indexed = {}
    for detail in error.get('details') or []:
        if not isinstance(detail, dict):
            continue
        for item in detail.get('errors') or []:
            if not isinstance(item, dict):
                continue
            index = _error_index(item.get('location'))
            if index is None:
                continue
            code = str(item.get('errorCode') or '')
            message = item.get('message') or code
            indexed.setdefault(index, []).append((code, message))

    uploaded = set()
    failed = {}
    for index in range(count):
        problems = indexed.get(index) or []
        if problems and any(_is_duplicate(code, message) for code, message in problems):
            uploaded.add(index)
            continue
        if problems:
            failed[index] = str(problems[0][1])[:500]
            continue
        result = results[index] if index < len(results) else {}
        if result or not error:
            uploaded.add(index)
            continue
        failed[index] = str(error.get('message') or 'partial failure')[:500]
    return uploaded, failed


def _is_duplicate(code, message) -> bool:
    blob = f'{code} {message}'.upper()
    return 'ORDER_ID' in blob and ('ALREADY' in blob or 'DUPLICATE' in blob)


def _error_index(location):
    elements = (location or {}).get('fieldPathElements') or []
    for element in elements:
        if not isinstance(element, dict):
            continue
        if element.get('fieldName') == 'conversions' and 'index' in element:
            try:
                return int(element['index'])
            except (TypeError, ValueError):
                return None
    return None


def _mark_many(order_ids, status, error):
    now = dj_timezone.now() if status == OfflineConversionLog.STATUS_UPLOADED else None
    for order_id in order_ids:
        OfflineConversionLog.objects.update_or_create(
            keycrm_order_id=order_id,
            defaults={
                'status': status,
                'uploaded_at': now,
                'error': '' if status == OfflineConversionLog.STATUS_UPLOADED else (error or '')[:2000],
            },
        )


def _window():
    end = datetime.now(dt_timezone.utc)
    return end - LOOKBACK, end


def _extract_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('data', 'items'):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _page_last(data):
    last_page = _as_int(data.get('last_page') if isinstance(data, dict) else None)
    if last_page is None and isinstance(data, dict) and isinstance(data.get('meta'), dict):
        last_page = _as_int(data['meta'].get('last_page'))
    return last_page


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _digits(value) -> str:
    return re.sub(r'\D', '', str(value or ''))


def _setting(name) -> str:
    return str(getattr(settings, name, '') or '').strip()


def _missing_settings() -> list[str]:
    required = [
        'KEYCRM_API_KEY',
        'GOOGLE_ADS_CLIENT_ID',
        'GOOGLE_ADS_CLIENT_SECRET',
        'GOOGLE_ADS_REFRESH_TOKEN',
        'GOOGLE_ADS_DEVELOPER_TOKEN',
        'GOOGLE_ADS_CUSTOMER_ID',
        'GOOGLE_ADS_CONVERSION_ACTION_ID',
    ]
    missing = []
    for name in required:
        raw = _setting(name)
        if name in ('GOOGLE_ADS_CUSTOMER_ID', 'GOOGLE_ADS_CONVERSION_ACTION_ID'):
            raw = _digits(raw)
        if not raw:
            missing.append(name)
    return missing


def _json_body(response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_error(response) -> str:
    payload = _json_body(response)
    message = payload.get('error_description') or payload.get('message')
    error = payload.get('error')
    if isinstance(error, dict):
        message = error.get('message') or message
    elif isinstance(error, str) and not message:
        message = error
    text = str(message or response.text or '')
    return text[:500]
