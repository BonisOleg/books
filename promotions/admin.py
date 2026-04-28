from django.contrib import admin
from django.utils.html import format_html
from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline

from .models import GiftPickerOption, GiftPickerQuestion, Promotion, UpsellGroup


@admin.register(Promotion)
class PromotionAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'product', 'start_date', 'end_date', 'is_active', 'is_running_display')
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    date_hierarchy = 'end_date'
    search_fields = ('title_uk', 'title_en', 'title_ru', 'product__name_uk')

    def is_running_display(self, obj):
        if obj.is_running:
            return format_html('<span style="color:#2e7d32;font-weight:600;">&#10003; Діє</span>')
        return format_html('<span style="color:#c62828;">&#10005; Не діє</span>')
    is_running_display.short_description = 'Статус'


@admin.register(UpsellGroup)
class UpsellGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'trigger_product', 'is_active')
    filter_horizontal = ('suggested_products',)


class GiftPickerOptionInline(TranslationTabularInline):
    model = GiftPickerOption
    extra = 2
    fields = ('text_uk', 'text_en', 'text_ru', 'categories', 'price_min', 'price_max')
    filter_horizontal = ('categories',)


@admin.register(GiftPickerQuestion)
class GiftPickerQuestionAdmin(TabbedTranslationAdmin):
    list_display = ('text', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('text_uk', 'text_en', 'text_ru')
    inlines = [GiftPickerOptionInline]
