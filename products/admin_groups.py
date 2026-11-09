from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from core.admin_mixins import LangFilteredFieldsets

from .models import ProductGroup


@admin.register(ProductGroup)
class ProductGroupAdmin(LangFilteredFieldsets, TranslationAdmin):
    list_display = (
        'name', 'slug', 'order', 'show_in_header', 'show_in_top_menu',
        'top_menu_order', 'auto_source', 'is_active',
        'date_from', 'date_to',
    )
    list_display_links = ('name',)
    list_editable = ('order', 'show_in_header', 'show_in_top_menu', 'top_menu_order')
    list_filter = ('is_active', 'show_in_header', 'show_in_top_menu', 'auto_source')
    search_fields = ('name_uk', 'name_en', 'name_ru', 'slug')
    prepopulated_fields = {'slug': ('name_uk',)}
    autocomplete_fields = ('products',)
    fieldsets = (
        ('Загальне', {
            'fields': (
                'slug', 'products', 'auto_source',
                'show_in_header', 'show_in_top_menu', 'top_menu_order',
                'order', 'is_active',
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
