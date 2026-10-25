from rest_framework import serializers
from .models import SubscriptionPackage, Features, Subscription

# Subscription Package Features
class FeaturesSerializer(serializers.ModelSerializer):

    class Meta:
        model = Features
        fields = [
            'order',
            'text', 
            'include',
            ]

# Subscription Package
class SubscriptionPackageSerializer(serializers.ModelSerializer): 
    features = serializers.SerializerMethodField()
    billing_days = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPackage
        fields = [
            'id', 
            'plan_name',
            'billing_period',
            'billing_days',
            'price',
            'downloads',
            'save_percent',
            'most_popular',
            'stripe_price_id',
            'stripe_product_id',
            'is_active', 
            'features',
            ]

    def get_billing_days(self, obj):
        return obj.get_billing_days()

    def get_features(self, obj):
        feature_qs = obj.features.all()
        if feature_qs.exists():
            return FeaturesSerializer(feature_qs, many=True).data

        # Backward-compatible fallback for old "Free Plan" rows created without features.
        plan_name = (obj.plan_name or "").strip().lower()
        if obj.downloads and (plan_name in {"free", "free plan"}):
            return [
                {
                    "order": 1,
                    "text": f"{obj.downloads} document download total",
                    "include": True,
                },
                {
                    "order": 2,
                    "text": "PDF download only",
                    "include": True,
                },
            ]

        return []

# Subscription Plan
class SubscriptionPlanSerializer(serializers.ModelSerializer):

    class Meta:
        model = SubscriptionPackage
        fields = [
            'id', 
            'plan_name',
            'billing_period',
            'price',
            'is_active',
            'stripe_price_id',
            ]

# Current Subscription Plan
class CurrentPlanSerializer(serializers.ModelSerializer):
    subscriptionpackage = SubscriptionPlanSerializer()
    class Meta:
        model = Subscription
        fields = [
            'id',
            'subscriptionpackage',
            'status',
            'start_date',
            'end_date',
            ]
