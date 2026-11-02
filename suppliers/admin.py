from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from products.models import Product

from suppliers.models import PendingPriceChange, Supplier, SupplierProduct, SupplierSyncRun
from suppliers.report import format_percent, money
from suppliers.services import sync_supplier


class SupplierProductInline(admin.TabularInline):
    model = SupplierProduct
    extra = 0
    can_delete = False
    show_change_link = True
    ordering = ('-linked_at',)
    fields = (
        'product', 'feed_code', 'ignored', 'marked_out_by_sync',
        'linked_at', 'last_seen_at',
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    change_form_template = 'admin/suppliers/supplier/change_form.html'
    list_display = (
        'name', 'feed_format', 'price_rule', 'markup_percent',
        'rounding', 'update_price', 'is_active', 'updated_at',
    )
    list_filter = ('is_active', 'feed_format', 'price_rule', 'rounding')
    search_fields = ('name', 'feed_url')
    readonly_fields = ('created_at', 'updated_at')
    actions = ('dry_run_selected', 'sync_selected')
    inlines = (SupplierProductInline,)
    fieldsets = (
        ('Постачальник', {'fields': ('name', 'is_active')}),
        ('Фід', {'fields': ('feed_url', 'feed_format')}),
        ('Ціни', {
            'fields': (
                'price_rule', 'markup_percent', 'rounding',
                'update_price', 'max_price_change_percent',
            ),
        }),
        ('Наявність', {'fields': ('mark_missing_out_of_stock',)}),
        ('Службове', {'fields': ('created_at', 'updated_at')}),
    )

    class Media:
        css = {'all': ('css/admin_supplier_sync.css',)}

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:object_id>/dry-run/',
                self.admin_site.admin_view(self.dry_run_view),
                name='suppliers_supplier_dry_run',
            ),
            path(
                '<int:object_id>/sync/',
                self.admin_site.admin_view(self.sync_view),
                name='suppliers_supplier_sync',
            ),
        ]
        return custom + urls

    def dry_run_view(self, request, object_id):
        return self._sync_view(request, object_id, dry_run=True)

    def sync_view(self, request, object_id):
        return self._sync_view(request, object_id, dry_run=False)

    def _sync_view(self, request, object_id, *, dry_run):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        self._require_change(request)
        supplier = self.get_object(request, str(object_id))
        if supplier is None:
            raise Http404('Постачальника не знайдено')
        run = sync_supplier(supplier, dry_run=dry_run)
        self._notify(request, run, dry_run=dry_run)
        return redirect('admin:suppliers_suppliersyncrun_change', run.pk)

    @admin.action(description='Перевірити вибраних (dry-run)')
    def dry_run_selected(self, request, queryset):
        self._sync_queryset(request, queryset, dry_run=True)

    @admin.action(description='Запустити синхронізацію')
    def sync_selected(self, request, queryset):
        self._sync_queryset(request, queryset, dry_run=False)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm('suppliers.change_supplier'):
            actions.pop('dry_run_selected', None)
            actions.pop('sync_selected', None)
        return actions

    def _sync_queryset(self, request, queryset, *, dry_run):
        self._require_change(request)
        bits = []
        failed = False
        for supplier in queryset.order_by('pk'):
            run = sync_supplier(supplier, dry_run=dry_run)
            failed = failed or run.status != SupplierSyncRun.Status.OK
            bits.append(f'{supplier.name}: {run.get_status_display()} (#{run.pk})')
        self.message_user(
            request,
            '; '.join(bits) or 'Нічого не вибрано.',
            level=messages.ERROR if failed else messages.SUCCESS,
        )

    def _require_change(self, request):
        if not request.user.is_staff or not request.user.has_perm('suppliers.change_supplier'):
            raise PermissionDenied

    def _notify(self, request, run, *, dry_run):
        if run.status == SupplierSyncRun.Status.FAILED:
            self.message_user(
                request,
                'Синхронізацію не застосовано. Див. звіт.',
                level=messages.ERROR,
            )
            return
        if dry_run:
            self.message_user(
                request,
                'Пробний запуск виконано. Каталог не змінено.',
                level=messages.SUCCESS,
            )
            return
        self.message_user(request, 'Синхронізацію застосовано.', level=messages.SUCCESS)


@admin.register(SupplierSyncRun)
class SupplierSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        'supplier', 'status', 'dry_run', 'started_at', 'finished_at',
        'items_in_feed', 'matched', 'price_changed', 'not_in_feed',
        'not_in_catalog', 'marked_out', 'errors',
    )
    list_filter = ('status', 'dry_run', 'supplier')
    search_fields = ('supplier__name',)
    date_hierarchy = 'started_at'
    ordering = ('-started_at',)
    list_select_related = ('supplier',)
    fieldsets = (
        ('Запуск', {
            'fields': ('supplier', 'status', 'dry_run', 'started_at', 'finished_at'),
        }),
        ('Підсумки', {
            'fields': (
                'items_in_feed', 'matched', 'price_changed', 'not_in_feed',
                'not_in_catalog', 'marked_out', 'errors',
            ),
        }),
        ('Звіт', {'fields': ('report_pre',)}),
        ('JSON', {'fields': ('report_json',), 'classes': ('collapse',)}),
    )
    readonly_fields = (
        'supplier', 'status', 'dry_run', 'started_at', 'finished_at',
        'items_in_feed', 'matched', 'price_changed', 'not_in_feed',
        'not_in_catalog', 'marked_out', 'errors', 'report_json', 'report_pre',
    )

    class Media:
        css = {'all': ('css/admin_supplier_sync.css',)}

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        if request.user.has_perm('suppliers.change_supplier'):
            return True
        return super().has_view_permission(request, obj)

    @admin.display(description='Звіт')
    def report_pre(self, obj):
        if obj is None or not obj.report:
            return '—'
        return format_html('<pre class="supplier-sync-report">{}</pre>', obj.report)


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'supplier', 'feed_code', 'ignored',
        'marked_out_by_sync', 'linked_at', 'last_seen_at',
    )
    list_filter = ('ignored', 'marked_out_by_sync', 'supplier')
    search_fields = (
        'feed_code',
        'product__name',
        'product__sku',
        'product__sku_manufacturer',
        'supplier__name',
    )
    list_select_related = ('product', 'supplier')
    autocomplete_fields = ('product', 'supplier')
    fields = (
        'product', 'supplier', 'feed_code', 'ignored',
        'marked_out_by_sync', 'linked_at', 'last_seen_at',
    )

    def get_readonly_fields(self, request, obj=None):
        locked = ['marked_out_by_sync', 'linked_at', 'last_seen_at']
        if obj is not None:
            locked.insert(0, 'product')
        return locked


@admin.register(PendingPriceChange)
class PendingPriceChangeAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'supplier', 'old_price_uah', 'new_price_uah',
        'percent_display', 'status', 'created_at',
    )
    list_filter = ('status', 'supplier')
    search_fields = (
        'product__name',
        'product__sku',
        'product__sku_manufacturer',
        'supplier__name',
    )
    list_select_related = ('product', 'supplier', 'resolved_by')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ('apply_pending', 'ignore_product')
    readonly_fields = (
        'supplier', 'product', 'run', 'old_price_uah', 'new_price_uah',
        'percent_display', 'status', 'created_at', 'resolved_at', 'resolved_by',
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    @admin.display(description='Стара ціна')
    def old_price_uah(self, obj):
        return money(obj.old_price)

    @admin.display(description='Нова ціна')
    def new_price_uah(self, obj):
        return money(obj.new_price)

    @admin.display(description='Відхилення')
    def percent_display(self, obj):
        return format_percent(obj.percent)

    @admin.action(description='Застосувати', permissions=['change'])
    def apply_pending(self, request, queryset):
        applied, errors = _settle(queryset, lambda item: _apply_one(request, item))
        _tell(self, request, applied, errors, f'Застосовано змін цін: {applied}.')

    @admin.action(description='Ігнорувати цей товар', permissions=['change'])
    def ignore_product(self, request, queryset):
        applied, errors = _settle(queryset, lambda item: _ignore_one(request, item))
        _tell(self, request, applied, errors, f'Ігноровано товарів: {applied}.')


def _tell(model_admin, request, applied, errors, success):
    if errors:
        model_admin.message_user(request, ' '.join(errors), level=messages.ERROR)
    if applied:
        model_admin.message_user(request, success, level=messages.SUCCESS)


def _settle(queryset, action):
    applied = 0
    errors = []
    for item in queryset.order_by('pk'):
        error = action(item)
        if error:
            errors.append(error)
        else:
            applied += 1
    return applied, errors


def _apply_one(request, item) -> str | None:
    if item.status != PendingPriceChange.Status.PENDING:
        return f'«{item.product}»: зміну вже вирішено, не застосовано.'
    with transaction.atomic():
        pending = _locked(PendingPriceChange.objects.filter(pk=item.pk)).get()
        if pending.status != PendingPriceChange.Status.PENDING:
            return f'«{pending.product}»: зміну вже вирішено, не застосовано.'
        product = _locked(Product.objects.filter(pk=pending.product_id)).get()
        if product.price != pending.old_price:
            return (
                f'«{product.name}»: ціна зараз {money(product.price)}, '
                f'очікувалась {money(pending.old_price)}. Зміну не застосовано.'
            )
        now = timezone.now()
        product.price = pending.new_price
        product.updated_at = now
        product.save(update_fields=['price', 'updated_at'])
        pending.status = PendingPriceChange.Status.APPLIED
        pending.resolved_at = now
        pending.resolved_by = request.user
        pending.save(update_fields=['status', 'resolved_at', 'resolved_by'])
    return None


def _ignore_one(request, item) -> str | None:
    if item.status != PendingPriceChange.Status.PENDING:
        return f'«{item.product}»: зміну вже вирішено.'
    with transaction.atomic():
        pending = _locked(
            PendingPriceChange.objects.select_related('supplier').filter(pk=item.pk)
        ).get()
        if pending.status != PendingPriceChange.Status.PENDING:
            return f'«{pending.product}»: зміну вже вирішено.'
        now = timezone.now()
        pending.status = PendingPriceChange.Status.IGNORED
        pending.resolved_at = now
        pending.resolved_by = request.user
        pending.save(update_fields=['status', 'resolved_at', 'resolved_by'])
        link = _locked(
            SupplierProduct.objects.filter(product_id=pending.product_id)
        ).first()
        if link is None:
            SupplierProduct.objects.create(
                supplier=pending.supplier,
                product_id=pending.product_id,
                feed_code='',
                ignored=True,
                linked_at=now,
                last_seen_at=now,
            )
        elif not link.ignored:
            link.ignored = True
            link.save(update_fields=['ignored'])
    return None


def _locked(queryset):
    if connection.features.has_select_for_update:
        return queryset.select_for_update()
    return queryset
