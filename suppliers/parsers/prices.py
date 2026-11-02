"""Розбір цін Google Merchant: «28630 UAH», «28630.00 UAH», «28 630,50 UAH»."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from suppliers.exceptions import PriceParseError

_SPACES = re.compile(r'[\s\u00a0\u202f\u2009]+')
_NUMBER = re.compile(r'\d+(?:\.\d+)?')


def parse_feed_price(raw: str) -> tuple[Decimal, str]:
    text = _SPACES.sub(' ', (raw or '').strip())
    if not text:
        raise PriceParseError('порожня ціна')
    parts = text.split(' ')
    if len(parts) < 2:
        shown = text[:80]
        raise PriceParseError(f'невалідна ціна «{shown}»')
    currency = parts[-1]
    if currency.casefold() != 'uah':
        raise PriceParseError(f'валюта не UAH («{currency[:16]}»)')
    number = _normalize_number(''.join(parts[:-1]))
    if not _NUMBER.fullmatch(number):
        shown = text[:80]
        raise PriceParseError(f'невалідна ціна «{shown}»')
    try:
        value = Decimal(number)
    except InvalidOperation as exc:
        raise PriceParseError(f'невалідна ціна «{text[:80]}»') from exc
    if value < 0:
        raise PriceParseError('відʼємна ціна')
    return value, 'UAH'


def _normalize_number(raw: str) -> str:
    number = raw.replace("'", '').replace('’', '').replace(' ', '')
    has_comma = ',' in number
    has_dot = '.' in number
    if has_comma and has_dot:
        if number.rfind(',') > number.rfind('.'):
            number = number.replace('.', '').replace(',', '.')
        else:
            number = number.replace(',', '')
        return number
    if has_comma:
        left, right = number.split(',', 1)
        if right.isdigit() and len(right) <= 2:
            return f'{left}.{right}'
        return number.replace(',', '')
    return number
