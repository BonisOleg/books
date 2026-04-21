from django.contrib import admin
from .models import Category, Product, ProductImage, ProductVideo, ProductAttribute


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    max_num = 20
    fields = ('image', 'alt_text', 'order')


class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 0
    max_num = 5
    fields = ('video_url', 'video_file', 'poster', 'order')


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1
    fields = ('name', 'value', 'order')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'parent', 'description', 'image', 'order', 'is_active')}),
        ('SEO', {'fields': ('meta_title', 'meta_description'), 'classes': ('collapse',)}),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'price', 'stock_status', 'badge', 'is_active')
    list_editable = ('price', 'stock_status', 'badge', 'is_active')
    list_filter = ('stock_status', 'badge', 'is_active', 'category')
    search_fields = ('name', 'sku', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVideoInline, ProductAttributeInline]
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'sku', 'category')}),
        ('Опис', {'fields': ('description', 'short_description')}),
        ('Ціна та наявність', {'fields': (
            'price', 'old_price', 'discount_percent', 'stock_status', 'badge'
        )}),
        ('Додатково', {'fields': (
            'manufacturer', 'country', 'weight', 'condition', 'is_active'
        )}),
        ('SEO', {'fields': ('meta_title', 'meta_description'), 'classes': ('collapse',)}),
    )
    save_on_top = True
