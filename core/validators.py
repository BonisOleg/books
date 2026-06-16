import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

UA_MOBILE_CODES = frozenset({
    '39', '50', '63', '66', '67', '68', '73', '75', '77',
    '91', '92', '93', '94', '95', '96', '97', '98', '99',
})

PHONE_INVALID_MSG = _(
    'Введіть коректний український номер телефону у форматі +380 XX XXX XX XX'
)

PHONE_WIDGET_ATTRS = {
    'class': 'form-input',
    'placeholder': '+380 XX XXX XX XX',
    'type': 'tel',
    'inputmode': 'tel',
    'autocomplete': 'tel',
    'data-phone-input': 'true',
    'maxlength': '19',
    'required': True,
}


def extract_phone_digits(value):
    return re.sub(r'\D', '', str(value).strip())


def normalize_ua_phone(value):
    """Normalize to +380XXXXXXXXX or return None if invalid."""
    digits = extract_phone_digits(value)
    if not digits:
        return None

    if len(digits) == 12 and digits.startswith('380'):
        national = digits[3:]
    elif len(digits) == 10 and digits.startswith('0'):
        national = digits[1:]
    elif len(digits) == 9:
        national = digits
    else:
        return None

    if len(national) != 9 or national[:2] not in UA_MOBILE_CODES:
        return None

    return f'+380{national}'


def validate_ua_phone(value):
    normalized = normalize_ua_phone(value)
    if not normalized:
        raise ValidationError(PHONE_INVALID_MSG, code='invalid_phone')
    return normalized
