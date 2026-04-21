from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
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


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, is_active=True)
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            quantity = 1
    except (ValueError, TypeError):
        quantity = 1
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
    cart = Cart(request)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 1
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
