from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin

from .models import Article, News


@admin.register(Article)
class ArticleAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title_uk', 'title_en', 'title_ru')
    prepopulated_fields = {'slug': ('title_uk',)}
    list_editable = ('is_published',)


@admin.register(News)
class NewsAdmin(TabbedTranslationAdmin):
    list_display = ('title', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title_uk', 'title_en', 'title_ru')
    prepopulated_fields = {'slug': ('title_uk',)}
    list_editable = ('is_published',)
