from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.admin import TabularInline
from .models import (
	SignatureAudit,
	TemplateCategory,
	DocumentType,
	DocumentTemplate,
	DocumentStructure,
	DocumentSchema,
	GeneratedDocument,
	DocumentFeedback,
	CreditWallet,
	PaymentMethod,
	CompanyBranding,
	HelpArticle,
	DocumentRequest,
)


class DocumentTypeInline(TabularInline):
	model = DocumentType
	extra = 0
	fields = ("name", "slug", "sort_order", "is_active")
	show_change_link = True


class DocumentTemplateInline(TabularInline):
	model = DocumentTemplate
	extra = 0
	fields = ("name", "slug", "is_active", "usage_count")
	show_change_link = True


@admin.register(TemplateCategory)
class TemplateCategoryAdmin(ModelAdmin):
	list_display = ("id", "name", "display_template_count", "is_active", "is_recommended", "is_popular", "sort_order")
	list_filter = ("is_active", "is_recommended", "is_popular")
	search_fields = ("name", "slug")
	list_editable = ("is_active", "is_recommended", "is_popular", "sort_order")
	inlines = [DocumentTypeInline]
	ordering = ("sort_order", "name")

	@admin.display(description="Template count")
	def display_template_count(self, obj):
		return obj.document_types.count()


@admin.register(DocumentType)
class DocumentTypeAdmin(ModelAdmin):
	list_display = ("id", "name", "category", "template_total", "is_active", "sort_order")
	list_filter = ("is_active", "category")
	search_fields = ("name", "slug", "description", "category__name")
	list_editable = ("sort_order", "is_active")
	inlines = [DocumentTemplateInline]
	autocomplete_fields = ("category",)
	ordering = ("sort_order", "name")
	
	fieldsets = (
		("Basic Info", {
			"fields": ("category", "name", "slug", "description", "is_active", "sort_order")
		}),
		("Document Schema", {
			"fields": ("schema_definition",),
			"description": "Define the unique input fields for this document type. Use JSON placeholders that match field names or labels."
		}),
	)

	@admin.display(description="Templates")
	def template_total(self, obj):
		return obj.templates.count()


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(ModelAdmin):
	list_display = ("id", "name", "document_type", "category_name", "is_active", "usage_count", "updated_at")
	list_filter = ("is_active", "document_type")
	search_fields = ("name", "slug", "description", "document_type__name", "document_type__category__name")
	autocomplete_fields = ("document_type",)
	readonly_fields = ("updated_at", "usage_count")
	ordering = ("name",)
	fieldsets = (
		("Basic Info", {
			"fields": ("document_type", "name", "slug", "description", "preview_image", "is_active")
		}),
		("Action Controls", {
			"fields": ("action_mode",),
			"description": "Choose which action buttons users can use for this template after generation."
		}),
		("Template Body", {
			"fields": ("content_template", "base_content"),
			"description": "Write the actual document body here. Use placeholders like [Client Name] or [Start Date]."
		}),
		("Stats", {
			"fields": ("usage_count", "updated_at"),
			"classes": ("collapse",)
		}),
	)

	@admin.display(description="Category")
	def category_name(self, obj):
		return obj.document_type.category.name


@admin.register(DocumentStructure)
class DocumentStructureAdmin(ModelAdmin):
	list_display = ("id", "name", "structure_type", "is_active", "usage_count", "logo_position")
	list_filter = ("is_active", "structure_type", "has_signature_section")
	search_fields = ("name", "slug", "description")
	list_editable = ("is_active",)
	ordering = ("structure_type", "name")
	fieldsets = (
		("Basic Info", {
			"fields": ("structure_type", "name", "slug", "description", "is_active")
		}),
		("Structure Features", {
			"fields": (
				"has_header", "has_footer", "has_page_numbers", 
				"has_signature_section", "has_date_field"
			)
		}),
		("Layout & Margins (mm)", {
			"fields": (
				"header_height_mm", "footer_height_mm",
				"left_margin_mm", "right_margin_mm", "top_margin_mm", "bottom_margin_mm",
				"line_spacing"
			)
		}),
		("Branding & Logo", {
			"fields": ("logo_width_mm", "logo_position")
		}),
		("Stats", {
			"fields": ("usage_count",),
			"classes": ("collapse",)
		}),
	)

@admin.register(DocumentSchema)
class DocumentSchemaAdmin(ModelAdmin):
	list_display = ("id", "structure", "updated_at")
	search_fields = ("structure__name", "structure__slug")
	list_select_related = ("structure",)
	autocomplete_fields = ("structure",)
	readonly_fields = ("created_at", "updated_at")
	fieldsets = (
		("Schema Configuration", {
			"fields": ("structure", "fields_definition"),
			"description": "Legacy reusable structure schema. The primary client-facing schema now lives on Document Types."
		}),
		("Timestamps", {
			"fields": ("created_at", "updated_at"),
			"classes": ("collapse",)
		}),
	)


@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(ModelAdmin):
	list_display = ("id", "name", "user_email", "status", "credit_used", "generated_at")
	list_filter = ("status", "category", "document_type", "structure")
	search_fields = ("name", "user__email", "template__name", "document_type__name")
	readonly_fields = ("generated_at", "previewed_at", "downloaded_at", "created_at", "updated_at", "input_fingerprint")
	list_select_related = ("user", "category", "document_type", "template", "structure")
	autocomplete_fields = ("user", "category", "document_type", "template", "structure")
	date_hierarchy = "generated_at"
	fieldsets = (
		("Document", {
			"fields": ("user", "name", "status", "credit_used", "generated_at")
		}),
		("Template Data", {
			"fields": ("category", "document_type", "template", "structure")
		}),
		("Content", {
			"fields": ("form_data", "rendered_content", "input_fingerprint")
		}),
		("Tracking", {
			"fields": ("previewed_at", "downloaded_at", "created_at", "updated_at"),
			"classes": ("collapse",)
		}),
	)

	@admin.display(description="User")
	def user_email(self, obj):
		return obj.user.email


@admin.register(DocumentFeedback)
class DocumentFeedbackAdmin(ModelAdmin):
	list_display = ("id", "document", "user", "rating", "is_public", "created_at")
	list_filter = ("is_public", "rating")
	search_fields = ("document__name", "user__email", "comment")
	readonly_fields = ("created_at", "updated_at")
	list_select_related = ("document", "user")
	autocomplete_fields = ("document", "user")
	date_hierarchy = "created_at"


@admin.register(PaymentMethod)
class PaymentMethodAdmin(ModelAdmin):
	list_display = ("id", "user", "provider", "card_brand", "card_last4", "expires", "is_default", "updated_at")
	list_filter = ("provider", "is_default")
	search_fields = ("user__email", "card_last4", "card_brand")
	list_select_related = ("user",)
	autocomplete_fields = ("user",)
	readonly_fields = ("updated_at",)

	@admin.display(description="Expires")
	def expires(self, obj):
		return f"{obj.exp_month:02d}/{obj.exp_year}"


@admin.register(CompanyBranding)
class CompanyBrandingAdmin(ModelAdmin):
	list_display = ("id", "user", "company_name", "phone", "logo_preview", "updated_at")
	search_fields = ("user__email", "company_name", "phone", "address")
	list_select_related = ("user",)
	autocomplete_fields = ("user",)
	readonly_fields = ("updated_at", "logo_preview")
	fieldsets = (
		("Company", {
			"fields": ("user", "company_name", "address", "phone")
		}),
		("Logo", {
			"fields": ("logo", "logo_preview")
		}),
	)

	@admin.display(description="Logo")
	def logo_preview(self, obj):
		if obj.logo:
			return format_html('<img src="{}" style="max-height: 48px; max-width: 96px; border-radius: 4px;" />', obj.logo.url)
		return "-"

@admin.register(HelpArticle)
class HelpArticleAdmin(ModelAdmin):
	list_display = ("id", "title", "section", "is_popular", "is_active", "sort_order")
	list_filter = ("section", "is_popular", "is_active")
	search_fields = ("title", "slug", "short_description", "content")
	list_editable = ("sort_order", "is_popular", "is_active")
	ordering = ("section", "sort_order", "title")


@admin.register(DocumentRequest)
class DocumentRequestAdmin(ModelAdmin):
	list_display = ("id", "document_name", "user", "category", "status", "request_count", "created_at")
	list_filter = ("status", "category")
	search_fields = ("document_name", "user__email", "category__name")
	list_select_related = ("user", "category")
	autocomplete_fields = ("user", "category")
	date_hierarchy = "created_at"
	list_editable = ("status", "request_count")
    
@admin.register(SignatureAudit)
class SignatureAuditAdmin(admin.ModelAdmin):
	list_display = ("id", "signature_request", "action", "actor", "created_at")
	list_filter = ("action",)
	search_fields = ("actor", "signature_request__recipient_email",)
	readonly_fields = ("created_at", "updated_at", "metadata")
