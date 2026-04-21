from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'display_name', 'rating', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating')
    list_editable = ('is_approved',)
    search_fields = ('text', 'author_name', 'product__name')
    readonly_fields = ('created_at',)
