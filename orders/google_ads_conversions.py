"""Вивантаження виконаних замовлень KeyCRM у Google Data Manager."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.conf import settings
from django.utils import timezone as dj_timezone

from orders.google_ads_conversions1 import (
    build_conversion,
    build_event,
    click_ids,
    format_conversion_datetime,
    has_contact,
    normalize_and_hash_email,
    normalize_and_hash_phone,
    normalize_phone_e164,
    order_amount,
    order_id_of,
    order_status_label,
    order_time,
    sha256_hash,
    utm_campaign_of,
    _field_violations,
    _invalid_error,
    _violations_by_event,
)
from orders.models import OfflineConversionLog

logger = logging.getLogger(__name__)

KEYCRM_API = 'https://openapi.keycrm.app/v1'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
INGEST_URL = 'https://datamanager.googleapis.com/v1/events:ingest'
_DEFAULT_LOOKBACK_DAYS = 10
_MIN_LOOKBACK_DAYS = 7
_MAX_LOOKBACK_DAYS = 14
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
    'clamp_lookback_days',
]


def upload_completed_orders(validate_only=None, *, days=None, send_summary=False) -> dict:
    validate_only = _resolve_validate_only(validate_only)
    missing = _missing_settings()
    if missing:
        message = 'Вивантаження в Data Manager вимкнено, не задано: ' + ', '.join(missing)
        logger.warning(message)
        summary = {
            'not_configured': True,
            'missing': missing,
            'validate_only': validate_only,
            'message': message,
            'fetched': 0,
            'uploaded': 0,
            'skipped': 0,
            'failed': 0,
            'invalid': 0,
            'lookback_days': clamp_lookback_days(days),
        }
        if send_summary:
            _safe_summary(summary)
        return summary

    lookback_days = clamp_lookback_days(days)
    try:
        orders = fetch_completed_orders(days=lookback_days)
    except Exception:
        logger.exception('KeyCRM: не вдалося отримати замовлення')
        summary = {
            'not_configured': False,
            'missing': [],
            'validate_only': validate_only,
            'message': 'keycrm_fetch_failed',
            'fetched': 0,
            'uploaded': 0,
            'skipped': 0,
            'failed': 0,
            'invalid': 0,
            'lookback_days': lookback_days,
        }
        _safe_failure(summary, 'keycrm_fetch_failed')
        if send_summary:
            _safe_summary(summary)
        return summary

    now = datetime.now(dt_timezone.utc)
    pending = []
    skipped = 0
    order_ids = []
    orders_by_id = {}
    for order in orders:
        order_id = order_id_of(order)
        if order_id is None:
            skipped += 1
            continue
        order_ids.append(order_id)
        orders_by_id[order_id] = order

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
        try:
            event = build_event(order, now=now)
        except Exception:
            logger.exception(
                'Data Manager: помилка побудови події order_id=%s',
                order_id,
            )
            if not validate_only:
                _mark_many(
                    [order_id],
                    OfflineConversionLog.STATUS_FAILED,
                    'build_event_failed',
                    orders_by_id=orders_by_id,
                )
            skipped += 1
            continue
        if event is None:
            skipped += 1
            continue
        pending.append((order_id, event))

    uploaded = 0
    failed = 0
    invalid = 0
    if pending:
        uploaded, failed, invalid = _upload_pending(
            pending,
            validate_only=validate_only,
            orders_by_id=orders_by_id,
        )

    summary = {
        'not_configured': False,
        'missing': [],
        'validate_only': validate_only,
        'message': '',
        'fetched': len(orders),
        'uploaded': uploaded,
        'skipped': skipped,
        'failed': failed,
        'invalid': invalid,
        'lookback_days': lookback_days,
    }
    logger.info(
        'Data Manager: отримано %s, вивантажено %s, пропущено %s, '
        'помилки %s, невалідні %s, перевірка %s, вікно %s дн.',
        summary['fetched'], uploaded, skipped, failed, invalid,
        validate_only, lookback_days,
    )
    if failed:
        _safe_failure(summary)
    if send_summary:
        _safe_summary(summary)
    return summary


def fetch_completed_orders(*, days=None) -> list:
    start, end = _window(days=days)
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


def clamp_lookback_days(days=None) -> int:
    raw = days
    if raw is None:
        raw = getattr(settings, 'KEYCRM_CONVERSION_DAYS', None)
    if raw is None or raw == '':
        raw = os.environ.get('KEYCRM_CONVERSION_DAYS')
    if raw is None or raw == '':
        raw = getattr(settings, 'LOOKBACK_DAYS', None)
    if raw is None or raw == '':
        raw = os.environ.get('LOOKBACK_DAYS')
    value = _DEFAULT_LOOKBACK_DAYS
    if isinstance(raw, str):
        raw = raw.strip()
    if raw not in (None, '') and not isinstance(raw, bool):
        try:
            if isinstance(raw, float) and not raw.is_integer():
                raise ValueError
            parsed = int(raw)
        except (TypeError, ValueError):
            parsed = _DEFAULT_LOOKBACK_DAYS
        else:
            value = parsed
    if value < _MIN_LOOKBACK_DAYS:
        return _MIN_LOOKBACK_DAYS
    if value > _MAX_LOOKBACK_DAYS:
        return _MAX_LOOKBACK_DAYS
    return value


def _lookback(days=None) -> timedelta:
    return timedelta(days=clamp_lookback_days(days))


def _window(days=None):
    end = datetime.now(dt_timezone.utc)
    return end - _lookback(days=days), end


def _upload_pending(pending, *, validate_only: bool, orders_by_id: dict) -> tuple[int, int, int]:
    try:
        token = _google_access_token()
    except Exception:
        logger.exception('Google OAuth: не вдалося отримати токен')
        order_ids = [item[0] for item in pending]
        if not validate_only:
            _mark_many(
                order_ids,
                OfflineConversionLog.STATUS_FAILED,
                'oauth_failed',
                orders_by_id=orders_by_id,
            )
        return 0, len(order_ids), 0

    uploaded = 0
    failed = 0
    invalid = 0
    for offset in range(0, len(pending), UPLOAD_CHUNK):
        chunk = pending[offset:offset + UPLOAD_CHUNK]
        try:
            up, fail, bad = _ingest_chunk(
                token,
                chunk,
                validate_only=validate_only,
                can_drop=True,
                orders_by_id=orders_by_id,
            )
            uploaded += up
            failed += fail
            invalid += bad
        except Exception:
            logger.exception(
                'Data Manager: помилка пачки offset=%s size=%s',
                offset, len(chunk),
            )
            order_ids = [item[0] for item in chunk]
            if not validate_only:
                _mark_many(
                    order_ids,
                    OfflineConversionLog.STATUS_FAILED,
                    'chunk_failed',
                    orders_by_id=orders_by_id,
                )
            failed += len(order_ids)
    return uploaded, failed, invalid


def _ingest_chunk(token, chunk, *, validate_only: bool, can_drop: bool, orders_by_id: dict):
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
        _mark_uploaded(order_ids, validate_only=validate_only, orders_by_id=orders_by_id)
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
                token, chunk, grouped,
                validate_only=validate_only,
                orders_by_id=orders_by_id,
            )

    message = _safe_error(response)
    if _is_duplicate_error(response):
        logger.info(
            'Data Manager: дубль transactionId, чанк вважаємо вивантаженим: %s',
            message,
        )
        _mark_uploaded(order_ids, validate_only=validate_only, orders_by_id=orders_by_id)
        return len(order_ids), 0, 0
    logger.error('Data Manager HTTP %s: %s', response.status_code, message)
    if not validate_only:
        _mark_many(
            order_ids,
            OfflineConversionLog.STATUS_FAILED,
            message,
            orders_by_id=orders_by_id,
        )
    return 0, len(order_ids), 0


def _drop_invalid_and_retry(token, chunk, grouped, *, validate_only: bool, orders_by_id: dict):
    keep = []
    for index, item in enumerate(chunk):
        if index not in grouped:
            keep.append(item)
            continue
        if not validate_only:
            _mark_many(
                [item[0]],
                OfflineConversionLog.STATUS_FAILED,
                _invalid_error(grouped[index]),
                orders_by_id=orders_by_id,
            )
    dropped = len(chunk) - len(keep)
    if not keep:
        return 0, 0, dropped
    uploaded, failed, _again = _ingest_chunk(
        token, keep,
        validate_only=validate_only,
        can_drop=False,
        orders_by_id=orders_by_id,
    )
    return uploaded, failed, dropped


def _mark_uploaded(order_ids, *, validate_only: bool, orders_by_id: dict) -> None:
    if validate_only:
        return
    _mark_many(
        order_ids,
        OfflineConversionLog.STATUS_UPLOADED,
        '',
        orders_by_id=orders_by_id,
    )


def _collect_pages(mode, between, start) -> list:
    found = []
    seen = set()
    for status_id in _completed_status_ids():
        for page in range(1, MAX_PAGES + 1):
            params = {
                'include': 'buyer,custom_fields',
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
                for item in batch:
                    order_id = order_id_of(item)
                    if order_id is None or order_id in seen:
                        continue
                    seen.add(order_id)
                    found.append(item)
            else:
                older = False
                for item in batch:
                    moment = order_time(item)
                    if moment is None or moment >= start:
                        order_id = order_id_of(item)
                        if order_id is None or order_id in seen:
                            continue
                        seen.add(order_id)
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


def _completed_status_ids() -> list[int]:
    raw = getattr(settings, 'KEYCRM_COMPLETED_STATUS_IDS', None)
    if raw in (None, ''):
        raw = os.environ.get('KEYCRM_COMPLETED_STATUS_IDS')
    if raw in (None, ''):
        singular = getattr(settings, 'KEYCRM_COMPLETED_STATUS_ID', 12)
        try:
            value = int(singular)
        except (TypeError, ValueError):
            value = 12
        return [value] if value > 0 else [12]
    if isinstance(raw, (list, tuple)):
        parts = [str(item) for item in raw]
    else:
        parts = str(raw).split(',')
    ids = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    return ids or [12]


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


def _mark_many(order_ids, status, error, *, orders_by_id=None):
    now = dj_timezone.now() if status == OfflineConversionLog.STATUS_UPLOADED else None
    orders_by_id = orders_by_id or {}
    for order_id in order_ids:
        defaults = {
            'status': status,
            'uploaded_at': now,
            'error': '' if status == OfflineConversionLog.STATUS_UPLOADED else (error or '')[:2000],
        }
        order = orders_by_id.get(order_id)
        if order is not None:
            defaults.update(_log_meta(order))
        OfflineConversionLog.objects.update_or_create(
            keycrm_order_id=order_id,
            defaults=defaults,
        )


def _log_meta(order) -> dict:
    clicks = click_ids(order)
    amount = order_amount(order)
    return {
        'order_date': order_time(order),
        'order_status': order_status_label(order),
        'amount': amount,
        'utm_campaign': utm_campaign_of(order),
        'has_gclid': bool(clicks),
        'has_contact': has_contact(order),
    }


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
    digit_names = {
        'GOOGLE_ADS_CUSTOMER_ID',
        'GOOGLE_ADS_CONVERSION_ACTION_ID',
    }
    required = (
        'KEYCRM_API_KEY',
        'GOOGLE_ADS_CLIENT_ID',
        'GOOGLE_ADS_CLIENT_SECRET',
        'GOOGLE_DATAMANAGER_REFRESH_TOKEN',
        'GOOGLE_ADS_CUSTOMER_ID',
        'GOOGLE_ADS_CONVERSION_ACTION_ID',
    )
    missing = []
    for name in required:
        value = _digits(_setting(name)) if name in digit_names else _setting(name)
        if not value:
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
    text = str(message or '').strip()
    if text:
        return text[:500]
    return f'HTTP {response.status_code}'


def _safe_failure(summary, error=''):
    try:
        from orders.telegram_notify import notify_import_failure
        notify_import_failure(summary, error=error)
    except Exception:
        logger.exception('Telegram: збій сповіщення про помилку імпорту')


def _safe_summary(summary):
    try:
        from orders.telegram_notify import notify_daily_summary
        notify_daily_summary(summary)
    except Exception:
        logger.exception('Telegram: збій щоденного підсумку')
