from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import User, UserProfile, OTP
from django.utils.html import format_html
from django.conf import settings
from unfold.admin import StackedInline


class UserProfileInline(StackedInline):
    model = UserProfile
    extra = 0
    max_num = 1


@admin.register(User)
class CustomAdminClass(ModelAdmin):
    list_display = ('id', 'email', 'role', 'is_staff', 'is_active', 'check_is_superuser', 'preview_user_image', 'created_at')
    list_display_links = ('id', 'email')
    list_filter = ('role', 'is_staff', 'is_active', 'is_superuser', 'is_verified')
    search_fields = ('email', 'user_profile__first_name', 'user_profile__last_name', 'user_profile__phone')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-id',)
    list_select_related = ('user_profile',)
    inlines = [UserProfileInline]
    fieldsets = (
        ('Account', {
            'fields': ('email', 'avatar', 'role')
        }),
        ('Access', {
            'fields': ('is_staff', 'is_active', 'is_verified', 'is_superuser')
        }),
        ('Policy', {
            'fields': ('term_and_condition_accepted', 'privacy_policy_accepted', 'ip_address')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def first_name(self, obj):
        return obj.user_profile.first_name if hasattr(obj, 'user_profile') else ''

    def last_name(self, obj):
        return obj.user_profile.last_name if hasattr(obj, 'user_profile') else ''

    def preview_user_image(self, obj):
        """Display user avatar image in admin list view with proper error handling"""
        # Check if Cloudinary is properly configured
        cloudinary_config = getattr(settings, 'CLOUDINARY_STORAGE', {})
        has_cloudinary = cloudinary_config.get('CLOUD_NAME') or settings.DEBUG is False
        
        # If no avatar or Cloudinary not configured, show placeholder
        if not obj.avatar or not has_cloudinary:
            return format_html(
                '<div style="width: 50px; height: 50px; background: #e0e0e0; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 24px;">👤</div>'
            )
        
        # Try to generate URL safely
        try:
            avatar_url = obj.avatar.url
            # Add cache-busting query param
            if '?' in avatar_url:
                avatar_url = f"{avatar_url}&v={int(obj.updated_at.timestamp())}"
            else:
                avatar_url = f"{avatar_url}?v={int(obj.updated_at.timestamp())}"
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px; border-radius: 4px;" />', 
                avatar_url
            )
        except Exception as e:
            # Fallback to icon if URL generation fails
            return format_html(
                '<div style="width: 50px; height: 50px; background: #ff9800; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 24px; color: white;">⚠️</div>'
            )
    
    preview_user_image.short_description = 'Avatar'
    
    def check_is_superuser(self, obj):
        return 'YES' if obj.is_superuser else 'NO'
    check_is_superuser.short_description = 'Superuser'
    
@admin.register(UserProfile)
class Useruser_profileAdmin(ModelAdmin):
    list_display = ('id', 'user', 'first_name', 'last_name', 'phone', 'dob')
    list_display_links = ('id', 'user', 'first_name', 'last_name')
    search_fields = ('user__email', 'first_name', 'last_name')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    fieldsets = (
        ('Profile', {
            'fields': ('user', 'first_name', 'last_name', 'dob', 'gender', 'accepted_terms')
        }),
        ('Contact', {
            'fields': ('phone', 'address')
        }),
        ('Social Links', {
            'fields': ('linkedin', 'github', 'twitter')
        }),
    )


@admin.register(OTP)
class OTPAdmin(ModelAdmin):
    list_display = ('id', 'user', 'purpose', 'is_verify', 'attempts', 'created_at', 'expires_at')
    list_filter = ('purpose', 'is_verify')
    search_fields = ('user__email', 'purpose')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    date_hierarchy = 'created_at'