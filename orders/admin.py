from django.contrib import admin
from django.utils.html import format_html

from .models import Order, OrderItem


def _order_item_product_value(obj, attr):
    if obj is None or not getattr(obj, 'product_id', None):
        return '—'
    product = getattr(obj, 'product', None)
    if product is None:
        return '—'
    value = getattr(product, attr, None)
    if value is None or value == '':
        return '—'
    return value


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = (
        'image_preview', 'product', 'product_name', 'product_sku',
        'product_article', 'product_manufacturer_code', 'product_manufacturer',
        'price', 'quantity',
    )
    readonly_fields = (
        'image_preview', 'product', 'product_name', 'product_sku',
        'product_article', 'product_manufacturer_code', 'product_manufacturer',
        'price', 'quantity',
    )

    class Media:
        css = {'all': ('css/admin-previews.css',)}

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')

    @admin.display(description='Артикул')
    def product_article(self, obj):
        return _order_item_product_value(obj, 'sku')

    @admin.display(description='Код виробника', ordering='sku_manufacturer')
    def product_manufacturer_code(self, obj):
        return _order_item_product_value(obj, 'sku_manufacturer')

    @admin.display(description='Виробник')
    def product_manufacturer(self, obj):
        return _order_item_product_value(obj, 'manufacturer')

    @admin.display(description='Фото')
    def image_preview(self, obj):
        if obj is None or not getattr(obj, 'product_id', None) or not obj.product:
            return format_html('<span class="admin-thumb-empty">—</span>')
        first_image = obj.product.images.first()
        if not first_image:
            return format_html('<span class="admin-thumb-empty">—</span>')
        return format_html(
            '<img src="{}" class="admin-thumb admin-thumb--sm" alt="">',
            first_image.image.url,
        )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'first_name', 'last_name', 'phone', 'items_count',
        'total', 'payment_method', 'payment_status', 'status',
        'keycrm_order_id', 'created_at',
    )
    list_filter = ('status', 'payment_method', 'payment_status')
    search_fields = ('first_name', 'last_name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at', 'keycrm_order_id', 'keycrm_payment_id')
    inlines = [OrderItemInline]
    list_editable = ('status', 'payment_status')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('items__product')

    @admin.display(description='Позицій')
    def items_count(self, obj):
        return obj.items.count()
