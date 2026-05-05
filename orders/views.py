from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cart.cart import Cart
from products.models import Product

from .forms import CheckoutForm, OneClickForm
from .models import Order, OrderItem
from .utils import create_account_for_order, send_new_order_notification, send_order_confirmation_email

ORDER_SESSION_KEY = 'allowed_order_ids'


def _allow_order_access(request, order):
    ids = request.session.get(ORDER_SESSION_KEY, [])
    if order.id not in ids:
        ids.append(order.id)
    request.session[ORDER_SESSION_KEY] = ids


def _check_order_access(request, order):
    if request.user.is_authenticated and order.user == request.user:
        return True
    if request.user.is_staff:
        return True
    allowed = request.session.get(ORDER_SESSION_KEY, [])
    return order.id in allowed


def checkout(request):
    cart = Cart(request)
    if cart.total_count == 0:
        return redirect('cart:detail')

    if request.method == 'POST':
        form = CheckoutForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.save(commit=False)
            mode = form.cleaned_data.get('checkout_mode', 'guest')
            if request.user.is_authenticated:
                order.user = request.user
            order.total = cart.total_price
            order.save()

            for item in cart.get_items():
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    product_name=item['product'].name,
                    product_sku=item['product'].sku,
                    price=item['price'],
                    quantity=item['quantity'],
                )

            cart.clear()
            _allow_order_access(request, order)

            send_order_confirmation_email(order, request)
            send_new_order_notification(order)
            if mode == 'register' and not request.user.is_authenticated:
                create_account_for_order(order, request)

            if order.payment_method == 'liqpay':
                return redirect('orders:pay_liqpay', order_id=order.id)
            elif order.payment_method == 'monobank':
                return redirect('orders:pay_mono', order_id=order.id)
            elif order.payment_method in ('cod', 'manager'):
                from .payments.cod_service import process_cod_order
                process_cod_order(order)

            return redirect('orders:success', order_id=order.id)
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'phone': getattr(request.user, 'phone', ''),
                'email': request.user.email,
                'patronymic': getattr(request.user, 'patronymic', ''),
            }
        form = CheckoutForm(initial=initial, user=request.user)

    items = cart.get_items()
    return render(request, 'orders/checkout.html', {
        'form': form,
        'cart_items': items,
        'cart_total': cart.total_price,
        'page_title': 'Оформлення замовлення',
    })


def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not _check_order_access(request, order):
        raise Http404
    return render(request, 'orders/order_success.html', {
        'order': order,
        'page_title': f'Замовлення #{order.order_number}',
    })


def oneclick(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    if request.method == 'POST':
        form = OneClickForm(request.POST)
        if form.is_valid():
            order = Order.objects.create(
                first_name=form.cleaned_data.get('name', ''),
                last_name='',
                phone=form.cleaned_data['phone'],
                payment_method='cod',
                city='',
                warehouse='',
                total=product.price,
                comment='Замовлення в 1 клік — уточнити доставку',
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                product_sku=product.sku,
                price=product.price,
                quantity=1,
            )
            send_new_order_notification(order)
            html = render_to_string('orders/partials/oneclick_success.html', {})
            return HttpResponse(html)
    else:
        form = OneClickForm()
    return render(request, 'orders/partials/oneclick_modal.html', {
        'form': form,
        'product': product,
    })


def pay_liqpay(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not _check_order_access(request, order):
        raise Http404
    from .payments.liqpay_service import create_liqpay_form
    form_html = create_liqpay_form(order, request)
    return render(request, 'orders/pay_liqpay.html', {
        'order': order,
        'liqpay_form': form_html,  # None when keys are not configured
        'page_title': 'Оплата LiqPay',
    })


def pay_mono(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not _check_order_access(request, order):
        raise Http404
    from .payments.monobank_service import create_mono_invoice
    invoice_url = create_mono_invoice(order, request)
    if invoice_url:
        return redirect(invoice_url)
    return redirect('orders:success', order_id=order.id)


@csrf_exempt
@require_POST
def liqpay_callback(request):
    from .payments.liqpay_service import process_callback
    process_callback(request)
    return HttpResponse('OK')


@csrf_exempt
@require_POST
def mono_callback(request):
    from .payments.monobank_service import process_callback
    process_callback(request)
    return HttpResponse('OK')
