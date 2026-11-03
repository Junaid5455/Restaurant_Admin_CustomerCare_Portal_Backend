from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'customer', 'rating', 'is_visible', 'created_at')
    list_filter = ('rating', 'is_visible', 'restaurant')
    search_fields = ('comment', 'owner_reply', 'customer__email', 'restaurant__name')
