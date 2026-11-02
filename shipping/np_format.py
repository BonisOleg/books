"""Числа, телефон і номер відділення для ТТН. Без запитів до API."""

import re
from decimal import Decimal, InvalidOperation

_INDEX_MARK = re.compile(r'№\s*(\d+)')
_INDEX_WORD = re.compile(r'(?:відділення|поштомат)\s*№?\s*(\d+)', re.IGNORECASE)


def warehouse_index(text):
    marked = _INDEX_MARK.search(text or '')
    if marked:
        return marked.group(1)
    word = _INDEX_WORD.search(text or '')
    if word:
        return word.group(1)
    return ''


def recipient_name(order):
    parts = [order.last_name, order.first_name, order.patronymic]
    return ' '.join(part.strip() for part in parts if part and part.strip())


def np_phone(value):
    digits = re.sub(r'\D', '', str(value or ''))
    if len(digits) == 10 and digits.startswith('0'):
        return '38' + digits
    if len(digits) == 9:
        return '380' + digits
    return digits


def first_phone(value):
    if isinstance(value, (list, tuple)):
        for item in value:
            phone = np_phone(item)
            if phone:
                return phone
        return ''
    return np_phone(value)


def money(value):
    try:
        amount = Decimal(value or 0).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal('0.00')
    return format(amount, 'f')


def weight(value):
    number = Decimal(value).quantize(Decimal('0.001'))
    text = format(number, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def parse_cost(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return None
