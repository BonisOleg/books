import base64
import hashlib
import json
from django.conf import settings
from django.urls import reverse


def create_liqpay_form(order, request):
    public_key = settings.LIQPAY_PUBLIC_KEY
    private_key = settings.LIQPAY_PRIVATE_KEY

    if not public_key or not private_key:
        return None

    callback_url = request.build_absolute_uri(reverse('liqpay_webhook'))
    result_url = request.build_absolute_uri(reverse('orders:success', args=[order.id]))

    params = {
        'version': '3',
        'public_key': public_key,
        'action': 'pay',
        'amount': str(order.total),
        'currency': 'UAH',
        'description': f'Замовлення #{order.order_number}',
        'order_id': str(order.id),
        'server_url': callback_url,
        'result_url': result_url,
        'language': 'uk',
    }

    data = base64.b64encode(json.dumps(params).encode()).decode()
    sign_string = private_key + data + private_key
    signature = base64.b64encode(hashlib.sha1(sign_string.encode()).digest()).decode()

    return (
        f'<form method="POST" action="https://www.liqpay.ua/api/3/checkout" accept-charset="utf-8">'
        f'<input type="hidden" name="data" value="{data}">'
        f'<input type="hidden" name="signature" value="{signature}">'
        f'<button type="submit" class="btn btn--buy btn--block">Оплатити через LiqPay</button>'
        f'</form>'
    )


def process_callback(request):
    private_key = settings.LIQPAY_PRIVATE_KEY
    data = request.POST.get('data', '')
    signature = request.POST.get('signature', '')

    sign_string = private_key + data + private_key
    expected_sign = base64.b64encode(hashlib.sha1(sign_string.encode()).digest()).decode()

    if signature != expected_sign:
        return

    try:
        decoded = json.loads(base64.b64decode(data).decode())
    except Exception:
        return

    order_id = decoded.get('order_id')
    status = decoded.get('status')

    if not order_id:
        return

    from orders.models import Order
    try:
        order = Order.objects.get(id=int(order_id))
    except Order.DoesNotExist:
        return

    order.payment_id = str(decoded.get('payment_id', ''))

    if status in ('success', 'sandbox'):
        order.payment_status = 'paid'
    elif status in ('failure', 'error'):
        order.payment_status = 'failed'

    order.save()
