from .cart import Cart


def cart_context(request):
    cart = Cart(request)
    return {
        'cart_items_count': cart.total_count,
        'cart_total': cart.total_price,
    }
