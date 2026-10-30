"""Нормалізація контактів і подія Google Data Manager."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    KYIV = ZoneInfo('Europe/Kyiv')
except ZoneInfoNotFoundError:
    KYIV = dt_timezone(timedelta(hours=3))

_UTM_CAMPAIGN_KEYS = frozenset({'utm_campaign'})


def sha256_hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def first_contact_value(value) -> str:
    """email/телефон у KeyCRM можуть бути рядком або списком."""
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        for item in value:
            text = str(item or '').strip()
            if text:
                return text
        return ''
    return str(value).strip()


def normalize_phone_e164(phone) -> str | None:
    phone = first_contact_value(phone)
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
    email = first_contact_value(email)
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


def is_offline_order(order) -> bool:
    """Офлайн = порожній source_uuid і (якщо задано) source_id ≠ KEYCRM_SITE_SOURCE_ID."""
    if not isinstance(order, dict):
        return True
    source_uuid = str(order.get('source_uuid') or '').strip()
    if source_uuid:
        return False
    site_source = str(getattr(settings, 'KEYCRM_SITE_SOURCE_ID', '') or '').strip()
    if not site_source:
        return True
    return str(order.get('source_id') or '').strip() != site_source


def resolve_event_source(order) -> str:
    """WEB для сайту, OTHER для офлайн (Data Manager). Одна точка зміни."""
    return 'OTHER' if is_offline_order(order) else 'WEB'


def build_event(order, *, now=None) -> dict | None:
    order_id = order_id_of(order)
    if order_id is None:
        return None
    transaction_id = transaction_id_of(order)
    if not transaction_id:
        return None
    buyer = _buyer(order)
    hashed_phone = normalize_and_hash_phone(buyer.get('phone'))
    hashed_email = normalize_and_hash_email(buyer.get('email'))
    clicks = click_ids(order)
    if not hashed_phone and not hashed_email and not clicks:
        logger.info('Пропуск події transactionId=%s', transaction_id)
        return None

    moment = now or datetime.now(dt_timezone.utc)
    event = {
        'transactionId': transaction_id,
        'eventTimestamp': format_event_timestamp(_event_moment(order, moment)),
        'conversionValue': _conversion_value(order),
        'currency': 'UAH',
        'eventSource': resolve_event_source(order),
    }
    if clicks:
        event['adIdentifiers'] = clicks
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


def transaction_id_of(order) -> str | None:
    """Номер сайту (source_uuid), інакше id KeyCRM."""
    if not isinstance(order, dict):
        return None
    source_uuid = str(order.get('source_uuid') or '').strip()
    if source_uuid:
        return source_uuid
    order_id = order_id_of(order)
    if order_id is None:
        return None
    return str(order_id)


def order_time(order):
    for key in ('updated_at', 'closed_at', 'status_changed_at', 'created_at'):
        moment = _parse_dt(order.get(key))
        if moment:
            return moment
    return None


def click_ids(order) -> dict[str, str]:
    found = {}
    for key in ('gclid', 'gbraid', 'wbraid'):
        text = _click_value(order, key)
        if text:
            found[key] = text
    return found


def utm_campaign_of(order) -> str:
    if not isinstance(order, dict):
        return ''
    for container in _value_containers(order):
        for key, value in container.items():
            if str(key).lower() not in _UTM_CAMPAIGN_KEYS:
                continue
            text = str(value or '').strip()
            if text:
                return text[:255]
    return ''


def order_amount(order) -> Decimal | None:
    raw = order.get('grand_total') if isinstance(order, dict) else None
    if raw in (None, ''):
        raw = order.get('total') if isinstance(order, dict) else None
    if raw in (None, ''):
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if value < 0:
        return Decimal('0')
    return value.quantize(Decimal('0.01'))


def order_status_label(order) -> str:
    if not isinstance(order, dict):
        return ''
    for key in ('status_name', 'status', 'status_id'):
        value = order.get(key)
        if value is None or value == '':
            continue
        if isinstance(value, dict):
            text = str(value.get('name') or value.get('id') or '').strip()
        else:
            text = str(value).strip()
        if text:
            return text[:100]
    return ''


def has_contact(order) -> bool:
    buyer = _buyer(order)
    phone = first_contact_value(buyer.get('phone'))
    email = first_contact_value(buyer.get('email'))
    return bool(
        normalize_phone_e164(phone) or normalize_and_hash_email(email)
    )


def _event_moment(order, now: datetime) -> datetime:
    moment = None
    for key in ('closed_at', 'status_changed_at', 'updated_at', 'created_at'):
        moment = _parse_dt(order.get(key))
        if moment:
            break
    if moment is None or moment > now + timedelta(minutes=5):
        moment = now
    if moment > now:
        moment = now - timedelta(seconds=60)
    return moment


def _click_value(order, name: str) -> str:
    if not isinstance(order, dict):
        return ''
    aliases = {'gclid', 'utm_gclid'} if name == 'gclid' else {name}
    for container in _value_containers(order):
        for key, value in container.items():
            if str(key).lower() not in aliases:
                continue
            text = _clean_click_id(value)
            if text:
                return text
    env_map = {
        'gclid': 'KEYCRM_CF_GCLID_UUID',
        'gbraid': 'KEYCRM_CF_GBRAID_UUID',
        'wbraid': 'KEYCRM_CF_WBRAID_UUID',
    }
    uuid = str(getattr(settings, env_map[name], '') or '').strip().casefold()
    if not uuid:
        return ''
    for item in _custom_fields(order):
        if not isinstance(item, dict):
            continue
        item_uuid = str(
            item.get('uuid') or item.get('id') or item.get('field_uuid') or ''
        ).strip().casefold()
        if item_uuid != uuid:
            continue
        text = _clean_click_id(item.get('value'))
        if text:
            return text
    return ''


def _value_containers(order) -> list:
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


def _custom_fields(order) -> list:
    raw = order.get('custom_fields') or order.get('customFields') or []
    if isinstance(raw, dict):
        raw = raw.get('data') or raw.get('items') or []
    return raw if isinstance(raw, list) else []


def _clean_click_id(value) -> str:
    if not isinstance(value, str):
        return ''
    text = value.strip()
    if not text or any(ch.isspace() for ch in text) or len(text) > 500:
        return ''
    return text


def _conversion_value(order) -> float:
    amount = order_amount(order)
    if amount is None:
        return 0.0
    return float(amount)


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
