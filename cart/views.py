from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.ratelimit import is_rate_limited
from products.models import Product

from .cart import Cart


def cart_detail(request):
    cart = Cart(request)
    items = cart.get_items()
    return render(request, 'cart/cart.html', {
        'cart_items': items,
        'cart_total': cart.total_price,
        'cart_count': cart.total_count,
        'page_title': 'Кошик',
    })


def _abuse_limited(request, action, ip_setting, session_setting):
    ip_limit, ip_period = getattr(settings, ip_setting)
    session_limit, session_period = getattr(settings, session_setting)
    return is_rate_limited(
        request,
        action,
        ip_limit=ip_limit,
        ip_period=ip_period,
        session_limit=session_limit,
        session_period=session_period,
    )


def _rate_limited_response():
    response = HttpResponse('Too many requests', status=429, content_type='text/plain')
    response['HX-Reswap'] = 'none'
    return response


def _parse_quantity(raw, *, default=1, minimum=1, maximum=None):
    try:
        quantity = int(raw)
    except (ValueError, TypeError):
        quantity = default
    if quantity < minimum:
        quantity = minimum
    if maximum is not None:
        quantity = min(quantity, maximum)
    return quantity


@require_POST
def cart_add(request, product_id):
    if _abuse_limited(request, 'cart_add', 'ABUSE_CART_ADD_IP', 'ABUSE_CART_ADD_SESSION'):
        return _rate_limited_response()

    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, is_active=True)
    max_qty = getattr(settings, 'CART_ADD_MAX_QUANTITY', 20)
    quantity = _parse_quantity(
        request.POST.get('quantity', 1),
        default=1,
        maximum=max_qty,
    )
    cart.add(product, quantity)
    return HttpResponse(str(cart.total_count))


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    cart.remove(product_id)
    if request.headers.get('HX-Request'):
        items = cart.get_items()
        return render(request, 'cart/partials/cart_items.html', {
            'cart_items': items,
            'cart_total': cart.total_price,
            'cart_count': cart.total_count,
        })
    return redirect('cart:detail')


@require_POST
def cart_update(request, product_id):
    if _abuse_limited(
        request, 'cart_update', 'ABUSE_CART_UPDATE_IP', 'ABUSE_CART_UPDATE_SESSION',
    ):
        return _rate_limited_response()

    cart = Cart(request)
    quantity = _parse_quantity(request.POST.get('quantity', 1), default=1, minimum=0)
    cart.update_quantity(product_id, quantity)
    if request.headers.get('HX-Request'):
        items = cart.get_items()
        return render(request, 'cart/partials/cart_items.html', {
            'cart_items': items,
            'cart_total': cart.total_price,
            'cart_count': cart.total_count,
        })
    return redirect('cart:detail')


def mini_cart(request):
    cart = Cart(request)
    items = cart.get_items()
    return render(request, 'cart/partials/mini_cart.html', {
        'cart_items': items,
        'cart_total': cart.total_price,
    })
