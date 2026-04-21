from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_name', 'product_sku', 'price', 'quantity')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'first_name', 'last_name', 'phone',
        'total', 'payment_method', 'payment_status', 'status', 'created_at'
    )
    list_filter = ('status', 'payment_method', 'payment_status')
    search_fields = ('first_name', 'last_name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemInline]
    list_editable = ('status', 'payment_status')
