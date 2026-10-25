from django.contrib import admin
from .models import SubscriptionPackage, Features, Subscription, PaymentHistory
from unfold.admin import ModelAdmin, TabularInline


# Subscription Package Features
class FeaturesInline(TabularInline):
    model = Features
    extra = 0
    ordering_field = "order" # enables drag-and-drop sorting
    hide_ordering_field = False
    fields = ("order", "text", "include")  # keep order included (required)

    class Media:
        js = ("admin/js/feature_order_autofill.js",)

# Subscription Package
@admin.register(SubscriptionPackage)
class SubscriptionPackageAdmin(ModelAdmin):
    list_display = (
        'plan_name',
        'billing_period',
        'billing_summary',
        'price',
        'downloads',
        'save_percent',
        'most_popular',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'billing_period', 'most_popular', 'billing_cycle_type')
    search_fields = ('plan_name', 'billing_cycle', 'stripe_price_id', 'stripe_product_id')
    ordering = ('billing_period', 'price', 'id')
    inlines = [FeaturesInline]
    list_editable = ('price', 'downloads', 'save_percent', 'most_popular', 'is_active')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ("Plan", {
            'fields': (
                'plan_name',
                'billing_period',
                'most_popular',
                'save_percent',
                'downloads',
                'price',
                'is_active',
            )
        }),
        ("Billing Rule", {
            'fields': (
                'billing_cycle_type', 
                'billing_cycle', 
                'custom_days', 
            )
        }),
        ("Stripe", {
            'fields': (
                'stripe_product_id',
                'stripe_price_id',
                )
        }),
        ("Timestamps", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Billing')
    def billing_summary(self, obj):
        if obj.billing_cycle_type == 'custom' and obj.custom_days:
            return f"{obj.custom_days} Days"
        return obj.billing_cycle or '-'

    class Media:
        js = ("admin/js/planitem_billing_toggle.js",)


# Subscribed users admin
@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ('user_email', 'subscriptionpackage', 'status', 'start_date', 'end_date', 'stripe_subscription_id', 'created_at')
    list_filter = ('status', 'subscriptionpackage')
    search_fields = ('user__email', 'stripe_subscription_id')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user', 'subscriptionpackage')
    list_select_related = ('user', 'subscriptionpackage')
    ordering = ('-start_date',)
    date_hierarchy = 'start_date'

    fieldsets = (
        ('Subscription', {
            'fields': ('user', 'subscriptionpackage', 'status', 'stripe_subscription_id')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'created_at', 'updated_at')
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(ModelAdmin):
    list_display = ('user', 'subscriptionpackage', 'amount', 'payment_gateway', 'payment_status', 'transaction_id', 'paid_at')
    list_filter = ('payment_gateway', 'payment_status')
    search_fields = ('user__email', 'transaction_id')
    readonly_fields = ('paid_at',)
    autocomplete_fields = ('user', 'subscriptionpackage')
    list_select_related = ('user', 'subscriptionpackage')
    date_hierarchy = 'paid_at'

    fieldsets = (
        ('Payment', {
            'fields': ('user', 'subscriptionpackage', 'amount', 'payment_gateway', 'payment_status', 'transaction_id')
        }),
        ('Timeline', {
            'fields': ('paid_at',)
        }),
    )
