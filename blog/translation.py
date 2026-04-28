from modeltranslation.translator import TranslationOptions, register

from .models import Article, News


@register(Article)
class ArticleTranslationOptions(TranslationOptions):
    fields = ('title', 'content', 'excerpt', 'meta_title', 'meta_description')


@register(News)
class NewsTranslationOptions(TranslationOptions):
    fields = ('title', 'content', 'excerpt', 'meta_title', 'meta_description')
