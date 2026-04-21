from decimal import Decimal
from django.conf import settings
from products.models import Product

CART_SESSION_KEY = 'cart'


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if not cart:
            cart = self.session[CART_SESSION_KEY] = {}
        self.cart = cart

    def add(self, product, quantity=1):
        product_id = str(product.id)
        if product_id not in self.cart:
            self.cart[product_id] = {
                'quantity': 0,
                'price': str(product.price),
            }
        self.cart[product_id]['quantity'] += quantity
        self.save()

    def remove(self, product_id):
        product_id = str(product_id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def update_quantity(self, product_id, quantity):
        product_id = str(product_id)
        if product_id in self.cart:
            if quantity <= 0:
                self.remove(product_id)
            else:
                self.cart[product_id]['quantity'] = quantity
                self.save()

    def save(self):
        self.session.modified = True

    def clear(self):
        self.session.pop(CART_SESSION_KEY, None)
        self.cart = {}
        self.save()

    def get_items(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids).prefetch_related('images')
        items = []
        changed = False
        for product in products:
            pid = str(product.id)
            cart_data = self.cart[pid]
            quantity = cart_data['quantity']
            current_price = product.price
            if str(current_price) != cart_data['price']:
                cart_data['price'] = str(current_price)
                changed = True
            price = current_price
            items.append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'total': price * quantity,
            })
        if changed:
            self.save()
        return items

    @property
    def total_count(self):
        return sum(item['quantity'] for item in self.cart.values())

    @property
    def total_price(self):
        return sum(
            Decimal(item['price']) * item['quantity']
            for item in self.cart.values()
        )

    def __len__(self):
        return self.total_count
