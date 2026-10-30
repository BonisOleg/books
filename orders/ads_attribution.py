"""First-party cookie ofion_ads і атрибуція для Order / KeyCRM."""

from __future__ import annotations

import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from urllib.parse import unquote

from django.conf import settings

COOKIE_NAME = 'ofion_ads'
COOKIE_MAX_AGE = 90 * 24 * 60 * 60
ADS_KEYS = (
    'gclid',
    'gbraid',
    'wbraid',
    'utm_source',
    'utm_medium',
    'utm_campaign',
    'utm_term',
    'utm_content',
)
UTM_KEYS = (
    'utm_source',
    'utm_medium',
    'utm_campaign',
    'utm_term',
    'utm_content',
)
_FIELD_MAX = 500


def read_ads_cookie(request) -> dict[str, str]:
    raw = (request.COOKIES.get(COOKIE_NAME) or '').strip()
    if not raw:
        return {}
    data = _decode_cookie(raw)
    if not isinstance(data, dict):
        return {}
    clean = {}
    for key in ADS_KEYS:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()[:_FIELD_MAX]
        if text:
            clean[key] = text
    return clean


def params_from_query(request) -> dict[str, str]:
    found = {}
    for key in ADS_KEYS:
        value = (request.GET.get(key) or '').strip()[:_FIELD_MAX]
        if value:
            found[key] = value
    return found


def merge_ads(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    merged = dict(existing or {})
    for key, value in (incoming or {}).items():
        if key in ADS_KEYS and value:
            merged[key] = str(value).strip()[:_FIELD_MAX]
    return {key: merged[key] for key in ADS_KEYS if merged.get(key)}


def encode_ads_cookie(data: dict[str, str]) -> str:
    payload = {key: data[key] for key in ADS_KEYS if data.get(key)}
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def set_ads_cookie(response, data: dict[str, str]) -> None:
    if not data:
        return
    response.set_cookie(
        COOKIE_NAME,
        encode_ads_cookie(data),
        max_age=COOKIE_MAX_AGE,
        samesite='Lax',
        secure=not getattr(settings, 'DEBUG', False),
        httponly=False,
        path='/',
    )


def apply_ads_to_order(order, request) -> list[str]:
    """Записує поля атрибуції з cookie на Order. Повертає змінені поля."""
    data = read_ads_cookie(request)
    if not data:
        return []
    changed = []
    for key in ADS_KEYS:
        value = data.get(key) or ''
        if not value:
            continue
        if getattr(order, key, '') == value:
            continue
        setattr(order, key, value)
        changed.append(key)
    return changed


def marketing_from_order(order) -> dict[str, str]:
    marketing = {}
    for key in UTM_KEYS:
        value = (getattr(order, key, '') or '').strip()
        if value:
            marketing[key] = value
    return marketing


def click_custom_fields(order) -> list[dict]:
    """custom_fields для KeyCRM з UUID з settings/env; без UUID — пропускаємо."""
    mapping = (
        ('gclid', 'KEYCRM_CF_GCLID_UUID'),
        ('gbraid', 'KEYCRM_CF_GBRAID_UUID'),
        ('wbraid', 'KEYCRM_CF_WBRAID_UUID'),
    )
    fields = []
    for attr, setting_name in mapping:
        value = (getattr(order, attr, '') or '').strip()
        uuid = str(getattr(settings, setting_name, '') or '').strip()
        if value and uuid:
            fields.append({'uuid': uuid, 'value': value})
    return fields


def _decode_cookie(raw: str):
    for decoder in (_decode_b64, _decode_quoted_json):
        try:
            return decoder(raw)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            continue
    return None


def _decode_b64(raw: str):
    padding = '=' * (-len(raw) % 4)
    return json.loads(urlsafe_b64decode(raw + padding).decode('utf-8'))


def _decode_quoted_json(raw: str):
    return json.loads(unquote(raw))
