from modeltranslation.translator import TranslationOptions, register

from .models import FAQ, Banner, Page, ProfileCabinetTexts, SEOTemplate, SiteSettings


@register(SiteSettings)
class SiteSettingsTranslationOptions(TranslationOptions):
    fields = ('site_description', 'promo_banner_text', 'seo_home_title', 'seo_home_description',
              'default_order_info')


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


@register(ProfileCabinetTexts)
class ProfileCabinetTextsTranslationOptions(TranslationOptions):
    fields = (
        'page_title', 'section_personal', 'label_last_name', 'label_first_name',
        'label_patronymic', 'label_phone', 'label_email', 'email_placeholder',
        'button_save', 'section_orders', 'table_number', 'table_date',
        'table_amount', 'table_status', 'table_payment', 'message_saved',
    )
