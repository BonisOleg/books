from modeltranslation.translator import TranslationOptions, register

from .models import Badge, Category, FilterGroup, FilterOption, Product, ProductAttribute


@register(Badge)
class BadgeTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'meta_title', 'meta_description')


@register(Product)
class ProductTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'short_description', 'meta_title', 'meta_description')


@register(ProductAttribute)
class ProductAttributeTranslationOptions(TranslationOptions):
    fields = ('name', 'value')


@register(FilterGroup)
class FilterGroupTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(FilterOption)
class FilterOptionTranslationOptions(TranslationOptions):
    fields = ('label',)
