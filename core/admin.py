from django.contrib import admin
from .models import SiteSettings, SEOTemplate


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Основне', {'fields': ('site_name', 'site_description', 'logo', 'favicon')}),
        ('Контакти', {'fields': ('email', 'address', 'phone_1', 'phone_2', 'phone_3',
                                  'contact_person', 'work_schedule')}),
        ('Умови повернення', {'fields': ('return_policy',)}),
        ('Соцмережі', {'fields': ('telegram_url', 'viber_url', 'facebook_url', 'instagram_url')}),
        ('Промо-банер', {'fields': ('promo_banner_text', 'promo_banner_url')}),
        ('SEO головної', {'fields': ('seo_home_title', 'seo_home_description')}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()


@admin.register(SEOTemplate)
class SEOTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'meta_title_template')
