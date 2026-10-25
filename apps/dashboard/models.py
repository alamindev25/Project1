from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
import uuid
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Max

class TimeStampedModel(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	class Meta:
		abstract = True


class TemplateCategory(TimeStampedModel):
	name = models.CharField(max_length=120)
	slug = models.SlugField(unique=True, blank=True)
	description = models.CharField(max_length=255, blank=True, null=True)
	icon = models.CharField(max_length=120, blank=True, null=True)
	template_count = models.PositiveIntegerField(default=0)
	is_recommended = models.BooleanField(default=False)
	is_popular = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	sort_order = models.PositiveIntegerField(default=1)

	class Meta:
		ordering = ["sort_order", "name"]
		verbose_name = "Template Category"
		verbose_name_plural = "Template Categories"

	# def save(self, *args, **kwargs):
	# 	if not self.slug:
	# 		self.slug = slugify(self.name)
	# 	super().save(*args, **kwargs)

	# def __str__(self):
	# 	return self.name
	
	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)
		if not self.pk:
			max_order = TemplateCategory.objects.aggregate(Max('sort_order'))['sort_order__max']
			self.sort_order = (max_order or 0) + 1

		super().save(*args, **kwargs)

	def __str__(self):
		return self.name


# class DocumentType(TimeStampedModel):
# 	category = models.ForeignKey(
# 		TemplateCategory,
# 		on_delete=models.CASCADE,
# 		related_name="document_types",
# 	)
# 	name = models.CharField(max_length=120)
# 	slug = models.SlugField(blank=True)
# 	description = models.CharField(max_length=255, blank=True, null=True)
# 	schema_definition = models.JSONField(
# 		default=list,
# 		blank=True,
# 		help_text=(
# 			"Array of field objects for this document type. Supported keys: "
# 			"name, label, type, required, order, placeholder, options, section, position, "
# 			"repeatable, min_items, max_items, children, conditions"
# 		),
# 	)
# 	is_active = models.BooleanField(default=True)
# 	sort_order = models.PositiveIntegerField(default=1)

# 	class Meta:
# 		ordering = ["sort_order", "name"]
# 		unique_together = ("category", "slug")

# 	def save(self, *args, **kwargs):
# 		if not self.slug:
# 			self.slug = slugify(self.name)
# 		super().save(*args, **kwargs)

# 	def __str__(self):
# 		return f"{self.category.name} - {self.name}"
	
class DocumentType(TimeStampedModel):
    category = models.ForeignKey(
        TemplateCategory,
        on_delete=models.CASCADE,
        related_name="document_types",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(blank=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    schema_definition = models.JSONField(
		
        default=list,
        blank=True,
        help_text=(
            "Array of field objects for this document type. Supported keys: "
            "name, label, type, is_required, is_visible, order, placeholder, options, section, position, "
            "repeatable, min_items, max_items, children, conditions"
        ),
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = ("category", "slug")

    def save(self, *args, **kwargs):
        if self.schema_definition and isinstance(self.schema_definition, list):
            from .serializers import sanitize_schema_fields
            self.schema_definition = sanitize_schema_fields(self.schema_definition)
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.pk:
            max_order = DocumentType.objects.filter(category=self.category).aggregate(Max('sort_order'))['sort_order__max']
            self.sort_order = (max_order or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} - {self.name}"



@receiver(post_save, sender=DocumentType)
def update_count_on_save(sender, instance, **kwargs):
    
    category = instance.category
    new_count = category.document_types.count()
    # 
    if category.template_count != new_count:
        category.template_count = new_count
        category.save()

@receiver(post_delete, sender=DocumentType)
def update_count_on_delete(sender, instance, **kwargs):
    
    category = instance.category
    category.template_count = category.document_types.count()
    category.save()


class DocumentTemplate(TimeStampedModel):
	ACTION_MODE_PREVIEW_DOWNLOAD_ONLY = "preview_download_only"
	ACTION_MODE_EMAIL_ONLY = "email_only"
	ACTION_MODE_SIGNATURE_ONLY = "signature_only"
	ACTION_MODE_BOTH = "both"
	ACTION_MODE_CHOICES = [
		(ACTION_MODE_PREVIEW_DOWNLOAD_ONLY, "Preview + Download only"),
		(ACTION_MODE_EMAIL_ONLY, "Preview + Download + Send by Email"),
		(ACTION_MODE_SIGNATURE_ONLY, "Preview + Download + Send for Signature"),
		(ACTION_MODE_BOTH, "Preview + Download + Email + Signature"),
	]

	document_type = models.ForeignKey(
		DocumentType,
		on_delete=models.CASCADE,
		related_name="templates",
	)
	name = models.CharField(max_length=140)
	slug = models.SlugField(blank=True)
	description = models.CharField(max_length=255, blank=True, null=True)
	preview_image = models.URLField(blank=True, null=True)
	content_template = models.TextField(
		blank=True,
		default="",
		help_text="Document body template with placeholders like [Client Name] and [Start Date].",
	)
	base_content = models.JSONField(default=dict, blank=True)
	action_mode = models.CharField(
		max_length=30,
		choices=ACTION_MODE_CHOICES,
		default=ACTION_MODE_BOTH,
		help_text=(
			"Controls which post-generation actions are available for this template. "
			"Preview and Download are always available."
		),
	)
	is_active = models.BooleanField(default=True)
	usage_count = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ["name"]
		unique_together = ("document_type", "slug")

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)
		super().save(*args, **kwargs)

	@property
	def allow_send_email(self):
		return self.action_mode in {self.ACTION_MODE_EMAIL_ONLY, self.ACTION_MODE_BOTH}

	@property
	def allow_send_signature(self):
		return self.action_mode in {self.ACTION_MODE_SIGNATURE_ONLY, self.ACTION_MODE_BOTH}

	@property
	def allowed_actions(self):
		return {
			"preview": True,
			"download": True,
			"send_email": self.allow_send_email,
			"send_signature": self.allow_send_signature,
		}

	def __str__(self):
		return self.name


class DocumentStructure(TimeStampedModel):
	"""
	Reusable document structure (e.g., Legal Agreements, Contracts, Invoices).
	Multiple document types can use the same structure - only content changes.
	"""
	STRUCTURE_TYPES = [
		('legal', 'Legal Agreements'),
		('contract', 'Contracts'),
		('financial', 'Financial Documents'),
		('hr', 'HR Documents'),
		('other', 'Other'),
	]
	structure_type = models.CharField(max_length=20, choices=STRUCTURE_TYPES)
	name = models.CharField(max_length=140)
	slug = models.SlugField(unique=True, blank=True)
	description = models.CharField(max_length=255, blank=True, null=True)
	
	# Structure definition
	has_header = models.BooleanField(default=True, help_text="Show company header with logo")
	has_signature_section = models.BooleanField(default=False, help_text="Include signature lines")
	has_date_field = models.BooleanField(default=True)
	has_page_numbers = models.BooleanField(default=True)
	has_footer = models.BooleanField(default=True, help_text="Show company footer")
	
	# Styling
	header_height_mm = models.PositiveIntegerField(default=30, help_text="Header space in mm")
	footer_height_mm = models.PositiveIntegerField(default=20, help_text="Footer space in mm")
	left_margin_mm = models.PositiveIntegerField(default=20)
	right_margin_mm = models.PositiveIntegerField(default=20)
	top_margin_mm = models.PositiveIntegerField(default=20)
	bottom_margin_mm = models.PositiveIntegerField(default=20)
	line_spacing = models.DecimalField(max_digits=3, decimal_places=1, default=1.15)
	
	# Branding
	logo_width_mm = models.PositiveIntegerField(default=40, help_text="Logo width (auto-height)")
	logo_position = models.CharField(
		max_length=20,
		choices=[('top_left', 'Top Left'), ('top_center', 'Top Center'), ('top_right', 'Top Right')],
		default='top_left'
	)
	
	is_active = models.BooleanField(default=True)
	usage_count = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ['structure_type', 'name']
		unique_together = ('structure_type', 'slug')

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(f"{self.structure_type}-{self.name}")
		super().save(*args, **kwargs)

	def __str__(self):
		return f"{self.get_structure_type_display()} - {self.name}"


class DocumentSchema(TimeStampedModel):
	"""
	Field definitions for a DocumentStructure.
	Defines what fields are required, their order, and validation rules.
	"""
	FIELD_TYPES = [
		('text', 'Short Text'),
		('textarea', 'Long Text'),
		('date', 'Date'),
		('email', 'Email'),
		('phone', 'Phone Number'),
		('number', 'Number'),
		('currency', 'Currency'),
		('checkbox', 'Checkbox'),
		('select', 'Dropdown'),
		('richtext', 'Rich Text'),
		('group', 'Grouped Fields'),
		('repeater', 'Repeatable Group'),
		('signature', 'Signature (e-sign compatible)'),
		('image', 'Image Upload'),
		('file', 'File Upload'),
	]

	structure = models.OneToOneField(
		DocumentStructure,
		on_delete=models.CASCADE,
		related_name='schema'
	)
	fields_definition = models.JSONField(
		default=list,
		blank=True,
		help_text=(
			"Array of field objects. Supported keys: "
			"name, label, type, is_required, is_visible, order, placeholder, options, section, position, "
			"repeatable, min_items, max_items, children, conditions"
		)
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def save(self, *args, **kwargs):
		if self.fields_definition and isinstance(self.fields_definition, list):
			from .serializers import sanitize_schema_fields
			self.fields_definition = sanitize_schema_fields(self.fields_definition)
		super().save(*args, **kwargs)

	def __str__(self):
		return f"Schema for {self.structure.name}"

	class Meta:
		verbose_name_plural = "Document Schemas"


class GeneratedDocument(TimeStampedModel):
	STATUS_CHOICES = [
		("active", "Active"),
		("archived", "Archived"),
		("under_review", "Under Review"),
		("draft", "Draft"),
	]

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="generated_documents",
	)
	category = models.ForeignKey(
		TemplateCategory,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="generated_documents",
	)
	document_type = models.ForeignKey(
		DocumentType,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="generated_documents",
	)
	template = models.ForeignKey(
		DocumentTemplate,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="generated_documents",
	)
	structure = models.ForeignKey(
		DocumentStructure,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="generated_documents",
		help_text="Reusable document structure (layout/styling)"
	)
	name = models.CharField(max_length=160)
	form_data = models.JSONField(default=dict, blank=True)
	signature_fields = models.JSONField(
		default=list,
		blank=True,
		help_text="List of field names that require signatures (e.g., ['signature_1', 'signature_2'])"
	)
	input_fingerprint = models.CharField(max_length=64, blank=True, null=True, db_index=True)
	rendered_content = models.TextField(blank=True, null=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
	# Path to the signed PDF (relative to MEDIA_ROOT), if generated
	signed_pdf_path = models.CharField(max_length=512, blank=True, null=True)
	credit_used = models.PositiveIntegerField(default=1)
	generated_at = models.DateTimeField(default=timezone.now)
	previewed_at = models.DateTimeField(blank=True, null=True)
	downloaded_at = models.DateTimeField(blank=True, null=True)

	class Meta:
		ordering = ["-generated_at"]

	def __str__(self):
		return f"{self.name} ({self.user.email})"


class DocumentAction(TimeStampedModel):
	ACTION_CHOICES = [
		("preview", "Preview"),
		("download", "Download"),
		("send_email", "Send Email"),
		("send_signature", "Send Signature"),
	]
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="document_actions",
	)
	document = models.ForeignKey(
		GeneratedDocument,
		on_delete=models.CASCADE,
		related_name="actions",
	)
	action = models.CharField(max_length=30, choices=ACTION_CHOICES)
	credit_used = models.PositiveIntegerField(default=1)
	metadata = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["-created_at"]
		unique_together = ("user", "document", "action")

	def __str__(self):
		return f"{self.user_id} - {self.document_id} - {self.action}"

class DocumentFeedback(TimeStampedModel):
	RATING_CHOICES = [(value, str(value)) for value in range(1, 6)]

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="document_feedbacks",
		null=True,
		blank=True,
	)
	document = models.OneToOneField(
		GeneratedDocument,
		on_delete=models.CASCADE,
		related_name="feedback",
		null=True,
		blank=True,
	)
	rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
	comment = models.TextField(blank=True, default="")
	is_public = models.BooleanField(default=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.rating}-star feedback for {self.document_id}"


class SignatureRequest(TimeStampedModel):
	STATUS_CHOICES = [
		("pending", "Pending"),
		("signed", "Signed"),
		("expired", "Expired"),
		("cancelled", "Cancelled"),
	]

	document = models.ForeignKey(
		GeneratedDocument,
		on_delete=models.CASCADE,
		related_name="signature_requests",
	)
	sender = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="sent_signature_requests",
	)
	recipient_email = models.EmailField()
	recipient_name = models.CharField(max_length=120, blank=True, null=True)
	token = models.CharField(max_length=64, unique=True, default=uuid.uuid4, editable=False)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
	expires_at = models.DateTimeField(blank=True, null=True)
	signed_at = models.DateTimeField(blank=True, null=True)
	signature_type = models.CharField(max_length=20, blank=True, null=True)
	signature_value = models.TextField(blank=True, null=True)
	# For sequential flows: this request may depend on another SignatureRequest
	depends_on = models.ForeignKey(
		"self",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="dependents",
		help_text="If set, this request should only be emailed/activated after the depended request is signed.",
	)
	# Track whether an email was sent for this request (helps avoid duplicate sends)
	email_sent = models.BooleanField(default=False)
	# Path to per-request signed PDF if generated (relative to MEDIA_ROOT)
	signed_pdf_path = models.CharField(max_length=512, blank=True, null=True)
	signer_role = models.CharField(max_length=120, blank=True, null=True, help_text="Signer role, e.g. Authorized Signer, Client, Employee")
	signer_title = models.CharField(max_length=120, blank=True, null=True, help_text="Signer job title, e.g. Director of Human Resources")


class SignatureAudit(TimeStampedModel):
	ACTION_CHOICES = [
		("created", "Created"),
		("signed", "Signed"),
		("expired", "Expired"),
		("email_sent", "Email Sent"),
	]

	signature_request = models.ForeignKey(
		SignatureRequest,
		on_delete=models.CASCADE,
		related_name="audits",
	)
	action = models.CharField(max_length=30, choices=ACTION_CHOICES)
	actor = models.CharField(max_length=255, blank=True, null=True, help_text="Who performed the action (user email or system)")
	metadata = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.signature_request_id} - {self.action}"



class CreditWallet(TimeStampedModel):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="credit_wallet",
	)
	credits_limit = models.PositiveIntegerField(default=200)
	credits_used = models.PositiveIntegerField(default=0)
	plan_download_limit = models.PositiveIntegerField(default=60)
	cycle_start = models.DateTimeField(default=timezone.now)
	cycle_end = models.DateTimeField(blank=True, null=True)

	@property
	def credits_remaining(self):
		if self.credits_used >= self.credits_limit:
			return 0
		return self.credits_limit - self.credits_used

	def __str__(self):
		return f"{self.user.email} ({self.credits_remaining}/{self.credits_limit})"


class PaymentMethod(TimeStampedModel):

	PROVIDER_CHOICES = [
		("stripe", "Stripe"),
		("paypal", "PayPal"),
		("manual", "Manual"),
	]

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="payment_methods",
	)
	provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default="stripe")
	card_brand = models.CharField(max_length=30)
	card_last4 = models.CharField(max_length=4)
	exp_month = models.PositiveSmallIntegerField()
	exp_year = models.PositiveSmallIntegerField()
	is_default = models.BooleanField(default=True)

	class Meta:
		ordering = ["-is_default", "-updated_at"]

	def __str__(self):
		return f"{self.card_brand} ****{self.card_last4}"


class CompanyBranding(TimeStampedModel):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="company_branding",
	)
	logo = models.ImageField(upload_to="company_branding/logo/", blank=True, null=True)
	company_name = models.CharField(max_length=200, blank=True, null=True)
	address = models.CharField(max_length=255, blank=True, null=True)
	phone = models.CharField(max_length=30, blank=True, null=True)

	def __str__(self):
		return self.company_name or f"Branding - {self.user.email}"


class HelpArticle(TimeStampedModel):
	SECTION_CHOICES = [
		("getting_started", "Getting Started"),
		("billing", "Billing & Payments"),
		("templates", "Templates & Docs"),
	]
	section = models.CharField(max_length=30, choices=SECTION_CHOICES)
	title = models.CharField(max_length=200)
	slug = models.SlugField(unique=True, blank=True)
	short_description = models.CharField(max_length=255, blank=True, null=True)
	content = models.TextField()
	is_popular = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	sort_order = models.PositiveIntegerField(default=1)

	class Meta:
		ordering = ["section", "sort_order", "title"]

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.title)
		super().save(*args, **kwargs)

	def __str__(self):
		return self.title

class DocumentRequest(TimeStampedModel):
	STATUS_CHOICES = [
		("pending", "Pending"),
		("in_progress", "In Progress"),
		("completed", "Completed"),
	]
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="document_requests",
	)
	document_name = models.CharField(max_length=200)
	category = models.ForeignKey(
		TemplateCategory,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="requested_documents",
	)
	short_description = models.TextField(blank=True, null=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
	request_count = models.PositiveIntegerField(default=1)

	class Meta:
		ordering = ["-request_count", "-created_at"]

	def __str__(self):
		return self.document_name
