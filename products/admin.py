from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from .forms import BulkImageUploadForm
from .models import (
    Badge,
    Category,
    Product,
    ProductAttribute,
    ProductImage,
    ProductVideo,
)


def _image_thumb(image_field, size_class=''):
    if not image_field:
        return format_html('<span class="admin-thumb-empty">—</span>')
    classes = 'admin-thumb'
    if size_class:
        classes += ' ' + size_class
    return format_html(
        '<img src="{}" class="{}" alt="">',
        image_field.url, classes,
    )


class AdminPreviewMedia:
    css = {'all': ('css/admin-previews.css', 'css/admin_lang_panels.css')}
    js = ('js/admin_lang_panels.js',)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = 20
    fields = ('preview', 'image', 'alt_text', 'order')
    readonly_fields = ('preview',)

    class Media:
        css = {'all': ('css/admin-previews.css',)}

    @admin.display(description='Прев\'ю')
    def preview(self, obj):
        return _image_thumb(obj.image, 'admin-thumb--lg')


class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 0
    max_num = 5
    fields = ('poster_preview', 'video_url', 'video_file', 'poster', 'order')
    readonly_fields = ('poster_preview',)

    class Media:
        css = {'all': ('css/admin-previews.css',)}

    @admin.display(description='Постер')
    def poster_preview(self, obj):
        return _image_thumb(obj.poster, 'admin-thumb--lg')


class ProductAttributeInline(TranslationTabularInline):
    model = ProductAttribute
    extra = 1
    fields = ('name_uk', 'name_en', 'name_ru', 'value_uk', 'value_en', 'value_ru', 'order')


@admin.register(Category)
class CategoryAdmin(TranslationAdmin):
    list_display = ('image_thumb', 'name', 'parent', 'order', 'is_active')
    list_display_links = ('image_thumb', 'name')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name_uk', 'name_en', 'name_ru')
    prepopulated_fields = {'slug': ('name_uk',)}
    fieldsets = (
        ('Загальне', {
            'fields': ('slug', 'parent', 'image', 'order', 'is_active'),
        }),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': ('name_uk', 'description_uk', 'meta_title_uk', 'meta_description_uk'),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('name_en', 'description_en', 'meta_title_en', 'meta_description_en'),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('name_ru', 'description_ru', 'meta_title_ru', 'meta_description_ru'),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(AdminPreviewMedia):
        pass

    @admin.display(description='Фото')
    def image_thumb(self, obj):
        return _image_thumb(obj.image, 'admin-thumb--sm')


@admin.register(Product)
class ProductAdmin(TranslationAdmin):
    actions = ['set_sale_end_date_action', 'clear_sale_end_date_action']
    list_display = ('image_thumb', 'name', 'sku', 'get_categories', 'price',
                    'stock_status', 'badge_obj', 'is_active')
    list_display_links = ('image_thumb', 'name')
    list_editable = ('price', 'stock_status', 'badge_obj', 'is_active')
    list_filter = ('stock_status', 'badge_obj', 'is_active', 'categories')
    search_fields = ('name_uk', 'name_en', 'name_ru', 'sku', 'sku_manufacturer')
    prepopulated_fields = {'slug': ('name_uk',)}
    inlines = [ProductImageInline, ProductVideoInline, ProductAttributeInline]
    autocomplete_fields = ('badge_obj',)
    filter_horizontal = ('categories',)
    fieldsets = (

        ('Ідентифікація', {
            'fields': ('slug', 'sku', 'sku_manufacturer', 'categories'),
        }),
        ('Ціна та наявність', {
            'fields': (
                'price', 'old_price', 'discount_percent', 'stock_status',
                'badge_obj', 'badge', 'sale_end_date',
            ),
        }),
        ('Додатково', {
            'fields': ('manufacturer', 'country', 'weight', 'is_active'),
        }),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': (
                'name_uk', 'description_uk', 'short_description_uk',
                'meta_title_uk', 'meta_description_uk',
            ),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': (
                'name_en', 'description_en', 'short_description_en',
                'meta_title_en', 'meta_description_en',
            ),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': (
                'name_ru', 'description_ru', 'short_description_ru',
                'meta_title_ru', 'meta_description_ru',
            ),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )
    save_on_top = True
    change_form_template = 'admin/products/product/change_form.html'

    class Media(AdminPreviewMedia):
        pass

    # ── Fixes ────────────────────────────────────────────────────────────────

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Decimal fields with USE_L10N=True (uk locale) use comma as decimal
        separator. Without localize=True Django's DecimalField rejects comma
        values submitted from <input type="number">, causing silent save failures."""
        if db_field.name in ('price', 'old_price'):
            kwargs['localize'] = True
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_changelist_form(self, request, **kwargs):
        """AutocompleteSelect widget (from autocomplete_fields) does not
        initialize correctly inside list_editable formset rows — badge_obj
        never submits a value, so it always saves as empty.
        Use the plain ModelChoiceField/Select in the changelist context only;
        the change-form keeps the autocomplete widget via autocomplete_fields."""
        _orig = self.autocomplete_fields
        self.autocomplete_fields = ()
        try:
            form = super().get_changelist_form(request, **kwargs)
        finally:
            self.autocomplete_fields = _orig
        return form

    def get_queryset(self, request):
        """Prefetch images and categories to avoid N+1 queries in changelist."""
        return super().get_queryset(request).prefetch_related('images', 'categories')

    def save_formset(self, request, form, formset, change):
        """Catch storage / upload errors in the video inline so they surface
        as admin messages instead of an unhandled 500.  All other inlines use
        the default implementation unchanged."""
        if formset.model is not ProductVideo:
            super().save_formset(request, form, formset, change)
            return

        sid = transaction.savepoint()
        try:
            super().save_formset(request, form, formset, change)
            transaction.savepoint_commit(sid)
        except Exception as exc:
            transaction.savepoint_rollback(sid)
            self.message_user(
                request,
                f'Відео не збережено: {exc}. '
                'Перевірте формат файлу, розмір або налаштування Cloudinary.',
                level=messages.ERROR,
            )

    # ── Column helpers ───────────────────────────────────────────────────────

    @admin.display(description='Категорії')
    def get_categories(self, obj):
        names = [c.name for c in obj.categories.all()]
        return ', '.join(names) if names else '—'

    @admin.display(description='Фото')
    def image_thumb(self, obj):
        first_image = next(iter(obj.images.all()), None)
        if not first_image:
            return format_html('<span class="admin-thumb-empty">—</span>')
        return _image_thumb(first_image.image, 'admin-thumb--sm')

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:object_id>/upload-images/',
                self.admin_site.admin_view(self.bulk_upload_view),
                name='products_product_bulk_upload',
            ),
        ]
        return custom + urls

    def bulk_upload_view(self, request, object_id):
        product = get_object_or_404(Product, pk=object_id)

        if request.method == 'POST':
            form = BulkImageUploadForm(request.POST, request.FILES)
            files = request.FILES.getlist('images')
            if files:
                existing = ProductImage.objects.filter(product=product).count()
                created = 0
                next_order = (
                    ProductImage.objects.filter(product=product)
                    .order_by('-order').values_list('order', flat=True).first() or 0
                )
                for f in files:
                    if existing + created >= 20:
                        messages.warning(
                            request, 'Досягнуто ліміту 20 фото на товар. Завантажено лише частину.'
                        )
                        break
                    next_order += 1
                    ProductImage.objects.create(
                        product=product, image=f, order=next_order
                    )
                    created += 1
                if created:
                    messages.success(
                        request, f'Завантажено {created} фото для «{product.name}».'
                    )
                return redirect('admin:products_product_change', object_id)
            else:
                messages.error(request, 'Не вибрано жодного файлу.')
        else:
            form = BulkImageUploadForm()

        context = {
            **self.admin_site.each_context(request),
            'title': f'Масове завантаження фото — {product.name}',
            'product': product,
            'form': form,
            'opts': self.model._meta,
            'has_change_permission': True,
        }
        return render(request, 'admin/products/product/bulk_upload.html', context)

    # ── Sale end date bulk actions ────────────────────────────────────────────

    @admin.action(description='⏱ Встановити таймер акції (масово)')
    def set_sale_end_date_action(self, request, queryset):
        selected_ids = list(queryset.values_list('id', flat=True))
        if 'apply' in request.POST:
            raw = request.POST.get('sale_end_date', '').strip()
            if raw:
                from django.utils.dateparse import parse_datetime
                dt = parse_datetime(raw)
                if dt and timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                if dt:
                    queryset.update(sale_end_date=dt)
                    self.message_user(
                        request,
                        f'Таймер акції встановлено для {queryset.count()} товарів.',
                        messages.SUCCESS,
                    )
                    return redirect('admin:products_product_changelist')
            self.message_user(request, 'Вкажіть коректну дату та час.', messages.ERROR)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Встановити таймер акції',
            'queryset': queryset,
            'selected_ids': selected_ids,
            'action': 'set_sale_end_date_action',
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
        }
        return render(request, 'admin/products/product/set_sale_end_date.html', context)

    @admin.action(description='✖ Зняти таймер акції (масово)')
    def clear_sale_end_date_action(self, request, queryset):
        updated = queryset.update(sale_end_date=None)
        self.message_user(
            request,
            f'Таймер знято з {updated} товарів.',
            messages.SUCCESS,
        )


@admin.register(Badge)
class BadgeAdmin(TranslationAdmin):
    list_display = ('name', 'slug', 'color', 'order', 'is_active', 'products_count')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active', 'color')
    search_fields = ('name_uk', 'name_en', 'name_ru', 'slug')
    prepopulated_fields = {'slug': ('name_uk',)}
    fieldsets = (
        ('Загальне', {'fields': ('slug', 'color', 'order', 'is_active')}),
        # ── Language panels ──────────────────────────────────────────────
        ('🇺🇦 Українська', {
            'fields': ('name_uk',),
            'classes': ('lang-panel', 'lang-uk'),
        }),
        ('🇬🇧 English', {
            'fields': ('name_en',),
            'classes': ('lang-panel', 'lang-en'),
        }),
        ('🇷🇺 Русский', {
            'fields': ('name_ru',),
            'classes': ('lang-panel', 'lang-ru'),
        }),
    )

    class Media(AdminPreviewMedia):
        pass

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('products')

    @admin.display(description='Товарів')
    def products_count(self, obj):
        return obj.products.count()
