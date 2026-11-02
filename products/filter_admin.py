from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render

from core.admin_mixins import LangFilteredFieldsets

from .forms import AddFilterValuesForm
from .models import FilterAttribute, FilterValue


class FilterValueInline(admin.TabularInline):
    model = FilterValue
    extra = 1
    fields = ('name', 'slug', 'position')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('position', 'name')


@admin.register(FilterAttribute)
class FilterAttributeAdmin(LangFilteredFieldsets, admin.ModelAdmin):
    list_display = ('name', 'slug', 'position', 'is_active', 'get_categories')
    list_editable = ('position', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('categories',)
    inlines = [FilterValueInline]
    fieldsets = (
        ('Загальне', {
            'fields': ('slug', 'categories', 'position', 'is_active'),
            'description': (
                'Порожній список категорій — фільтр доступний у каталозі '
                'і в усіх категоріях, де є товари з цими значеннями.'
            ),
        }),
        ('🇺🇦 Українська', {
            'fields': ('name',),
            'classes': ('lang-panel', 'lang-uk'),
        }),
    )

    class Media:
        css = {'all': ('css/admin-previews.css', 'css/admin_lang_panels.css')}
        js = ('js/admin_lang_panels.js',)

    @admin.display(description='Категорії')
    def get_categories(self, obj):
        cats = list(obj.categories.all())
        if not cats:
            return '— всі —'
        return ', '.join(cat.name for cat in cats[:3])


@admin.register(FilterValue)
class FilterValueAdmin(admin.ModelAdmin):
    """Лише для autocomplete. Редагування — в атрибуті фільтра."""

    search_fields = ('name', 'slug', 'attribute__name', 'attribute__slug')
    ordering = ('attribute__position', 'position', 'name')
    list_display = ('name', 'slug', 'attribute', 'position')

    def has_module_permission(self, request):
        return False

    def get_urls(self):
        from django.urls import path
        custom = [
            path(
                'autocomplete/',
                self.admin_site.admin_view(self.autocomplete_view),
                name='products_filtervalue_autocomplete',
            ),
        ]
        return custom + super().get_urls()

    def autocomplete_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        term = (request.GET.get('term') or '').strip()
        queryset, use_distinct = self.get_search_results(
            request, self.get_queryset(request).select_related('attribute'), term,
        )
        if use_distinct:
            queryset = queryset.distinct()
        paginator = self.get_paginator(request, queryset, 20)
        page = paginator.get_page(request.GET.get('page') or 1)
        return JsonResponse({
            'results': [
                {'id': str(obj.pk), 'text': str(obj)}
                for obj in page.object_list
            ],
            'pagination': {'more': page.has_next()},
        })


@admin.action(description='Додати значення фільтра')
def add_filter_values_action(modeladmin, request, queryset):
    if not modeladmin.has_change_permission(request):
        raise PermissionDenied
    selected_ids = list(queryset.values_list('pk', flat=True))
    if request.POST.get('apply'):
        form = AddFilterValuesForm(request.POST)
        if form.is_valid():
            values = list(form.cleaned_data['filter_values'])
            for value in values:
                value.products.add(*selected_ids)
            modeladmin.message_user(
                request,
                f'Значення фільтра додано до {len(selected_ids)} товарів.',
                messages.SUCCESS,
            )
            return redirect('admin:products_product_changelist')
    else:
        form = AddFilterValuesForm()

    context = {
        **modeladmin.admin_site.each_context(request),
        'title': 'Додати значення фільтра',
        'queryset': queryset,
        'selected_ids': selected_ids,
        'form': form,
        'action': 'add_filter_values_action',
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        'opts': modeladmin.model._meta,
    }
    return render(
        request,
        'admin/products/product/add_filter_values.html',
        context,
    )
