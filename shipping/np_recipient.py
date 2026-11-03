"""Отримувач інтернет-документа Нової Пошти.

Counterparty.save створює приватну особу (CounterpartyType=PrivatePerson,
CounterpartyProperty=Recipient, FirstName, LastName, MiddleName, Phone).
Recipient — Ref контрагента, ContactRecipient — ContactPerson.data[0].Ref.
InternetDocument.save на відділення: CityRecipient — Ref міста,
RecipientAddress — Ref відділення. RecipientWarehouseIndex не передається.
https://developers.novaposhta.ua/ (Counterparty.save, InternetDocument.save)
"""

import re

from .np_errors import humanize_np_response
from .np_format import np_phone, recipient_name

MSG_NO_NAME = 'Не вказано ім’я отримувача'
MSG_BAD_PHONE = 'Некоректний телефон отримувача'
MSG_NO_CITY_REF = 'Не вказано Ref міста отримувача'
MSG_NO_WAREHOUSE_REF = 'Не вказано Ref відділення отримувача'
MSG_NO_ADDRESS = 'Не вказано адресу отримувача'
MSG_NO_RECIPIENT = 'Нова Пошта не повернула отримувача'
MSG_NO_CONTACT = 'Нова Пошта не повернула контакт отримувача'

_BRANCH_HINT = re.compile(r'відділен|поштомат|postomat', re.IGNORECASE)


def recipient_to_doors(order):
    if (order.warehouse_ref or '').strip():
        return False
    if any((
        (getattr(order, 'recipient_street', '') or '').strip(),
        (getattr(order, 'recipient_house', '') or '').strip(),
        (getattr(order, 'recipient_area', '') or '').strip(),
        (getattr(order, 'recipient_flat', '') or '').strip(),
    )):
        return True
    text = (order.warehouse or '').strip()
    return bool(text) and not _BRANCH_HINT.search(text)


def assert_recipient_ready(order):
    """Перевірка до будь-якого запиту в Нову Пошту."""
    from .np_ttn import NpUserError, _require_phone

    first, last, _middle = name_parts(order)
    if not first or not last:
        raise NpUserError(MSG_NO_NAME)
    _require_phone(order.phone, MSG_BAD_PHONE)
    if recipient_to_doors(order):
        city = (order.city or '').strip()
        street = (getattr(order, 'recipient_street', '') or '').strip() or (order.warehouse or '').strip()
        if not city or not street:
            raise NpUserError(MSG_NO_ADDRESS)
        return
    if not (getattr(order, 'city_ref', '') or '').strip():
        raise NpUserError(MSG_NO_CITY_REF)
    if not (order.warehouse_ref or '').strip():
        raise NpUserError(MSG_NO_WAREHOUSE_REF)


def name_parts(order):
    return (
        (order.first_name or '').strip(),
        (order.last_name or '').strip(),
        (getattr(order, 'patronymic', '') or '').strip(),
    )


def save_private_recipient(order):
    """Counterparty.save для приватної особи-отримувача.

    https://developers.novaposhta.ua/ — Counterparty.save, InternetDocument.save.
    """
    from .np_ttn import NpUserError, _redact, np_call

    first, last, middle = name_parts(order)
    data = np_call('Counterparty', 'save', {
        'CounterpartyType': 'PrivatePerson',
        'CounterpartyProperty': 'Recipient',
        'FirstName': first,
        'LastName': last,
        'MiddleName': middle,
        'Phone': np_phone(order.phone),
    })
    if not data.get('success'):
        raise NpUserError(_redact(humanize_np_response(data)))
    rows = data.get('data') or []
    row = rows[0] if rows and isinstance(rows[0], dict) else None
    if not row or not (row.get('Ref') or '').strip():
        raise NpUserError(MSG_NO_RECIPIENT)
    contact = contact_person_ref(row.get('ContactPerson'))
    if not contact:
        raise NpUserError(MSG_NO_CONTACT)
    return (row.get('Ref') or '').strip(), contact


def contact_person_ref(contact):
    """Ref з ContactPerson.data[0] або з обгортки-списку актуальної відповіді API."""
    if isinstance(contact, dict):
        if contact.get('success') is False:
            return ''
        return _first_ref(contact.get('data'))
    if isinstance(contact, list):
        for item in contact:
            if not isinstance(item, dict):
                continue
            if 'data' in item:
                if item.get('success') is False:
                    continue
                ref = _first_ref(item.get('data'))
            else:
                ref = (item.get('Ref') or '').strip()
            if ref:
                return ref
    return ''


def _first_ref(data):
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return ''
    return (data[0].get('Ref') or '').strip()


def apply_recipient(payload, order, to_doors, recipient_ref, contact_ref):
    payload['Recipient'] = recipient_ref
    payload['ContactRecipient'] = contact_ref
    payload.pop('RecipientWarehouseIndex', None)
    if to_doors:
        street = (order.recipient_street or '').strip() or (order.warehouse or '').strip()
        payload['NewAddress'] = '1'
        payload['RecipientCityName'] = (order.city or '').strip()
        payload['RecipientName'] = recipient_name(order)
        payload['RecipientType'] = 'PrivatePerson'
        area = (order.recipient_area or '').strip()
        if area:
            payload['RecipientArea'] = area
        payload['RecipientAddressName'] = street
        house = (order.recipient_house or '').strip()
        flat = (order.recipient_flat or '').strip()
        if house:
            payload['RecipientHouse'] = house
        if flat:
            payload['RecipientFlat'] = flat
        return
    payload['CityRecipient'] = (order.city_ref or '').strip()
    payload['RecipientAddress'] = (order.warehouse_ref or '').strip()
