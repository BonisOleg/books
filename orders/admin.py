from django.contrib import admin
from django.utils.html import format_html

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('image_preview', 'product', 'product_name', 'product_sku', 'price', 'quantity')
    readonly_fields = ('image_preview', 'product', 'product_name', 'product_sku', 'price', 'quantity')

    class Media:
        css = {'all': ('css/admin-previews.css',)}

    @admin.display(description='Фото')
    def image_preview(self, obj):
        if not obj.product:
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
        'total', 'payment_method', 'payment_status', 'status', 'created_at',
    )
    list_filter = ('status', 'payment_method', 'payment_status')
    search_fields = ('first_name', 'last_name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemInline]
    list_editable = ('status', 'payment_status')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('items')

    @admin.display(description='Позицій')
    def items_count(self, obj):
        return obj.items.count()
