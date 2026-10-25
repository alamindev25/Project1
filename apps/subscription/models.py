from django.db import models
from project import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL

# Subscription Plan Item
class SubscriptionPackage(models.Model):
    BILLING_CHOICES = [

        ('30 Days', '30 Days'),

        ('365 Days', '365 Days'),
    ]

    BILLING_PERIOD_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    CYCLE_TYPE = [
        ('preset', 'Preset'),
        ('custom', 'Custom'),
    ]
    billing_cycle_type = models.CharField(max_length=10, choices=CYCLE_TYPE, default='preset')
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CHOICES, blank=True, null=True)
    billing_period = models.CharField(max_length=10, choices=BILLING_PERIOD_CHOICES, blank=True, null=True)
    custom_days = models.PositiveIntegerField(blank=True, null=True)
    plan_name = models.CharField(max_length=50, blank=True, null=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    downloads = models.PositiveIntegerField(blank=True, null=True)
    save_percent = models.PositiveIntegerField(blank=True, null=True)
    most_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="Designates whether this plan is active and available for subscription.")
    stripe_product_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def clean(self):
        # preset need only select
        if self.billing_cycle_type == 'preset':
            if not self.billing_cycle:
                raise ValidationError({
                    "billing_cycle": "Billing cycle is required for preset plans."
                })
            if self.custom_days:
                raise ValidationError({
                    "custom_days": "Custom days must be empty for preset plans."
                })

        # custiom days need value
        if self.billing_cycle_type == 'custom':
            if not self.custom_days:
                raise ValidationError({
                    "custom_days": "Custom days value is required for custom plans."
                })
            if self.billing_cycle:
                raise ValidationError({
                    "billing_cycle": "Preset billing cycle cannot be selected for custom plans."
                })

    def get_billing_days(self):
        # Return billing duration in days
        if self.billing_cycle_type == 'custom':
            return self.custom_days

        mapping = {
            '7 Days': 7,
            '14 Days': 14,
            '30 Days': 30,
            '90 Days': 90,
            '180 Days': 180,
            '365 Days': 365,
        }
        return mapping.get(self.billing_cycle)

    def __str__(self):
        if self.billing_cycle_type == 'custom':
            return f"{self.custom_days} Days (Custom) Plan"
        return f"{self.billing_cycle} Plan"

# Subscription Package Features
class Features(models.Model):
    subscriptionpackage = models.ForeignKey(SubscriptionPackage, on_delete=models.CASCADE, related_name="features", null=True, blank=True)
    text = models.CharField(max_length=255, null=True, blank=True)
    include = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1, db_index=True)  # IMPORTANT for drag-and-drop ordering
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
    def __str__(self):
        return self.text or "Features Text"

# User Subscription
class Subscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    subscriptionpackage = models.ForeignKey(SubscriptionPackage, on_delete=models.PROTECT, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True) 
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending')
    ], default='pending')  
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def has_subscription(self):
        return self.status == 'active' and self.end_date > timezone.now()
    
    # expire subscription if end_date has passed
    def check_and_update_status(self):
        if self.status == 'active' and self.end_date and self.end_date < timezone.now():
            self.status = 'expired'
            self.save()
    
    def __str__(self):
        return f"{self.user.email} "

# Payment History
class PaymentHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subscriptionpackage = models.ForeignKey(SubscriptionPackage, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_gateway = models.CharField(max_length=50, choices=[
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    ])
    payment_status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'), 
    ])
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subscriptionpackage.price if self.subscriptionpackage else self.amount}"

# Income Report (for admin dashboard)
class IncomeReport(models.Model):
    total_income = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Income Report for {self.month.strftime('%B %Y')} - Total Income: {self.total_income}"
