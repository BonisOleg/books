"""Парсинг і форматування дати відправки товару."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from django.utils import timezone

SHIP_DATE_DISPLAY_FORMAT = '%d.%m.%Y'

_RELATIVE_OFFSETS = {
    'сьогодні': 0,
    'today': 0,
    'завтра': 1,
    'tomorrow': 1,
    'післязавтра': 2,
    'після завтра': 2,
    'day after tomorrow': 2,
    'day-after-tomorrow': 2,
}

_PREFIX_RE = re.compile(
    r'^(?:відправимо|відправка|відправлення|ships?|shipping)\s+',
    re.IGNORECASE,
)

_DATE_FORMATS = (
    '%d.%m.%Y',
    '%Y-%m-%d',
    '%d/%m/%Y',
    '%d-%m-%Y',
    '%Y.%m.%d',
    '%d.%m.%y',
    '%d/%m/%y',
    '%d-%m-%y',
)


def local_today() -> date:
    return timezone.localdate()


def format_ship_date(value: date) -> str:
    return value.strftime(SHIP_DATE_DISPLAY_FORMAT)


def parse_shipping_time_text(raw, *, today: date | None = None) -> date | None:
    """Повертає date для однозначних форматів / відносних фраз, інакше None."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    base = today if today is not None else local_today()
    normalized = re.sub(r'\s+', ' ', text.casefold()).strip(' .,:;!-')

    offset = _RELATIVE_OFFSETS.get(normalized)
    if offset is not None:
        return base + timedelta(days=offset)

    stripped = _PREFIX_RE.sub('', normalized).strip(' .,:;!-')
    offset = _RELATIVE_OFFSETS.get(stripped)
    if offset is not None:
        return base + timedelta(days=offset)

    for candidate in (text.strip(), normalized):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None
