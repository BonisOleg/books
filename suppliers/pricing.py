"""Правило ціни постачальника: як у фіді або націнка, далі округлення."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from suppliers.constants import PRICE_MARKUP, ROUND_ONE, ROUND_TEN
from suppliers.exceptions import PriceComputeError

_ONE = Decimal('1')
_TEN = Decimal('10')
_HUNDRED = Decimal('100')
_CENTS = Decimal('0.01')
_MAX_PRICE = Decimal('10000000000')
_PERCENT_CAP = Decimal('99999999999999.99')


def compute_price(feed_price: Decimal, supplier) -> Decimal:
    value = Decimal(feed_price)
    if supplier.price_rule == PRICE_MARKUP:
        markup = Decimal(supplier.markup_percent)
        value = value * (_HUNDRED + markup) / _HUNDRED
    rounded = _round(value, supplier.rounding)
    if rounded < 0:
        raise PriceComputeError('Відʼємна ціна після правила.')
    if rounded >= _MAX_PRICE:
        raise PriceComputeError('Ціна не вміщається в поле каталогу.')
    return rounded


def change_percent(old: Decimal, new: Decimal) -> Decimal | None:
    """Відсоток |нова − стара| / стара × 100. None, якщо стара ціна 0."""
    old = Decimal(old)
    new = Decimal(new)
    if old == 0:
        return None
    raw = (abs(new - old) * _HUNDRED / old).quantize(_CENTS, rounding=ROUND_HALF_UP)
    if raw > _PERCENT_CAP:
        return _PERCENT_CAP
    return raw


def needs_confirmation(old: Decimal, new: Decimal, threshold: Decimal) -> bool:
    """Поріг 0 не стримує зміну. Порівняння за відсотком, округленим до копійки відсотка."""
    threshold = Decimal(threshold)
    if threshold <= 0:
        return False
    percent = change_percent(old, new)
    if percent is None:
        return Decimal(new) != Decimal(old)
    return percent > threshold


def _round(value: Decimal, rounding: str) -> Decimal:
    if rounding == ROUND_ONE:
        value = value.quantize(_ONE, rounding=ROUND_HALF_UP)
    elif rounding == ROUND_TEN:
        value = (value / _TEN).quantize(_ONE, rounding=ROUND_HALF_UP) * _TEN
    else:
        value = value.quantize(_CENTS, rounding=ROUND_HALF_UP)
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)
