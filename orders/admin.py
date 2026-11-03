from urllib.parse import quote

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html

from shipping.np_ttn import create_ttn, online_payment_needs_confirm

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
    change_form_template = 'admin/orders/order/change_form.html'
    actions = ('create_ttn_for_selected',)
    list_display = (
        'id', 'first_name', 'last_name', 'phone', 'items_count',
        'total', 'payment_method', 'payment_status', 'status',
        'ttn_tracking', 'ttn_status', 'ttn_error_short',
        'keycrm_order_id', 'created_at',
    )
    list_filter = ('status', 'payment_method', 'payment_status', 'ttn_status')
    search_fields = ('first_name', 'last_name', 'phone', 'email', 'ttn_number')
    readonly_fields = (
        'created_at', 'updated_at', 'keycrm_order_id', 'keycrm_payment_id',
        'ttn_number', 'ttn_ref', 'ttn_status', 'ttn_error',
        'ttn_created_at', 'ttn_delivery_cost',
    )
    autocomplete_fields = ('shipment_origin',)
    inlines = [OrderItemInline]
    list_editable = ('status', 'payment_status')
    fieldsets = (
        ('Покупець', {'fields': (
            'user', 'first_name', 'last_name', 'patronymic', 'phone', 'email',
        )}),
        ('Доставка', {'fields': (
            'city', 'city_ref', 'warehouse', 'warehouse_ref',
            'recipient_area', 'recipient_street', 'recipient_house', 'recipient_flat',
            'comment',
        )}),
        ('Оплата', {'fields': (
            'payment_method', 'payment_status', 'payment_id', 'total', 'status',
        )}),
        ('Нова Пошта ТТН', {'fields': (
            'shipment_origin', 'parcel_weight', 'parcel_length', 'parcel_width', 'parcel_height',
            'ttn_number', 'ttn_ref', 'ttn_status', 'ttn_error',
            'ttn_created_at', 'ttn_delivery_cost',
        )}),
        ('KeyCRM', {'fields': ('keycrm_order_id', 'keycrm_payment_id')}),
        ('Аналітика', {
            'classes': ('collapse',),
            'fields': (
                'gclid', 'gbraid', 'wbraid',
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            ),
        }),
        ('Службове', {'fields': ('created_at', 'updated_at')}),
    )

    class Media:
        css = {'all': ('css/admin-np-ttn.css', 'css/admin-previews.css')}

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('items__product').select_related('shipment_origin')

    def get_urls(self):
        custom = [
            path(
                '<int:order_id>/create-ttn/',
                self.admin_site.admin_view(self.create_ttn_view),
                name='orders_order_create_ttn',
            ),
        ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        if (
            request.method == 'POST'
            and 'create_ttn_for_selected' in request.POST.getlist('action')
            and not self.has_change_permission(request)
        ):
            raise PermissionDenied
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['ttn_needs_payment_confirm'] = request.GET.get('ttn_confirm') == '1'
        return super().change_view(request, object_id, form_url, extra_context)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.get_internal_type() == 'DecimalField':
            kwargs['localize'] = True
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def create_ttn_view(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id)
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied
        if not self.has_change_permission(request, order):
            raise PermissionDenied
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        change_url = reverse('admin:orders_order_change', args=[order.pk])
        if online_payment_needs_confirm(order) and request.POST.get('confirm') != '1':
            messages.warning(
                request,
                'Онлайн-оплата ще не підтверджена. '
                'Натисніть «Підтвердити створення ТТН», щоб створити накладну.',
            )
            return redirect(f'{change_url}?ttn_confirm=1')
        existed = (order.ttn_number or '').strip()
        result = create_ttn(order.pk)
        if result is None:
            messages.error(request, 'Не вдалося створити ТТН.')
        elif existed and result.ttn_number == existed:
            messages.info(request, f'ТТН вже існує: {result.ttn_number}.')
        elif result.ttn_number and result.ttn_status == 'created':
            messages.success(request, f'ТТН {result.ttn_number} створено.')
        else:
            messages.error(request, f'Не вдалося створити ТТН: {result.ttn_error}')
        return redirect(change_url)

    @admin.action(permissions=['change'], description='Створити ТТН для вибраних')
    def create_ttn_for_selected(self, request, queryset):
        if not self.has_change_permission(request):
            raise PermissionDenied
        created = 0
        existed = 0
        failed = 0
        skipped = []
        for order in queryset:
            if online_payment_needs_confirm(order):
                skipped.append(str(order.pk))
                continue
            had_number = bool((order.ttn_number or '').strip())
            result = create_ttn(order.pk)
            if result is None or not (result.ttn_number or '').strip():
                failed += 1
                continue
            if had_number:
                existed += 1
            else:
                created += 1
        if created or existed or failed:
            level = messages.SUCCESS if created and not failed else messages.INFO
            self.message_user(
                request,
                f'Створено ТТН: {created}. Вже існували: {existed}. З помилкою: {failed}.',
                level=level,
            )
        if skipped:
            joined = ', '.join(f'#{pk}' for pk in skipped)
            self.message_user(
                request,
                'Пропущено без підтвердження (онлайн-оплата не отримана): '
                f'{joined}. Відкрийте замовлення і підтвердьте створення ТТН.',
                level=messages.WARNING,
            )

    @admin.display(description='Позицій')
    def items_count(self, obj):
        return len(obj.items.all())

    @admin.display(description='ТТН')
    def ttn_tracking(self, obj):
        number = (obj.ttn_number or '').strip()
        if not number:
            return '—'
        url = f'https://novaposhta.ua/tracking/?cargo_number={quote(number)}'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            url,
            number,
        )

    @admin.display(description='Помилка ТТН')
    def ttn_error_short(self, obj):
        text = (obj.ttn_error or '').strip()
        if not text:
            return '—'
        if len(text) > 80:
            return f'{text[:80]}…'
        return text
