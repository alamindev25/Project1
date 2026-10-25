from django.contrib import admin
from django.core.cache import cache
from apps.cms.models import CMS, FAQ, CMSPoint, Page
from unfold.admin import ModelAdmin, TabularInline

# Register your models here.

class CMSPointInline(TabularInline):
    model = CMSPoint
    extra = 1 #
    fields = ("text", "order")


@admin.register(Page)
class CustomAdminClass(ModelAdmin):
    list_display = ("id", "title", "type", "status", "slug", "image")
    list_display_links = ("id", "title")
    list_filter = ("type", "status")
    search_fields = ("title", "slug", "content")
    list_editable = ("status",)
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        (None, {
            "fields": ("title", "slug", "type", "status", "image")
        }),
        ("Content", {
            "fields": ("content",)
        }),
    )

@admin.register(CMS)
class CMSAdmin(ModelAdmin):
    list_display = ("id", "page", "section", "title", "status")
    list_display_links = ("id", "title")
    list_filter = ("status",)
    search_fields = ("page", "section", "title", "sub_title", "description", "video_link")
    list_editable = ("status",)

    inlines = [CMSPointInline]

    def _section_key(self, request, obj=None):
        section = ""
        if obj and obj.section:
            section = obj.section
        elif request.method == "POST":
            section = request.POST.get("section", "")
        return str(section).strip().lower()

    def _is_preview_section(self, request, obj=None):
        return self._section_key(request, obj) == "preview_samples"

    def _is_watch_video_section(self, request, obj=None):
        return self._section_key(request, obj) == "watch_video"

    def get_fieldsets(self, request, obj=None):
        base_fieldsets = [
            (None, {
                "fields": ("page", "section", "title", "status")
            }),
            ("Content", {
                "fields": ("sub_title", "description", "short_description")
            }),
        ]

        if self._is_watch_video_section(request, obj):
            base_fieldsets.append(
                ("Video", {
                    "fields": ("video_link", "video_thumbnail"),
                    "description": "Upload video URL and optional thumbnail image to display in the video section."
                })
            )
        else:
            base_fieldsets.append(
                ("Media & CTA", {
                    "fields": ("background_image", "file_url", "button_text", "button_link", "other")
                })
            )

        if self._is_preview_section(request, obj):
            base_fieldsets.append(
                ("Preview Samples (3 Images)", {
                    "fields": ("preview_image_1", "preview_image_2", "preview_image_3"),
                    "description": "This section appears only for section=preview_samples."
                })
            )

        return tuple(base_fieldsets)

    def _clear_landing_cache(self):
        try:
            cache.delete_many([
                "landing_page_data",
                "landing_page_data_v8",
                "landing_page_data_v9",
                "landing_page_data_v10",
                "landing_page_data_v11",
                "landing_page_data_v12",
                "landing_page_data_v13",
            ])
        except Exception:
            pass

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._clear_landing_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self._clear_landing_cache()

@admin.register(FAQ)
class FAQAdmin(ModelAdmin):
    list_display = ("id", "question", "status")
    list_display_links = ("id", "question")
    list_filter = ("status",)
    search_fields = ("question", "answer")
    list_editable = ("status",)

    fieldsets = (
        (None, {
            "fields": ("question", "status")
        }),
        ("Answer", {
            "fields": ("answer",)
        }),
    )


@admin.register(CMSPoint)
class CMSPointAdmin(ModelAdmin):
    list_display = ("id", "cms", "text", "order")
    list_display_links = ("id", "text")
    list_filter = ("cms",)
    search_fields = ("text",)
    list_editable = ("order",)