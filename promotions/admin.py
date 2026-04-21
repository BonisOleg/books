from django.contrib import admin
from .models import Promotion, UpsellGroup, GiftPickerQuestion, GiftPickerOption


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'start_date', 'end_date', 'is_active', 'is_running')
    list_filter = ('is_active',)
    search_fields = ('title', 'product__name')

    def is_running(self, obj):
        return obj.is_running
    is_running.boolean = True
    is_running.short_description = 'Діє зараз'


@admin.register(UpsellGroup)
class UpsellGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'trigger_product', 'is_active')
    filter_horizontal = ('suggested_products',)


class GiftPickerOptionInline(admin.TabularInline):
    model = GiftPickerOption
    extra = 2
    filter_horizontal = ('categories',)


@admin.register(GiftPickerQuestion)
class GiftPickerQuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    inlines = [GiftPickerOptionInline]
