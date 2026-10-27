"""Вивантаження виконаних замовлень KeyCRM у Google Data Manager."""

from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings

from orders.google_ads_conversions1 import (
    build_conversion,
    build_event,
    format_conversion_datetime,
    normalize_and_hash_email,
    normalize_and_hash_phone,
    normalize_phone_e164,
    order_id_of,
    order_time,
    sha256_hash,
    _digits,
    _extract_list,
    _field_violations,
    _invalid_error,
    _lookback,
    _missing_settings,
    _page_last,
    _setting,
    _violations_by_event,
    _window,
)
from orders.google_ads_conversions2 import (
    failed_retry_ids,
    mark_conversion_logs,
    retry_eligible,
    select_pending,
)
from orders.models import OfflineConversionLog

logger = logging.getLogger(__name__)

KEYCRM_API = 'https://openapi.keycrm.app/v1'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
INGEST_URL = 'https://datamanager.googleapis.com/v1/events:ingest'
PAGE_LIMIT = 50
MAX_PAGES = 20
UPLOAD_CHUNK = 200
TIMEOUT = 20

__all__ = [
    'build_conversion',
    'build_event',
    'format_conversion_datetime',
    'normalize_and_hash_email',
    'normalize_and_hash_phone',
    'normalize_phone_e164',
    'sha256_hash',
    'upload_completed_orders',
]


def upload_completed_orders(validate_only=None, order_ids=None) -> dict:
    validate_only = _resolve_validate_only(validate_only)
    missing = _missing_settings()
    if missing:
        message = 'Вивантаження в Data Manager вимкнено, не задано: ' + ', '.join(missing)
        logger.warning(message)
        return _summary(
            not_configured=True,
            missing=missing,
            validate_only=validate_only,
            message=message,
        )

    now = datetime.now(dt_timezone.utc)
    retried = 0
    if order_ids is None:
        orders = fetch_completed_orders()
        pending, skipped = select_pending(orders, now)
        for order_id in failed_retry_ids(_present_ids(orders)):
            event = _event_for_retry(order_id, now)
            if event is None:
                continue
            pending.append((order_id, event))
            retried += 1
    else:
        orders, missing_count = _load_explicit_orders(order_ids)
        pending, skipped = select_pending(
            orders,
            now,
            ignore_attempt_cap=True,
            require_completed=True,
        )
        skipped += missing_count

    uploaded = failed = invalid = 0
    if pending:
        uploaded, failed, invalid = _upload_pending(
            pending, validate_only=validate_only,
        )
    summary = _summary(
        validate_only=validate_only,
        fetched=len(orders),
        uploaded=uploaded,
        skipped=skipped,
        failed=failed,
        invalid=invalid,
        retried=retried,
    )
    logger.info(
        'Data Manager: отримано %s, повторів %s, вивантажено %s, пропущено %s, '
        'помилки %s, невалідні %s, перевірка %s',
        summary['fetched'], retried, uploaded, skipped, failed, invalid, validate_only,
    )
    return summary


def _summary(**overrides) -> dict:
    summary = {
        'not_configured': False,
        'missing': [],
        'validate_only': False,
        'message': '',
        'fetched': 0,
        'uploaded': 0,
        'skipped': 0,
        'failed': 0,
        'invalid': 0,
        'retried': 0,
    }
    summary.update(overrides)
    return summary


def _present_ids(orders):
    ids = []
    for order in orders:
        order_id = order_id_of(order)
        if order_id is not None:
            ids.append(order_id)
    return ids


def _event_for_retry(order_id, now):
    order = _fetch_order(order_id, strict=False)
    if order is None:
        return None
    if not retry_eligible(order, now):
        logger.info(
            'Пропуск повтору keycrm_order_id=%s: не виконано або поза вікном кліку',
            order_id,
        )
        return None
    return build_event(order, now=now)


def _load_explicit_orders(order_ids):
    found = []
    missing = 0
    seen = set()
    for raw in order_ids:
        try:
            order_id = int(raw)
        except (TypeError, ValueError):
            missing += 1
            continue
        if order_id <= 0 or order_id in seen:
            continue
        seen.add(order_id)
        order = _fetch_order(order_id, strict=True)
        if order is None:
            missing += 1
        else:
            found.append(order)
    return found, missing


def _fetch_order(order_id, *, strict):
    try:
        response = requests.get(
            f'{KEYCRM_API}/order/{order_id}',
            headers=_keycrm_headers(),
            params={'include': 'buyer'},
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        if strict:
            raise
        logger.warning('KeyCRM: не вдалося прочитати замовлення %s', order_id)
        return None
    if response.status_code == 404:
        logger.info('KeyCRM: замовлення %s не знайдено', order_id)
        return None
    if response.status_code >= 400:
        logger.error('KeyCRM HTTP %s для замовлення %s', response.status_code, order_id)
        if strict:
            response.raise_for_status()
        return None
    payload = _json_body(response)
    if isinstance(payload.get('data'), dict):
        payload = payload['data']
    if order_id_of(payload) is None:
        return None
    return payload


def _keycrm_headers():
    return {
        'Authorization': f'Bearer {_setting("KEYCRM_API_KEY")}',
        'Accept': 'application/json',
    }


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


def _upload_pending(pending, *, validate_only: bool) -> tuple[int, int, int]:
    token = _google_access_token()
    uploaded = 0
    failed = 0
    invalid = 0
    for offset in range(0, len(pending), UPLOAD_CHUNK):
        up, fail, bad = _ingest_chunk(
            token,
            pending[offset:offset + UPLOAD_CHUNK],
            validate_only=validate_only,
            can_drop=True,
        )
        uploaded += up
        failed += fail
        invalid += bad
    return uploaded, failed, invalid


def _ingest_chunk(token, chunk, *, validate_only: bool, can_drop: bool):
    order_ids = [item[0] for item in chunk]
    response = requests.post(
        INGEST_URL,
        headers=_google_headers(token),
        json=_ingest_body([item[1] for item in chunk], validate_only),
        timeout=TIMEOUT,
    )
    if response.status_code < 400:
        payload = _json_body(response)
        logger.info(
            'Data Manager ingest requestId=%s fieldWarnings=%s',
            payload.get('requestId') or '',
            payload.get('fieldWarnings') or [],
        )
        _mark_uploaded(order_ids, validate_only=validate_only)
        return len(order_ids), 0, 0

    violations = _field_violations(response)
    for field, description in violations:
        logger.error(
            'Data Manager fieldViolation field=%s description=%s',
            field, description,
        )
    if can_drop and response.status_code == 400:
        grouped = _violations_by_event(violations, len(chunk))
        if grouped:
            return _drop_invalid_and_retry(
                token, chunk, grouped, validate_only=validate_only,
            )

    message = _safe_error(response)
    if _is_duplicate_error(response):
        logger.info(
            'Data Manager: дубль transactionId, чанк вважаємо вивантаженим: %s',
            message,
        )
        _mark_uploaded(order_ids, validate_only=validate_only)
        return len(order_ids), 0, 0
    logger.error('Data Manager HTTP %s: %s', response.status_code, message)
    if not validate_only:
        mark_conversion_logs(order_ids, OfflineConversionLog.STATUS_FAILED, message)
    raise requests.HTTPError(message, response=response)


def _drop_invalid_and_retry(token, chunk, grouped, *, validate_only: bool):
    keep = []
    for index, item in enumerate(chunk):
        if index not in grouped:
            keep.append(item)
            continue
        if not validate_only:
            mark_conversion_logs(
                [item[0]],
                OfflineConversionLog.STATUS_FAILED,
                _invalid_error(grouped[index]),
            )
    dropped = len(chunk) - len(keep)
    if not keep:
        return 0, 0, dropped
    uploaded, failed, _again = _ingest_chunk(
        token, keep, validate_only=validate_only, can_drop=False,
    )
    return uploaded, failed, dropped


def _mark_uploaded(order_ids, *, validate_only: bool) -> None:
    if validate_only:
        return
    mark_conversion_logs(order_ids, OfflineConversionLog.STATUS_UPLOADED, '')


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
        headers=_keycrm_headers(),
        params=params,
        timeout=TIMEOUT,
    )
    if response.status_code >= 400:
        logger.error('KeyCRM HTTP %s: %s', response.status_code, response.text[:300])
        response.raise_for_status()
    return _json_body(response)


def _google_access_token() -> str:
    creds = _oauth_credentials()
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'client_id': creds['client_id'],
            'client_secret': creds['client_secret'],
            'refresh_token': creds['refresh_token'],
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
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def _ingest_body(events, validate_only: bool) -> dict:
    body = {
        'destinations': [_destination()],
        'events': events,
        'encoding': 'HEX',
        'validateOnly': validate_only,
    }
    if _flag('GOOGLE_DATAMANAGER_CONSENT_GRANTED'):
        body['consent'] = {
            'adUserData': 'CONSENT_GRANTED',
            'adPersonalization': 'CONSENT_GRANTED',
        }
    return body


def _destination() -> dict:
    destination = {
        'reference': 'keycrm',
        'operatingAccount': {
            'accountType': 'GOOGLE_ADS',
            'accountId': _digits(_setting('GOOGLE_ADS_CUSTOMER_ID')),
        },
        'productDestinationId': _digits(_setting('GOOGLE_ADS_CONVERSION_ACTION_ID')),
    }
    login_id = _digits(_setting('GOOGLE_ADS_LOGIN_CUSTOMER_ID'))
    if login_id:
        destination['loginAccount'] = {
            'accountType': 'GOOGLE_ADS',
            'accountId': login_id,
        }
    return destination


def _oauth_credentials() -> dict:
    return {
        'client_id': _setting('GOOGLE_ADS_CLIENT_ID'),
        'client_secret': _setting('GOOGLE_ADS_CLIENT_SECRET'),
        'refresh_token': _setting('GOOGLE_DATAMANAGER_REFRESH_TOKEN'),
    }


def _resolve_validate_only(value) -> bool:
    if value is None:
        return _flag('GOOGLE_DATAMANAGER_VALIDATE_ONLY')
    return bool(value)


def _flag(name) -> bool:
    raw = getattr(settings, name, False)
    if isinstance(raw, bool):
        return raw
    text = str(raw or '').strip().lower()
    if not text:
        return False
    return text in ('1', 'true', 'yes', 'on')


def _is_duplicate_error(response) -> bool:
    text = ''
    try:
        text = response.text or ''
    except Exception:
        text = ''
    blob = f'{_safe_error(response)}\n{text[:4000]}'.upper()
    return 'DUPLICATE' in blob or 'ALREADY' in blob


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
    text = str(message or '').strip()
    if text:
        return text[:500]
    return f'HTTP {response.status_code}'
