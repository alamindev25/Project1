from django.db import models

# Create your models here.

class AboutSystem(models.Model):
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    email = models.EmailField()
    contact_phone = models.CharField(max_length=50, blank=True, null=True)
    office_address = models.TextField(blank=True, null=True)
    contact_notification_email = models.EmailField(blank=True, null=True)
    copyright = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='about_system/logo/', blank=True, null=True)
    favicon = models.ImageField(upload_to='about_system/favicon/', blank=True, null=True)
    description = models.TextField()

    def __str__(self):
        return self.title

class DynamicPages(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    status = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class SMTPSetting(models.Model):
    ENCRYPTION_CHOICES = [
        ('none', 'None'),
        ('tls', 'TLS'),
        ('ssl', 'SSL'),
    ]

    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField()
    username = models.EmailField()
    password = models.CharField(max_length=255)
    encryption = models.CharField(max_length=10, choices=ENCRYPTION_CHOICES, default='tls')
    sender_name = models.CharField(max_length=255, blank=True, null=True)
    sender_email = models.EmailField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.host} ({self.sender_email})"
    
    def get_email_backend_settings(self):
        return {
            'EMAIL_HOST': self.host,
            'EMAIL_PORT': self.port,
            'EMAIL_HOST_USER': self.username,
            'EMAIL_HOST_PASSWORD': self.password,
            'EMAIL_USE_TLS': self.encryption == 'tls',
            'EMAIL_USE_SSL': self.encryption == 'ssl',
        }


class SocialMedia(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    icon = models.ImageField(upload_to='about_system/social_media/', blank=True, null=True)


class SystemColor(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=7)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LandingPageHero(models.Model):
    """Landing page hero section content - editable from admin"""
    title = models.CharField(max_length=500, default="Generate professional business documents instantly")
    subtitle = models.CharField(max_length=500, default="Structured templates, fast generation, and instant PDF export.")
    cta_primary = models.CharField(max_length=100, default="Get Started Free", help_text="Primary button text")
    cta_secondary = models.CharField(max_length=100, default="View Templates", help_text="Secondary button text")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Landing Page Hero"
    
    class Meta:
        verbose_name = "Landing Page Hero Section"
        verbose_name_plural = "Landing Page Hero Sections"


class LandingPagePricing(models.Model):
    """Landing page pricing tiers - editable from admin"""
    PLAN_TYPES = [
        ('starter', 'Starter'),
        ('pro', 'Professional'),
        ('business', 'Business'),
    ]
    
    BILLING_PERIODS = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    plan_name = models.CharField(max_length=100, choices=PLAN_TYPES)
    billing_period = models.CharField(max_length=20, choices=BILLING_PERIODS)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    downloads = models.PositiveIntegerField(help_text="Number of downloads per month")
    tagline = models.CharField(max_length=255, blank=True, null=True, help_text="e.g., 'Start with Starter and upgrade anytime'")
    features = models.TextField(blank=True, null=True, help_text="Features, one per line (e.g., Unlimited Previews, Add custom logo)")
    footer_text = models.TextField(blank=True, null=True, help_text="Footer disclaimer (e.g., 'Credits reset every billing cycle...')")
    save_percent = models.PositiveIntegerField(default=0, help_text="Percentage saved (yearly plans)")
    is_popular = models.BooleanField(default=False, help_text="Mark as 'Most Popular'")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_plan_name_display()} - {self.get_billing_period_display()} - ${self.price}"
    
    class Meta:
        verbose_name = "Landing Page Pricing"
        verbose_name_plural = "Landing Page Pricing Tiers"
        ordering = ['order']


class LandingPageFeature(models.Model):
    """Landing page features/steps - editable from admin"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = "Landing Page Feature/Step"
        verbose_name_plural = "Landing Page Features/Steps"
        ordering = ['order']


class LandingPageBadge(models.Model):
    """Security/trust badges - editable from admin"""
    title = models.CharField(max_length=255, help_text="e.g., SSL Secured, 24/7 Support")
    icon = models.CharField(max_length=100, blank=True, null=True, help_text="Icon name or emoji")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = "Security Badge"
        verbose_name_plural = "Security Badges"
        ordering = ['order']


class LandingPageSection(models.Model):
    """Flexible landing page sections editable from admin (text/image/video/buttons)."""
    page = models.CharField(max_length=100, default="landing")
    section_key = models.CharField(max_length=100, help_text="Unique key, e.g. hero, how_it_works, preview_samples")
    title = models.CharField(max_length=255, blank=True, null=True)
    sub_title = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    short_description = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True, help_text="Optional external image URL (useful for large files)")
    image = models.ImageField(upload_to='system_setting/landing/sections/', blank=True, null=True)
    preview_image_1 = models.ImageField(upload_to='system_setting/landing/preview_samples/', blank=True, null=True)
    preview_image_2 = models.ImageField(upload_to='system_setting/landing/preview_samples/', blank=True, null=True)
    preview_image_3 = models.ImageField(upload_to='system_setting/landing/preview_samples/', blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)
    button_text = models.CharField(max_length=255, blank=True, null=True)
    button_link = models.CharField(max_length=255, blank=True, null=True)
    other = models.CharField(max_length=255, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Landing Page Section"
        verbose_name_plural = "Landing Page Sections"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page} - {self.section_key}"


class LandingPreviewSample(models.Model):
    title = models.CharField(max_length=255)
    image_url = models.URLField(blank=True, null=True, help_text="Optional external image URL (useful for large files)")
    image = models.ImageField(upload_to='system_setting/landing/preview_samples/', blank=True, null=True)
    video_url = models.URLField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Landing Preview Sample"
        verbose_name_plural = "Landing Preview Samples"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class LandingTestimonial(models.Model):
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True, null=True)
    rating = models.PositiveSmallIntegerField(default=5)
    comment = models.TextField()
    avatar = models.ImageField(upload_to='system_setting/landing/testimonials/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Landing Testimonial"
        verbose_name_plural = "Landing Testimonials"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class LandingCheckoutBrand(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='system_setting/landing/checkout_brands/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Landing Checkout Brand"
        verbose_name_plural = "Landing Checkout Brands"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

class DashboardSettings(models.Model):
    """User dashboard customization settings"""
    welcome_message = models.CharField(max_length=500, default="Welcome to your dashboard!", help_text="Welcome message for logged-in users")
    sidebar_menu = models.TextField(
        default="Templates\nBilling & Payments\nHistory\nHelp Center\nSettings",
        help_text="Sidebar menu labels, one item per line",
    )
    search_placeholder = models.CharField(max_length=255, default="Search your templates")
    user_role_label = models.CharField(max_length=255, default="Operations Manager")
    credits_text_template = models.CharField(
        max_length=255,
        default="Credits Remaining {remaining}/{limit}",
        help_text="Use {remaining} and {limit} placeholders",
    )
    show_recent_documents = models.BooleanField(default=True)
    show_subscription_info = models.BooleanField(default=True)
    show_credits_info = models.BooleanField(default=True)
    max_recent_documents = models.PositiveIntegerField(default=5, help_text="Number of recent documents to show")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Dashboard Settings"
    
    class Meta:
        verbose_name = "Dashboard Settings"
        verbose_name_plural = "Dashboard Settings"


class ContactUs(models.Model):
    PURPOSE_CHOICES = [
        ('general_inquiry', 'General Inquiry'),
        ('support', 'Support'),
        ('feedback', 'Feedback'),
        ('refund_request', 'Refund Request'),
        ('others', 'Others'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
    ]

    name = models.CharField(max_length=120)
    email = models.EmailField()
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.purpose}"