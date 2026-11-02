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


def _round(value: Decimal, rounding: str) -> Decimal:
    if rounding == ROUND_ONE:
        value = value.quantize(_ONE, rounding=ROUND_HALF_UP)
    elif rounding == ROUND_TEN:
        value = (value / _TEN).quantize(_ONE, rounding=ROUND_HALF_UP) * _TEN
    else:
        value = value.quantize(_CENTS, rounding=ROUND_HALF_UP)
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)
