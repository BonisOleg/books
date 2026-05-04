from django.contrib import admin
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin

from .admin_mixins import LangFilteredFieldsets
from .models import FAQ, Banner, Page, ProfileCabinetTexts, SEOTemplate, SiteSettings


class LangPanelMedia:
    css = {'all': ('css/admin_lang_panels.css',)}
    js = ('js/admin_lang_panels.js',)


@admin.register(SiteSettings)
class SiteSettingsAdmin(LangFilteredFieldsets, TranslationAdmin):
    fieldsets = (
        ('Основне', {'fields': ('site_name', 'logo', 'favicon')}),
        ('Контакти', {
            'fields': ('email', 'address', 'phone_1', 'phone_2', 'phone_3',
                       'contact_person', 'work_schedule'),
        }),
        ('Умови повернення', {'fields': ('return_policy',)}),
        ('Соцмережі', {
            'fields': ('telegram_url', 'viber_url', 'facebook_url',
                       'instagram_url', 'youtube_url', 'tiktok_url'),
        }),
        ('Промо-банер — посилання', {'fields': ('promo_banner_url',)}),
        ('Онлайн-консультант', {
            'fields': ('online_consultant_code',),
            'description': 'Скрипт-код віджета чату (Tawk.to, JivoSite, Crisp тощо). '
                           'Вставляється у кінець &lt;body&gt;.',
        }),
        ('Кольори (тема)', {
            'fields': ('primary_color', 'accent_color', 'bg_color', 'text_color'),
            'description': 'Залиште поля порожніми, якщо не хочете міняти дефолтну палітру.',
        }),
        ('Аналітика та реклама', {
            'fields': (
                'google_tag_manager_id', 'google_analytics_id',
                'google_ads_conversion_id', 'facebook_pixel_id',
            ),
        }),
        ('Мови', {
            'fields': ('enable_ru', 'enable_en'),
            'description': 'Українська завжди увімкнена. '
                           'Тут можна додати додаткові мови для перемикання на сайті.',
        }),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': (
                'site_description_uk', 'promo_banner_text_uk',
                'seo_home_title_uk', 'seo_home_description_uk',
            ),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': (
                'site_description_en', 'promo_banner_text_en',
                'seo_home_title_en', 'seo_home_description_en',
            ),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': (
                'site_description_ru', 'promo_banner_text_ru',
                'seo_home_title_ru', 'seo_home_description_ru',
            ),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(LangPanelMedia):
        pass

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()


_PROFILE_COPY_FIELDS_UK = (
    'page_title_uk', 'section_personal_uk',
    'label_last_name_uk', 'label_first_name_uk', 'label_patronymic_uk',
    'label_phone_uk', 'label_email_uk', 'email_placeholder_uk',
    'button_save_uk', 'section_orders_uk',
    'table_number_uk', 'table_date_uk', 'table_amount_uk', 'table_status_uk',
    'table_payment_uk', 'message_saved_uk',
)
_PROFILE_COPY_FIELDS_EN = tuple(f.replace('_uk', '_en') for f in _PROFILE_COPY_FIELDS_UK)
_PROFILE_COPY_FIELDS_RU = tuple(f.replace('_uk', '_ru') for f in _PROFILE_COPY_FIELDS_UK)


@admin.register(ProfileCabinetTexts)
class ProfileCabinetTextsAdmin(LangFilteredFieldsets, TranslationAdmin):
    """Єдиний запис — тексти /accounts/profile/ (три мови)."""

    fieldsets = (
        ('🇺🇦 Українська', {
            'fields': _PROFILE_COPY_FIELDS_UK,
            'classes': ('lang-panel', 'lang-uk'),
            'description': 'Сторінка особистого кабінету. Порожні значення на сайті '
                           'замінюються стандартними підписами (див. код _FALLBACK).',
        }),
        ('🇬🇧 English', {
            'fields': _PROFILE_COPY_FIELDS_EN,
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': _PROFILE_COPY_FIELDS_RU,
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(LangPanelMedia):
        pass

    def has_add_permission(self, request):
        return not ProfileCabinetTexts.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SEOTemplate)
class SEOTemplateAdmin(LangFilteredFieldsets, TranslationAdmin):
    list_display = ('name', 'meta_title_template')
    fieldsets = (
        (None, {'fields': ('name',)}),
        ('🇺🇦 Українська', {
            'fields': ('meta_title_template_uk', 'meta_description_template_uk'),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('meta_title_template_en', 'meta_description_template_en'),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('meta_title_template_ru', 'meta_description_template_ru'),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(LangPanelMedia):
        pass


@admin.register(Banner)
class BannerAdmin(LangFilteredFieldsets, TranslationAdmin):
    list_display = ('image_thumb', 'title', 'position', 'order', 'is_active',
                    'start_date', 'end_date')
    list_display_links = ('image_thumb', 'title')
    list_editable = ('order', 'is_active')
    list_filter = ('position', 'is_active')
    search_fields = ('title',)
    fieldsets = (
        (None, {'fields': ('title', 'image', 'image_mobile')}),
        ('Посилання', {'fields': ('link', 'open_in_new_tab')}),
        ('Розташування', {'fields': ('position', 'order', 'is_active')}),
        ('Період показу', {'fields': ('start_date', 'end_date')}),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': ('alt_text_uk',),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('alt_text_en',),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('alt_text_ru',),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media:
        css = {'all': ('css/admin-previews.css', 'css/admin_lang_panels.css')}
        js = ('js/admin_lang_panels.js',)

    @admin.display(description='Прев\'ю')
    def image_thumb(self, obj):
        if not obj.image:
            return format_html('<span class="admin-thumb-empty">—</span>')
        return format_html(
            '<img src="{}" class="admin-thumb admin-thumb--sm" alt="">',
            obj.image.url,
        )


@admin.register(Page)
class PageAdmin(LangFilteredFieldsets, TranslationAdmin):
    list_display = ('title', 'slug', 'is_published', 'show_in_footer', 'footer_order', 'updated_at')
    list_editable = ('is_published', 'show_in_footer', 'footer_order')
    list_filter = ('is_published', 'show_in_footer')
    search_fields = ('title_uk', 'title_en', 'title_ru', 'slug')
    prepopulated_fields = {'slug': ('title_uk',)}
    fieldsets = (
        ('Загальне', {'fields': ('slug', 'show_in_footer', 'footer_order', 'is_published')}),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': ('title_uk', 'content_uk', 'meta_title_uk', 'meta_description_uk'),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('title_en', 'content_en', 'meta_title_en', 'meta_description_en'),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('title_ru', 'content_ru', 'meta_title_ru', 'meta_description_ru'),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(LangPanelMedia):
        pass


@admin.register(FAQ)
class FAQAdmin(LangFilteredFieldsets, TranslationAdmin):
    list_display = ('question', 'scope', 'order', 'is_published')
    list_editable = ('scope', 'order', 'is_published')
    list_filter = ('scope', 'is_published')
    search_fields = ('question_uk', 'question_en', 'question_ru')
    fieldsets = (
        ('Загальне', {'fields': ('scope', 'order', 'is_published')}),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': ('question_uk', 'answer_uk'),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('question_en', 'answer_en'),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('question_ru', 'answer_ru'),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(LangPanelMedia):
        pass
