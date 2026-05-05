import json
import hashlib
import base64
import ecdsa
import requests
from django.conf import settings
from django.urls import reverse


MONO_API_URL = 'https://api.monobank.ua/api/merchant/invoice/create'
MONO_PUBKEY_URL = 'https://api.monobank.ua/api/merchant/pubkey'

_mono_pubkey_cache = {}


def _get_mono_pubkey():
    if 'key' in _mono_pubkey_cache:
        return _mono_pubkey_cache['key']
    token = settings.MONOBANK_TOKEN
    try:
        resp = requests.get(MONO_PUBKEY_URL, headers={'X-Token': token}, timeout=10)
        if resp.status_code == 200:
            key_data = resp.json().get('key', '')
            pub_key = ecdsa.VerifyingKey.from_pem(key_data)
            _mono_pubkey_cache['key'] = pub_key
            return pub_key
    except Exception:
        pass
    return None


def _verify_mono_signature(x_sign_header, body_bytes):
    pub_key = _get_mono_pubkey()
    if not pub_key:
        return False
    try:
        signature = base64.b64decode(x_sign_header)
        pub_key.verify(
            signature,
            body_bytes,
            hashfunc=hashlib.sha256,
        )
        return True
    except (ecdsa.BadSignatureError, Exception):
        return False


def create_mono_invoice(order, request):
    token = settings.MONOBANK_TOKEN
    if not token:
        return None

    callback_url = request.build_absolute_uri(reverse('mono_webhook'))
    result_url = request.build_absolute_uri(reverse('orders:success', args=[order.id]))

    payload = {
        'amount': int(round(order.total * 100)),
        'ccy': 980,
        'merchantPaymInfo': {
            'reference': str(order.id),
            'destination': f'Замовлення #{order.order_number}',
        },
        'redirectUrl': result_url,
        'webHookUrl': callback_url,
    }

    try:
        resp = requests.post(
            MONO_API_URL,
            json=payload,
            headers={'X-Token': token},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            order.payment_id = data.get('invoiceId', '')
            order.save()
            return data.get('pageUrl')
    except Exception:
        pass

    return None


def process_callback(request):
    x_sign = request.headers.get('X-Sign', '')
    body_bytes = request.body
    if not x_sign or not _verify_mono_signature(x_sign, body_bytes):
        return False

    try:
        data = json.loads(body_bytes)
    except Exception:
        return False

    invoice_id = data.get('invoiceId', '')
    status = data.get('status', '')
    reference = data.get('reference', '')

    if not reference:
        return

    from orders.models import Order
    try:
        order = Order.objects.get(id=int(reference))
    except (Order.DoesNotExist, ValueError):
        return

    order.payment_id = invoice_id

    if status == 'success':
        order.payment_status = 'paid'
    elif status in ('failure', 'expired'):
        order.payment_status = 'failed'

    order.save()
