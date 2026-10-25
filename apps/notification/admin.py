from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import DeviceToken, Notification

# Device Token
@admin.register(DeviceToken)
class DeviceTokenAdmin(ModelAdmin):
    list_display = (
        'id',
        'user',
        'token',
        'device_type',
        'updated_at',
    )
    search_fields = ('token', 'device_type', 'user__email')
    list_filter = ('device_type', 'created_at')
    ordering = ('-created_at',)
    autocomplete_fields = ('user',)
    list_select_related = ('user',)

# Notification
@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = (
        'id',
        'user',
        'title',
        'notification_type',
        'is_read',
        'created_at',
    )
    list_display_links = ('id', 'title')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'body', 'notification_type', 'user__email')
    list_editable = ('is_read',)
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
