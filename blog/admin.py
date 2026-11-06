from django.contrib import admin
from django.utils import timezone
from modeltranslation.admin import TranslationAdmin

from core.admin_mixins import LangFilteredFieldsets

from .models import Article, News


class LangPanelMedia:
    css = {'all': ('css/admin_lang_panels.css',)}
    js = ('js/admin_lang_panels.js',)


class PublishStatusMixin:
    @admin.display(description='Статус')
    def publish_status(self, obj):
        if not obj.is_published:
            return 'Чернетка'
        if obj.published_at > timezone.now():
            return 'Заплановано'
        return 'Опубліковано'


@admin.register(Article)
class ArticleAdmin(PublishStatusMixin, LangFilteredFieldsets, TranslationAdmin):
    list_display = ('title', 'publish_status', 'is_published', 'published_at', 'created_at')
    list_filter = ('is_published', 'published_at')
    search_fields = ('title_uk', 'title_en', 'title_ru')
    prepopulated_fields = {'slug': ('title_uk',)}
    list_editable = ('is_published',)
    fieldsets = (
        ('Загальне', {'fields': ('slug', 'image', 'cover_link', 'is_published', 'published_at')}),
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
class NewsAdmin(PublishStatusMixin, LangFilteredFieldsets, TranslationAdmin):
    list_display = ('title', 'publish_status', 'is_published', 'published_at', 'created_at')
    list_filter = ('is_published', 'published_at')
    search_fields = ('title_uk', 'title_en', 'title_ru')
    prepopulated_fields = {'slug': ('title_uk',)}
    list_editable = ('is_published',)
    fieldsets = (
        ('Загальне', {'fields': ('slug', 'image', 'cover_link', 'is_published', 'published_at')}),
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
