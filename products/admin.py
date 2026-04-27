from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.utils.html import format_html

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
    css = {'all': ('css/admin-previews.css',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = 20
    fields = ('preview', 'image', 'alt_text', 'order')
    readonly_fields = ('preview',)

    class Media(AdminPreviewMedia):
        pass

    @admin.display(description='Прев\'ю')
    def preview(self, obj):
        return _image_thumb(obj.image, 'admin-thumb--lg')


class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 0
    max_num = 5
    fields = ('poster_preview', 'video_url', 'video_file', 'poster', 'order')
    readonly_fields = ('poster_preview',)

    class Media(AdminPreviewMedia):
        pass

    @admin.display(description='Постер')
    def poster_preview(self, obj):
        return _image_thumb(obj.poster, 'admin-thumb--lg')


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1
    fields = ('name', 'value', 'order')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('image_thumb', 'name', 'parent', 'order', 'is_active')
    list_display_links = ('image_thumb', 'name')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'parent', 'description', 'image', 'order', 'is_active')}),
        ('SEO', {'fields': ('meta_title', 'meta_description'), 'classes': ('collapse',)}),
    )

    class Media(AdminPreviewMedia):
        pass

    @admin.display(description='Фото')
    def image_thumb(self, obj):
        return _image_thumb(obj.image, 'admin-thumb--sm')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('image_thumb', 'name', 'sku', 'category', 'price',
                    'stock_status', 'badge_obj', 'is_active')
    list_display_links = ('image_thumb', 'name')
    list_editable = ('price', 'stock_status', 'badge_obj', 'is_active')
    list_filter = ('stock_status', 'badge_obj', 'is_active', 'category')
    search_fields = ('name', 'sku', 'sku_manufacturer', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVideoInline, ProductAttributeInline]
    autocomplete_fields = ('badge_obj',)
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'sku', 'sku_manufacturer', 'category')}),
        ('Опис', {'fields': ('description', 'short_description')}),
        ('Ціна та наявність', {'fields': (
            'price', 'old_price', 'discount_percent', 'stock_status',
            'badge_obj', 'badge',
        )}),
        ('Додатково', {'fields': (
            'manufacturer', 'country', 'weight', 'is_active'
        )}),
        ('SEO', {'fields': ('meta_title', 'meta_description'), 'classes': ('collapse',)}),
    )
    save_on_top = True
    change_form_template = 'admin/products/product/change_form.html'

    class Media(AdminPreviewMedia):
        pass

    @admin.display(description='Фото')
    def image_thumb(self, obj):
        first_image = obj.images.first()
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
                limit = ProductImage._meta.get_field
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


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'color', 'order', 'is_active', 'products_count')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active', 'color')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('products')

    @admin.display(description='Товарів')
    def products_count(self, obj):
        return obj.products.count()
