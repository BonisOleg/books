"""Нормалізація контактів і подія Google Data Manager."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_LOOKBACK_HOURS = 48

try:
    KYIV = ZoneInfo('Europe/Kyiv')
except ZoneInfoNotFoundError:
    KYIV = dt_timezone(timedelta(hours=3))


def sha256_hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def normalize_phone_e164(phone) -> str | None:
    if phone is None:
        return None
    cleaned = re.sub(r'[\s().\-]', '', str(phone).strip())
    if not cleaned:
        return None
    has_plus = cleaned.startswith('+')
    digits = cleaned[1:] if has_plus else cleaned
    if not digits.isdigit():
        return None
    if len(digits) == 10 and digits.startswith('0'):
        return '+380' + digits[1:]
    if len(digits) == 9:
        return '+380' + digits
    if len(digits) == 11 and digits.startswith('80'):
        return '+380' + digits[2:]
    if len(digits) == 12 and digits.startswith('380'):
        return '+' + digits
    if digits.startswith('380'):
        return None
    if has_plus and 8 <= len(digits) <= 15:
        return '+' + digits
    return None


def normalize_and_hash_phone(phone) -> str | None:
    normalized = normalize_phone_e164(phone)
    if not normalized:
        return None
    return sha256_hash(normalized)


def normalize_and_hash_email(email) -> str | None:
    if not email or '@' not in str(email):
        return None
    text = re.sub(r'\s+', '', str(email)).lower()
    if '@' not in text:
        return None
    local_part, domain = text.split('@', 1)
    if domain in ('gmail.com', 'googlemail.com'):
        local_part = local_part.replace('.', '').split('+', 1)[0]
    if not local_part or not domain:
        return None
    return sha256_hash(f'{local_part}@{domain}')


def format_conversion_datetime(moment: datetime) -> str:
    local = moment.astimezone(KYIV)
    offset = local.strftime('%z')
    if len(offset) == 5:
        offset = f'{offset[:3]}:{offset[3:]}'
    return f"{local.strftime('%Y-%m-%d %H:%M:%S')}{offset}"


def format_event_timestamp(moment: datetime) -> str:
    local = moment.astimezone(KYIV)
    offset = local.strftime('%z')
    if len(offset) == 5:
        offset = f'{offset[:3]}:{offset[3:]}'
    return f"{local.strftime('%Y-%m-%dT%H:%M:%S')}{offset}"


def build_event(order, *, now=None) -> dict | None:
    order_id = order_id_of(order)
    if order_id is None:
        return None
    buyer = _buyer(order)
    hashed_phone = normalize_and_hash_phone(buyer.get('phone'))
    hashed_email = normalize_and_hash_email(buyer.get('email'))
    gclid = _gclid(order)
    if not hashed_phone and not hashed_email and not gclid:
        logger.info('Пропуск події transactionId=keycrm-%s', order_id)
        return None

    moment = now or datetime.now(dt_timezone.utc)
    event = {
        'transactionId': f'keycrm-{order_id}',
        'eventTimestamp': format_event_timestamp(_event_moment(order, moment)),
        'conversionValue': _conversion_value(order),
        'currency': 'UAH',
        'eventSource': 'WEB',
    }
    if gclid:
        event['adIdentifiers'] = {'gclid': gclid}
    identifiers = []
    if hashed_phone:
        identifiers.append({'phoneNumber': hashed_phone})
    if hashed_email:
        identifiers.append({'emailAddress': hashed_email})
    if identifiers:
        event['userData'] = {'userIdentifiers': identifiers}
    return event


def build_conversion(order, *, now=None, **_legacy):
    """Сумісний виклик build_event. customer_id/action_id ігноруються."""
    return build_event(order, now=now)


def order_id_of(order):
    try:
        value = int(order.get('id'))
    except (TypeError, ValueError, AttributeError):
        return None
    if value <= 0:
        return None
    return value


def order_time(order):
    for key in ('updated_at', 'closed_at', 'status_changed_at', 'created_at'):
        moment = _parse_dt(order.get(key))
        if moment:
            return moment
    return None


def source_event_moment(order):
    """Час події з KeyCRM: closed_at, далі status_changed_at, updated_at, created_at."""
    if not isinstance(order, dict):
        return None
    for key in ('closed_at', 'status_changed_at', 'updated_at', 'created_at'):
        moment = _parse_dt(order.get(key))
        if moment:
            return moment
    return None


def _event_moment(order, now: datetime) -> datetime:
    moment = source_event_moment(order)
    if moment is None or moment > now + timedelta(minutes=5):
        moment = now
    if moment > now:
        moment = now - timedelta(seconds=60)
    return moment


_GCLID_KEYS = frozenset({'gclid', 'utm_gclid'})


def _gclid(order) -> str:
    if not isinstance(order, dict):
        return ''
    for container in _gclid_containers(order):
        for key, value in container.items():
            if str(key).lower() not in _GCLID_KEYS:
                continue
            text = _clean_gclid(value)
            if text:
                return text
    return ''


def _gclid_containers(order) -> list:
    found = [order]
    marketing = order.get('marketing')
    if isinstance(marketing, dict):
        found.append(marketing)
        nested = marketing.get('utm')
        if isinstance(nested, dict):
            found.append(nested)
    utm = order.get('utm')
    if isinstance(utm, dict):
        found.append(utm)
    return found


def _clean_gclid(value) -> str:
    if not isinstance(value, str):
        return ''
    text = value.strip()
    if not text or any(ch.isspace() for ch in text) or len(text) > 500:
        return ''
    return text


def _conversion_value(order) -> float:
    raw = order.get('grand_total')
    if raw in (None, ''):
        raw = order.get('total') or 0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value < 0:
        return 0.0
    return value


def _buyer(order) -> dict:
    buyer = order.get('buyer') or {}
    if isinstance(buyer, dict) and isinstance(buyer.get('data'), dict):
        return buyer['data']
    return buyer if isinstance(buyer, dict) else {}


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip().replace('Z', '+00:00')
        moment = None
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
                try:
                    moment = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    moment = None
        if moment is None:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=KYIV)
    return moment.astimezone(dt_timezone.utc)


_EVENT_INDEX = re.compile(r'events\[(\d+)\]')


def _response_dict(response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _field_violations(response):
    error = _response_dict(response).get('error')
    details = error.get('details') if isinstance(error, dict) else None
    if not isinstance(details, list):
        return []
    found = []
    for detail in details:
        items = detail.get('fieldViolations') if isinstance(detail, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            field = ' '.join(str(item.get('field') or '').split())
            description = ' '.join(str(item.get('description') or '').split())[:300]
            if field or description:
                found.append((field, description))
    return found


def _violations_by_event(violations, size):
    grouped = {}
    for field, description in violations:
        match = _EVENT_INDEX.search(field)
        if not match:
            continue
        index = int(match.group(1))
        if 0 <= index < size:
            grouped.setdefault(index, []).append((field, description))
    return grouped


def _invalid_error(items) -> str:
    parts = [f'{field}: {description}' for field, description in items]
    return ('invalid: ' + '; '.join(parts))[:2000]


def _lookback() -> timedelta:
    raw = getattr(settings, 'LOOKBACK_HOURS', None)
    if raw is None:
        raw = os.environ.get('LOOKBACK_HOURS')
    hours = _DEFAULT_LOOKBACK_HOURS
    if isinstance(raw, str):
        raw = raw.strip()
    if raw not in (None, '') and not isinstance(raw, bool):
        try:
            if isinstance(raw, float) and not raw.is_integer():
                raise ValueError
            parsed = int(raw)
        except (TypeError, ValueError):
            parsed = 0
        if parsed > 0:
            hours = parsed
    return timedelta(hours=hours)


def _window():
    end = datetime.now(dt_timezone.utc)
    return end - _lookback(), end


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
