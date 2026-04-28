from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from .models import Article, News


class LangPanelMedia:
    css = {'all': ('css/admin_lang_panels.css',)}
    js = ('js/admin_lang_panels.js',)


@admin.register(Article)
class ArticleAdmin(TranslationAdmin):
    list_display = ('title', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title_uk', 'title_en', 'title_ru')
    prepopulated_fields = {'slug': ('title_uk',)}
    list_editable = ('is_published',)
    fieldsets = (
        ('Загальне', {'fields': ('slug', 'image', 'is_published')}),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': ('title_uk', 'content_uk', 'excerpt_uk',
                       'meta_title_uk', 'meta_description_uk'),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('title_en', 'content_en', 'excerpt_en',
                       'meta_title_en', 'meta_description_en'),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('title_ru', 'content_ru', 'excerpt_ru',
                       'meta_title_ru', 'meta_description_ru'),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(LangPanelMedia):
        pass


@admin.register(News)
class NewsAdmin(TranslationAdmin):
    list_display = ('title', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title_uk', 'title_en', 'title_ru')
    prepopulated_fields = {'slug': ('title_uk',)}
    list_editable = ('is_published',)
    fieldsets = (
        ('Загальне', {'fields': ('slug', 'image', 'is_published')}),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': ('title_uk', 'content_uk', 'excerpt_uk',
                       'meta_title_uk', 'meta_description_uk'),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('title_en', 'content_en', 'excerpt_en',
                       'meta_title_en', 'meta_description_en'),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('title_ru', 'content_ru', 'excerpt_ru',
                       'meta_title_ru', 'meta_description_ru'),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(LangPanelMedia):
        pass
