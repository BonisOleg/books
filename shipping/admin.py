import re

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import path, reverse

from . import novaposhta_api
from .models import NPTTNSettings, ShipmentOrigin

_UUID_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)


def _clean_ref(value):
    value = (value or '').strip()
    if not _UUID_RE.fullmatch(value):
        return ''
    return value


@admin.register(ShipmentOrigin)
class ShipmentOriginAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'city_name', 'warehouse_name', 'is_active', 'is_default')
    list_filter = ('kind', 'is_active', 'is_default')
    search_fields = ('name', 'city_name', 'warehouse_name', 'street_name')
    change_form_template = 'admin/shipping/shipmentorigin/change_form.html'
    fieldsets = (
        ('Основне', {'fields': ('name', 'kind', 'is_active', 'is_default')}),
        ('Місто', {
            'fields': ('city_name', 'city_ref'),
            'description': 'Кнопка «Знайти місто» біля поля шукає в Новій Пошті. '
                           'Ref можна також заповнити командою fill_origin_refs.',
        }),
        ('Відділення', {'fields': ('warehouse_name', 'warehouse_ref')}),
        ('Адресний забір', {'fields': ('street_name', 'street_ref', 'building')}),
    )

    class Media:
        css = {'all': ('css/admin-shipment-origin.css',)}
        js = ('js/admin-shipment-origin.js',)

    def get_urls(self):
        custom = [
            path(
                'lookup/cities/',
                self.admin_site.admin_view(self.cities_view),
                name='shipping_shipmentorigin_city_search',
            ),
            path(
                'lookup/warehouses/',
                self.admin_site.admin_view(self.warehouses_view),
                name='shipping_shipmentorigin_warehouse_search',
            ),
            path(
                'lookup/streets/',
                self.admin_site.admin_view(self.streets_view),
                name='shipping_shipmentorigin_street_search',
            ),
        ]
        return custom + super().get_urls()

    def _allowed(self, request):
        return self.has_view_permission(request) or self.has_change_permission(request)

    def cities_view(self, request):
        if not self._allowed(request):
            return JsonResponse({'error': 'Немає доступу'}, status=403)
        query = (request.GET.get('q') or '').strip()[:100]
        if len(query) < 2:
            return JsonResponse({'results': []})
        try:
            results = novaposhta_api.search_cities(query)
        except Exception:
            return JsonResponse({'results': [], 'error': 'НП не відповідає'})
        return JsonResponse({'results': results})

    def warehouses_view(self, request):
        if not self._allowed(request):
            return JsonResponse({'error': 'Немає доступу'}, status=403)
        city_ref = _clean_ref(request.GET.get('city_ref'))
        if not city_ref:
            return JsonResponse({'results': [], 'error': 'Спочатку оберіть місто'})
        query = (request.GET.get('q') or '').strip()[:100]
        try:
            rows = novaposhta_api.search_warehouses(city_ref, query)
        except Exception:
            return JsonResponse({'results': [], 'error': 'НП не відповідає'})
        results = [
            {'ref': row.get('ref') or '', 'name': row.get('description') or '', 'number': row.get('number') or ''}
            for row in rows
        ]
        return JsonResponse({'results': results})

    def streets_view(self, request):
        if not self._allowed(request):
            return JsonResponse({'error': 'Немає доступу'}, status=403)
        settlement_ref = _clean_ref(request.GET.get('settlement_ref'))
        if not settlement_ref:
            return JsonResponse({'results': [], 'error': 'Спочатку оберіть місто'})
        query = (request.GET.get('q') or '').strip()[:100]
        try:
            results = novaposhta_api.search_streets(settlement_ref, query)
        except Exception:
            return JsonResponse({'results': [], 'error': 'НП не відповідає'})
        return JsonResponse({'results': results})


@admin.register(NPTTNSettings)
class NPTTNSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Відправлення', {
            'fields': (
                'default_weight', 'length', 'width', 'height',
                'cargo_description', 'cargo_type',
            ),
        }),
        ('Оплата доставки', {
            'fields': ('payer_type', 'payment_method', 'cod_mode', 'cod_payer_type'),
        }),
        ('Відправник', {
            'fields': ('sender_type', 'sender_ref', 'contact_sender_ref', 'sender_phone'),
        }),
        ('Автостворення', {'fields': ('auto_create_ttn',)}),
    )

    def has_add_permission(self, request):
        if NPTTNSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        obj = NPTTNSettings.objects.first()
        if obj:
            return redirect(reverse('admin:shipping_npttnsettings_change', args=[obj.pk]))
        return redirect(reverse('admin:shipping_npttnsettings_add'))
