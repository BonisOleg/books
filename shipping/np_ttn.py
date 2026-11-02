"""Інтернет-документ Нової Пошти. Ключ API не потрапляє в логи й у текст помилки."""

import hashlib
import logging
import re
import threading
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection, connections, transaction
from django.utils import timezone

from orders.models import Order

from .models import NPTTNSettings, ShipmentOrigin
from .novaposhta_api import NP_API_URL
from .np_errors import humanize_np_response
from .np_format import (
    money as _money,
    np_phone,
    parse_cost as _parse_cost,
    recipient_name as _recipient_name,
    warehouse_index as _warehouse_index,
    weight as _weight,
)

logger = logging.getLogger(__name__)

MSG_NO_KEY = 'Ключ НП не налаштовано'
MSG_UNAVAILABLE = 'НП не відповідає'
ONLINE_PAYMENT_METHODS = ('liqpay', 'monobank')
NP_TIMEOUT = 15
SENDER_CACHE_TTL = 6 * 60 * 60

_BRANCH_HINT = re.compile(r'відділен|поштомат|postomat', re.IGNORECASE)


class NpUserError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def online_payment_needs_confirm(order):
    return (
        order.payment_method in ONLINE_PAYMENT_METHODS
        and order.payment_status != 'paid'
    )


def _api_key():
    return (getattr(settings, 'NOVAPOSHTA_API_KEY', '') or '').strip()


def _redact(message):
    text = str(message or '')
    key = _api_key()
    if key:
        text = text.replace(key, '***')
    return text


class _ApiKeyLogFilter(logging.Filter):
    def filter(self, record):
        key = _api_key()
        if not key:
            return True
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        if key in rendered:
            record.msg = rendered.replace(key, '***')
            record.args = ()
        if record.exc_info:
            text = logging.Formatter().formatException(record.exc_info)
            if key in text:
                record.exc_text = text.replace(key, '***')
                record.exc_info = None
        return True


if not any(isinstance(item, _ApiKeyLogFilter) for item in logger.filters):
    logger.addFilter(_ApiKeyLogFilter())


def build_internet_document_payload(order, ttn_settings):
    origin = order.shipment_origin
    if origin is None:
        raise NpUserError('Не обрано точку відправки')

    sender_ref, contact_ref, sender_phone = resolve_sender(ttn_settings)
    weight = _pick_positive(
        order.parcel_weight, ttn_settings.default_weight, 'Не вказано вагу відправлення',
    )
    length = _pick_positive(
        order.parcel_length, ttn_settings.length, 'Не вказано довжину відправлення',
    )
    width = _pick_positive(
        order.parcel_width, ttn_settings.width, 'Не вказано ширину відправлення',
    )
    height = _pick_positive(
        order.parcel_height, ttn_settings.height, 'Не вказано висоту відправлення',
    )
    description = (ttn_settings.cargo_description or '').strip()
    if not description:
        raise NpUserError('Не вказано опис вантажу')
    recipient_name = _recipient_name(order)
    if not recipient_name:
        raise NpUserError('Не вказано ім’я отримувача')

    weight_text = _weight(weight)
    to_doors = _recipient_to_doors(order)
    payload = {
        'PayerType': ttn_settings.payer_type,
        'PaymentMethod': ttn_settings.payment_method,
        'DateTime': timezone.localdate().strftime('%d.%m.%Y'),
        'CargoType': ttn_settings.cargo_type,
        'Weight': weight_text,
        'ServiceType': _service_type(origin.kind == ShipmentOrigin.KIND_ADDRESS, to_doors),
        'SeatsAmount': '1',
        'Description': description,
        'Cost': _money(order.total),
        'CitySender': (origin.city_ref or '').strip(),
        'Sender': sender_ref,
        'SenderAddress': _sender_address(origin),
        'ContactSender': contact_ref,
        'SendersPhone': sender_phone,
        'RecipientName': recipient_name,
        'RecipientType': 'PrivatePerson',
        'RecipientsPhone': _require_phone(order.phone, 'Некоректний телефон отримувача'),
        'OptionsSeat': [{
            'volumetricWidth': str(int(Decimal(width))),
            'volumetricLength': str(int(Decimal(length))),
            'volumetricHeight': str(int(Decimal(height))),
            'weight': weight_text,
        }],
    }
    _apply_recipient(payload, order, to_doors)
    _apply_cod(payload, order, ttn_settings)
    return payload


def create_ttn(order_id, force=False):
    try:
        with transaction.atomic():
            order = _lock_order(order_id)
            if (order.ttn_number or '').strip():
                return order
            try:
                _issue_document(order)
            except NpUserError as exc:
                _store_error(order, exc.message)
            return order
    except Order.DoesNotExist:
        logger.warning('TTN: замовлення %s не знайдено', order_id)
        return None
    except Exception:
        logger.exception('TTN: неочікувана помилка для замовлення %s', order_id)
        return Order.objects.filter(pk=order_id).first()


def schedule_auto_ttn(order):
    try:
        if order is None or not getattr(order, 'pk', None):
            return
        if not _should_auto_create(order):
            return
        order_id = order.pk
        transaction.on_commit(lambda oid=order_id: enqueue_create_ttn(oid))
    except Exception:
        logger.warning(
            'TTN: не вдалося запланувати створення для замовлення %s',
            getattr(order, 'pk', None),
        )


def enqueue_create_ttn(order_id):
    thread = threading.Thread(
        target=_create_ttn_worker,
        args=(order_id,),
        daemon=True,
        name=f'np-ttn-{order_id}',
    )
    thread.start()


def _create_ttn_worker(order_id):
    try:
        create_ttn(order_id)
    except Exception:
        logger.exception('TTN: збій фонового створення для замовлення %s', order_id)
    finally:
        connections.close_all()


def _should_auto_create(order):
    try:
        config = NPTTNSettings.objects.first()
    except Exception:
        logger.warning('TTN: не вдалося прочитати налаштування')
        return False
    if config is None or not config.auto_create_ttn:
        return False
    if order.payment_method == 'cod':
        return True
    return order.payment_method in ONLINE_PAYMENT_METHODS and order.payment_status == 'paid'


def _issue_document(order):
    if order.shipment_origin_id is None:
        raise NpUserError('Не обрано точку відправки')
    if not _api_key():
        raise NpUserError(MSG_NO_KEY)
    config = NPTTNSettings.objects.first()
    if config is None:
        raise NpUserError('Налаштування ТТН не заповнені')
    payload = build_internet_document_payload(order, config)
    data = np_call('InternetDocument', 'save', payload)
    if not data.get('success'):
        raise NpUserError(_redact(humanize_np_response(data)))
    document = (data.get('data') or [{}])[0]
    number = str(document.get('IntDocNumber') or '').strip()
    if not number:
        raise NpUserError('Нова Пошта не повернула номер ТТН')
    order.ttn_number = number
    order.ttn_ref = str(document.get('Ref') or '').strip()
    order.ttn_delivery_cost = _parse_cost(document.get('CostOnSite'))
    order.ttn_status = 'created'
    order.ttn_created_at = timezone.now()
    order.ttn_error = ''
    order.save(update_fields=[
        'ttn_number', 'ttn_ref', 'ttn_delivery_cost',
        'ttn_status', 'ttn_created_at', 'ttn_error',
    ])


def np_call(model, method, properties):
    api_key = _api_key()
    if not api_key:
        raise NpUserError(MSG_NO_KEY)
    try:
        response = requests.post(
            NP_API_URL,
            json={
                'apiKey': api_key,
                'modelName': model,
                'calledMethod': method,
                'methodProperties': properties or {},
            },
            timeout=NP_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise NpUserError(MSG_UNAVAILABLE) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise NpUserError('Некоректна відповідь Нової Пошти') from exc
    if not isinstance(data, dict):
        raise NpUserError('Некоректна відповідь Нової Пошти')
    return data


def _lock_order(order_id):
    qs = Order.objects.select_related('shipment_origin')
    if connection.features.has_select_for_update:
        lock_kwargs = {}
        if connection.features.has_select_for_update_of:
            lock_kwargs['of'] = ('self',)
        qs = qs.select_for_update(**lock_kwargs)
    return qs.get(pk=order_id)


def _store_error(order, message):
    message = _redact(message)
    order.ttn_error = message
    if not order.ttn_number:
        order.ttn_status = 'error'
    order.save(update_fields=['ttn_error', 'ttn_status'])
    logger.warning('TTN: замовлення %s: %s', order.pk, message)


def resolve_sender(ttn_settings):
    sender_ref = (ttn_settings.sender_ref or '').strip()
    contact_ref = (ttn_settings.contact_sender_ref or '').strip()
    phone = np_phone(ttn_settings.sender_phone)
    if sender_ref and contact_ref:
        if not phone:
            raise NpUserError('Вкажіть телефон відправника у налаштуваннях ТТН')
        return sender_ref, contact_ref, phone
    if not _api_key():
        raise NpUserError(MSG_NO_KEY)
    kind = _sender_kind(ttn_settings.sender_type)
    cached = _cache_get(_sender_cache_key(kind))
    if cached and cached.get('sender_ref') and cached.get('contact_ref') and cached.get('phone'):
        return (
            sender_ref or cached['sender_ref'],
            contact_ref or cached['contact_ref'],
            phone or cached['phone'],
        )
    resolved = _fetch_sender(sender_ref, phone, kind)
    _cache_set(_sender_cache_key(kind), {
        'sender_ref': resolved[0],
        'contact_ref': resolved[1],
        'phone': resolved[2],
    })
    return resolved


def _sender_kind(sender_type):
    kind = (sender_type or '').strip()
    if kind == NPTTNSettings.SENDER_PRIVATE:
        return NPTTNSettings.SENDER_PRIVATE
    return NPTTNSettings.SENDER_ORGANIZATION


def _fetch_sender(sender_ref, phone, kind):
    if not sender_ref:
        data = np_call('Counterparty', 'getCounterparties', {
            'CounterpartyProperty': 'Sender',
            'Page': '1',
        })
        if not data.get('success'):
            raise NpUserError(_redact(humanize_np_response(data)))
        sender_ref = _pick_sender_ref(data.get('data') or [], kind)
        if not sender_ref:
            raise NpUserError('Не знайдено відправника в кабінеті Нової Пошти')
    contacts = np_call('Counterparty', 'getCounterpartyContactPersons', {
        'Ref': sender_ref,
        'Page': '1',
    })
    if not contacts.get('success'):
        raise NpUserError(_redact(humanize_np_response(contacts)))
    contact_ref, contact_phone = _pick_contact(contacts.get('data') or [], phone)
    if not contact_ref:
        raise NpUserError('Не знайдено контактну особу відправника')
    final_phone = phone or np_phone(contact_phone)
    if not final_phone:
        raise NpUserError('Вкажіть телефон відправника у налаштуваннях ТТН')
    return sender_ref, contact_ref, final_phone


def _pick_sender_ref(rows, sender_type):
    kind = _sender_kind(sender_type)
    for row in rows:
        if not isinstance(row, dict):
            continue
        ref = (row.get('Ref') or '').strip()
        if ref and row.get('CounterpartyType') == kind:
            return ref
    return ''


def _pick_contact(rows, phone):
    fallback = ('', '')
    for row in rows:
        if not isinstance(row, dict):
            continue
        ref = (row.get('Ref') or '').strip()
        if not ref:
            continue
        raw_phone = row.get('Phones') or row.get('Phone') or ''
        if isinstance(raw_phone, list):
            raw_phone = raw_phone[0] if raw_phone else ''
        contact_phone = np_phone(str(raw_phone))
        if not fallback[0]:
            fallback = (ref, contact_phone)
        if phone and contact_phone == phone:
            return ref, contact_phone
    return fallback


def _sender_cache_key(kind):
    digest = hashlib.sha256(_api_key().encode()).hexdigest()[:12]
    return f'np-ttn-sender:{kind}:{digest}'


def _cache_get(key):
    try:
        return cache.get(key)
    except Exception:
        logger.warning('TTN: кеш відправника недоступний')
        return None


def _cache_set(key, value):
    try:
        cache.set(key, value, SENDER_CACHE_TTL)
    except Exception:
        logger.warning('TTN: не вдалося записати кеш відправника')


def _sender_address(origin):
    if origin.kind == ShipmentOrigin.KIND_ADDRESS:
        ref = (origin.street_ref or '').strip()
        if not ref:
            raise NpUserError('Не заповнено Ref адреси забору')
        return ref
    ref = (origin.warehouse_ref or '').strip()
    if not ref:
        raise NpUserError('Не заповнено Ref відділення відправника')
    return ref


def _service_type(sender_doors, recipient_doors):
    if sender_doors and recipient_doors:
        return 'DoorsDoors'
    if sender_doors:
        return 'DoorsWarehouse'
    if recipient_doors:
        return 'WarehouseDoors'
    return 'WarehouseWarehouse'


def _recipient_to_doors(order):
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


def _apply_recipient(payload, order, to_doors):
    city = (order.city or '').strip()
    if to_doors:
        street = (order.recipient_street or '').strip() or (order.warehouse or '').strip()
        if not city or not street:
            raise NpUserError('Не вказано адресу отримувача')
        payload['NewAddress'] = '1'
        payload['RecipientCityName'] = city
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

    warehouse = (order.warehouse or '').strip()
    ref = (order.warehouse_ref or '').strip()
    if not city or not warehouse:
        raise NpUserError('Не вказано відділення отримувача')
    number = _warehouse_index(warehouse)
    payload['RecipientCityName'] = city
    payload['RecipientAddressName'] = number or warehouse
    if ref:
        payload['RecipientWarehouseIndex'] = ref
        payload['RecipientAddress'] = ref


def _apply_cod(payload, order, ttn_settings):
    if order.payment_method != 'cod':
        return
    amount = _money(order.total)
    if ttn_settings.cod_mode == NPTTNSettings.COD_BACKWARD:
        payload['BackwardDeliveryData'] = [{
            'PayerType': ttn_settings.cod_payer_type,
            'CargoType': 'Money',
            'RedeliveryString': amount,
        }]
        return
    payload['AfterpaymentOnGoodsCost'] = amount


def _pick_positive(override, fallback, message):
    value = override if override is not None else fallback
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise NpUserError(message) from exc
    if number <= 0:
        raise NpUserError(message)
    return number


def _require_phone(value, message):
    phone = np_phone(value)
    if len(phone) != 12 or not phone.startswith('380'):
        raise NpUserError(message)
    return phone

