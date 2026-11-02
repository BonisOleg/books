from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html

from suppliers.models import Supplier, SupplierSyncRun
from suppliers.services import sync_supplier


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
    fieldsets = (
        ('Постачальник', {'fields': ('name', 'is_active')}),
        ('Фід', {'fields': ('feed_url', 'feed_format')}),
        ('Ціни', {
            'fields': ('price_rule', 'markup_percent', 'rounding', 'update_price'),
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
