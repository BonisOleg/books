from django.contrib import admin
from django.utils.html import format_html

from .models import Banner, FAQ, Page, SEOTemplate, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Основне', {'fields': ('site_name', 'site_description', 'logo', 'favicon')}),
        ('Контакти', {'fields': ('email', 'address', 'phone_1', 'phone_2', 'phone_3',
                                  'contact_person', 'work_schedule')}),
        ('Умови повернення', {'fields': ('return_policy',)}),
        ('Соцмережі', {'fields': ('telegram_url', 'viber_url', 'facebook_url',
                                   'instagram_url', 'youtube_url', 'tiktok_url')}),
        ('Промо-банер', {'fields': ('promo_banner_text', 'promo_banner_url')}),
        ('SEO головної', {'fields': ('seo_home_title', 'seo_home_description')}),
        ('Онлайн-консультант', {
            'fields': ('online_consultant_code',),
            'description': 'Скрипт-код віджета чату (Tawk.to, JivoSite, Crisp тощо). '
                           'Вставляється у кінець &lt;body&gt;.'
        }),
        ('Кольори (тема)', {
            'fields': ('primary_color', 'accent_color', 'bg_color', 'text_color'),
            'description': 'Залиште поля порожніми, якщо не хочете міняти дефолтну палітру.'
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
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()


@admin.register(SEOTemplate)
class SEOTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'meta_title_template')


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('image_thumb', 'title', 'position', 'order', 'is_active',
                    'start_date', 'end_date')
    list_display_links = ('image_thumb', 'title')
    list_editable = ('order', 'is_active')
    list_filter = ('position', 'is_active')
    search_fields = ('title',)
    fieldsets = (
        (None, {'fields': ('title', 'image', 'image_mobile', 'alt_text')}),
        ('Посилання', {'fields': ('link', 'open_in_new_tab')}),
        ('Розташування', {'fields': ('position', 'order', 'is_active')}),
        ('Період показу', {'fields': ('start_date', 'end_date')}),
    )

    class Media:
        css = {'all': ('css/admin-previews.css',)}

    @admin.display(description='Прев\'ю')
    def image_thumb(self, obj):
        if not obj.image:
            return format_html('<span class="admin-thumb-empty">—</span>')
        return format_html(
            '<img src="{}" class="admin-thumb admin-thumb--sm" alt="">',
            obj.image.url,
        )


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'show_in_footer', 'footer_order', 'updated_at')
    list_editable = ('is_published', 'show_in_footer', 'footer_order')
    list_filter = ('is_published', 'show_in_footer')
    search_fields = ('title', 'slug', 'content')
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'content')}),
        ('Розташування', {'fields': ('show_in_footer', 'footer_order', 'is_published')}),
        ('SEO', {'fields': ('meta_title', 'meta_description'), 'classes': ('collapse',)}),
    )


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'scope', 'order', 'is_published')
    list_editable = ('scope', 'order', 'is_published')
    list_filter = ('scope', 'is_published')
    search_fields = ('question', 'answer')
    fieldsets = (
        (None, {'fields': ('question', 'answer', 'scope', 'order', 'is_published')}),
    )
