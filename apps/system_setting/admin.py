from django import forms
from django.contrib import admin
from django.utils.html import format_html
from urllib.parse import quote
from unfold.admin import ModelAdmin
from .models import (
    AboutSystem, DynamicPages, SMTPSetting, SocialMedia, SystemColor,
    LandingPageHero, LandingPagePricing, LandingPageFeature, LandingPageBadge,
    DashboardSettings, LandingPageSection, LandingPreviewSample,
    LandingTestimonial, LandingCheckoutBrand, ContactUs
)
@admin.register(AboutSystem)

class AboutSystemAdmin(ModelAdmin):
    list_display = ("id", "name", "title", "email", "contact_phone", "contact_notification_email", "copyright", "description",)
    search_fields = ("id", "name", "title", "email", "contact_phone", "office_address", "contact_notification_email", "copyright", "description",)
    list_display_links = ("id", "name", "title", "email", "contact_phone", "contact_notification_email", "copyright", "description",)
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "title", "description")
        }),
        ("Contact Details", {
            "fields": ("email", "contact_phone", "office_address", "contact_notification_email")
        }),
        ("Branding", {
            "fields": ("logo", "favicon", "copyright")
        }),
    )

    def has_add_permission(self, request):
        return False

    # def preview_logo(self, obj):
    #     if obj.logo:
    #         return format_html(f'<img src="{obj.logo.url}" width="50" height="50" />')
    #     return "No Logo"

    # def preview_favicon(self, obj):
    #     if obj.favicon:
    #         return format_html(f'<img src="{obj.favicon.url}" width="50" height="50" />')
    #     return "No Favicon"

@admin.register(DynamicPages)
class DynamicPagesAdmin(ModelAdmin):
    list_display = ("id", "title", "status",)
    search_fields = ("id", "title", "content",)
    list_display_links = ("id", "title", "status",)

@admin.register(SMTPSetting)
class SMTPSettingAdmin(ModelAdmin):
  

    list_display = ("id", "host", "port", "username", "encryption", "sender_name", "sender_email", "is_active",)
    search_fields = ("id", "host", "username", "sender_name", "sender_email",)
    list_display_links = ("id", "host", "username", "sender_name", "sender_email",)

    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SocialMedia)
class SocialMediaAdmin(ModelAdmin):
    list_display = ("id", "name", "url", "preview_icon",)
    search_fields = ("id", "name", "url", "preview_icon",)
    list_display_links = ("id", "name", "url","preview_icon",)


    def preview_icon(self, obj):
        if obj.icon:
            return format_html(f'<img src="{obj.icon.url}" width="50" height="50" />')
        return "No Icon"
    



class SystemColorForm(forms.ModelForm):
    class Meta:
        model = SystemColor
        fields = '__all__'
        widgets = {
            'code': forms.TextInput(attrs={
                'type': 'color',
                'style': 'width: 670px; height: 100px;'
            })
        }


@admin.register(SystemColor)
class SystemColorAdmin(ModelAdmin):
    form = SystemColorForm
    list_display = ("id", "name", "code", "is_active",)
    search_fields = ("id", "name", "code",)
    list_display_links = ("id", "name", "code",)


# ============================================
# Landing Page Content Admin Interfaces
# ============================================

@admin.register(LandingPageHero)
class LandingPageHeroAdmin(ModelAdmin):
    list_display = ("id", "title", "cta_primary", "cta_secondary", "is_active")
    search_fields = ("title", "subtitle", "cta_primary")
    list_display_links = ("id", "title")
    fieldsets = (
        ("Hero Content", {
            "fields": ("title", "subtitle")
        }),
        ("Call to Action Buttons", {
            "fields": ("cta_primary", "cta_secondary")
        }),
        ("Status", {
            "fields": ("is_active",)
        }),
    )

    def has_add_permission(self, request):
        # Only allow one hero section
        return not LandingPageHero.objects.exists()


@admin.register(LandingPagePricing)
class LandingPagePricingAdmin(ModelAdmin):
    list_display = ("plan_name", "billing_period", "price", "downloads", "is_popular", "order", "is_active")
    list_filter = ("plan_name", "billing_period", "is_popular", "is_active")
    search_fields = ("plan_name",)
    list_display_links = ("plan_name",)
    list_editable = ("order", "is_active", "is_popular")
    fieldsets = (
        ("Plan Details", {
            "fields": ("plan_name", "billing_period", "price")
        }),
        ("Card Text Content", {
            "fields": ("tagline", "features", "footer_text"),
            "description": "Customize card text: tagline (top), features list (middle), footer (bottom)"
        }),
        ("Plan Features", {
            "fields": ("downloads", "save_percent")
        }),
        ("Display", {
            "fields": ("is_popular", "order", "is_active")
        }),
    )
    ordering = ("order",)


@admin.register(LandingPageFeature)
class LandingPageFeatureAdmin(ModelAdmin):
    list_display = ("title", "description", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "description")
    list_display_links = ("title",)
    list_editable = ("order", "is_active")
    fieldsets = (
        ("Feature Content", {
            "fields": ("title", "description")
        }),
        ("Display", {
            "fields": ("order", "is_active")
        }),
    )
    ordering = ("order",)


@admin.register(LandingPageBadge)
class LandingPageBadgeAdmin(ModelAdmin):
    list_display = ("title", "icon", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "icon")
    list_display_links = ("title",)
    list_editable = ("order", "is_active")
    fieldsets = (
        ("Badge Content", {
            "fields": ("title", "icon")
        }),
        ("Display", {
            "fields": ("order", "is_active")
        }),
    )
    ordering = ("order",)


@admin.register(DashboardSettings)
class DashboardSettingsAdmin(ModelAdmin):
    list_display = ("id", "welcome_message", "is_active")
    list_display_links = ("id", "welcome_message")
    fieldsets = (
        ("Welcome Message", {
            "fields": ("welcome_message",)
        }),
        ("Topbar & Identity", {
            "fields": ("search_placeholder", "user_role_label")
        }),
        ("Sidebar", {
            "fields": ("sidebar_menu",)
        }),
        ("Credits", {
            "fields": ("credits_text_template",)
        }),
        ("Features to Show", {
            "fields": ("show_recent_documents", "show_subscription_info", "show_credits_info")
        }),
        ("Settings", {
            "fields": ("max_recent_documents",)
        }),
        ("Status", {
            "fields": ("is_active",)
        }),
    )

    def has_add_permission(self, request):
        # Only allow one dashboard settings record
        return not DashboardSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LandingPageSection)
class LandingPageSectionAdmin(ModelAdmin):
    list_display = (
        "id",
        "page",
        "section_key",
        "title",
        "order",
        "is_active",
    )
    list_filter = ("page", "section_key", "is_active")
    search_fields = ("page", "section_key", "title", "sub_title", "description")
    list_display_links = ("id", "title")
    list_editable = ("order", "is_active")
    fieldsets = (
        ("Section Identity", {
            "fields": ("page", "section_key", "order", "is_active")
        }),
        ("Text Content", {
            "fields": ("title", "sub_title", "description", "short_description")
        }),
        ("Media", {
            "fields": ("image_url", "image", "preview_image_1", "preview_image_2", "preview_image_3", "video_url")
        }),
        ("CTA", {
            "fields": ("button_text", "button_link", "other")
        }),
    )
    ordering = ("order", "id")


@admin.register(LandingPreviewSample)
class LandingPreviewSampleAdmin(ModelAdmin):
    list_display = ("title", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title",)
    list_display_links = ("title",)
    list_editable = ("order", "is_active")
    fieldsets = (
        ("Content", {
            "fields": ("title", "image_url", "image", "video_url")
        }),
        ("Display", {
            "fields": ("order", "is_active")
        }),
    )
    ordering = ("order", "id")


@admin.register(LandingTestimonial)
class LandingTestimonialAdmin(ModelAdmin):
    list_display = ("name", "role", "rating", "order", "is_active")
    list_filter = ("is_active", "rating")
    search_fields = ("name", "role", "comment")
    list_display_links = ("name",)
    list_editable = ("order", "is_active", "rating")
    fieldsets = (
        ("Profile", {
            "fields": ("name", "role", "avatar")
        }),
        ("Feedback", {
            "fields": ("rating", "comment")
        }),
        ("Display", {
            "fields": ("order", "is_active")
        }),
    )
    ordering = ("order", "id")


@admin.register(LandingCheckoutBrand)
class LandingCheckoutBrandAdmin(ModelAdmin):
    list_display = ("name", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    list_display_links = ("name",)
    list_editable = ("order", "is_active")
    fieldsets = (
        ("Brand", {
            "fields": ("name", "logo")
        }),
        ("Display", {
            "fields": ("order", "is_active")
        }),
    )
    ordering = ("order", "id")


@admin.register(ContactUs)
class ContactUsAdmin(ModelAdmin):
    list_display = ("id", "name", "email", "message", "purpose", "status", "created_at", "reply_email")
    list_filter = ("purpose", "status", "created_at")
    search_fields = ("name", "email", "message")
    list_display_links = ("id", "name", "email")
    readonly_fields = ("name", "email", "purpose", "message", "status", "created_at", "updated_at", "reply_email")
    fieldsets = (
        ("Client Contact", {
            "fields": ("name", "email", "purpose", "message", "status", "created_at", "updated_at")
        }),
        ("Reply", {
            "fields": ("reply_email",)
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True

    def reply_email(self, obj):
        subject = quote(f"Re: {obj.get_purpose_display()} request")
        body = quote(f"Hello {obj.name},\n\nThanks for contacting us.\n\n")
        return format_html(
            '<a class="button" href="mailto:{email}?subject={subject}&body={body}">Reply</a>',
            email=obj.email,
            subject=subject,
            body=body,
        )

    reply_email.short_description = "Reply to client"

