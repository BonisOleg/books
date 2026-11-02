from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from core.admin_mixins import LangFilteredFieldsets

from .models import ProductGroup


@admin.register(ProductGroup)
class ProductGroupAdmin(LangFilteredFieldsets, TranslationAdmin):
    list_display = (
        'name', 'slug', 'order', 'show_in_header', 'is_active', 'date_from', 'date_to',
    )
    list_display_links = ('name',)
    list_editable = ('order', 'show_in_header')
    list_filter = ('is_active', 'show_in_header')
    search_fields = ('name_uk', 'name_en', 'name_ru', 'slug')
    prepopulated_fields = {'slug': ('name_uk',)}
    autocomplete_fields = ('products',)
    fieldsets = (
        ('Загальне', {
            'fields': (
                'slug', 'products', 'show_in_header', 'order', 'is_active',
                'date_from', 'date_to',
            ),
        }),
        ('🇺🇦 Українська', {
            'fields': ('name_uk', 'meta_title_uk', 'meta_description_uk'),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('name_en', 'meta_title_en', 'meta_description_en'),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('name_ru', 'meta_title_ru', 'meta_description_ru'),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media:
        css = {'all': ('css/admin-previews.css', 'css/admin_lang_panels.css')}
        js = ('js/admin_lang_panels.js',)
