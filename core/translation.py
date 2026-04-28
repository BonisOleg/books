from modeltranslation.translator import TranslationOptions, register

from .models import FAQ, Banner, Page, SEOTemplate, SiteSettings


@register(SiteSettings)
class SiteSettingsTranslationOptions(TranslationOptions):
    fields = ('site_description', 'promo_banner_text', 'seo_home_title', 'seo_home_description')


@register(FAQ)
class FAQTranslationOptions(TranslationOptions):
    fields = ('question', 'answer')


@register(Banner)
class BannerTranslationOptions(TranslationOptions):
    fields = ('alt_text',)


@register(Page)
class PageTranslationOptions(TranslationOptions):
    fields = ('title', 'content', 'meta_title', 'meta_description')


@register(SEOTemplate)
class SEOTemplateTranslationOptions(TranslationOptions):
    fields = ('meta_title_template', 'meta_description_template')
