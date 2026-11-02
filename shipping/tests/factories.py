import json
from decimal import Decimal

import requests

from orders.models import Order
from shipping.models import NPTTNSettings, ShipmentOrigin

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'np-ttn-tests',
    }
}


def json_response(payload, status_code=200):
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode()
    return response


def ttn_api_success(number='20450123456789', ref='ref-ttn', cost='68.00', warnings=None):
    return {
        'success': True,
        'data': [{
            'IntDocNumber': number,
            'Ref': ref,
            'CostOnSite': cost,
        }],
        'errors': [],
        'warnings': warnings or [],
        'errorCodes': [],
    }


def origin(**kwargs):
    data = {
        'name': 'Київ №1',
        'kind': ShipmentOrigin.KIND_WAREHOUSE,
        'city_name': 'Київ',
        'city_ref': 'city-ref',
        'warehouse_name': '№1',
        'warehouse_ref': 'sender-wh',
        'is_active': True,
        'is_default': False,
    }
    data.update(kwargs)
    return ShipmentOrigin.objects.create(**data)


def ttn_settings(**kwargs):
    data = {
        'default_weight': Decimal('0.500'),
        'length': 20,
        'width': 15,
        'height': 10,
        'payer_type': 'Recipient',
        'cargo_description': 'Книги',
        'cargo_type': 'Parcel',
        'payment_method': 'Cash',
        'auto_create_ttn': False,
        'cod_mode': NPTTNSettings.COD_AFTERPAYMENT,
        'cod_payer_type': 'Recipient',
        'sender_ref': 'sender-ref',
        'contact_sender_ref': 'contact-ref',
        'sender_phone': '+380671112233',
        'sender_type': 'Organization',
    }
    data.update(kwargs)
    current = NPTTNSettings.objects.first()
    if current is None:
        return NPTTNSettings.objects.create(**data)
    for key, value in data.items():
        setattr(current, key, value)
    current.save()
    return current


def order(**kwargs):
    data = {
        'first_name': 'Іван',
        'last_name': 'Петренко',
        'patronymic': 'Іванович',
        'phone': '+380501112233',
        'city': 'Київ',
        'warehouse': 'Поштомат №12',
        'warehouse_ref': 'recip-wh',
        'payment_method': 'cod',
        'payment_status': 'pending',
        'total': Decimal('150.00'),
    }
    data.update(kwargs)
    return Order.objects.create(**data)
