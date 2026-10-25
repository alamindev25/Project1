from decimal import Decimal


def seed_subscription_plans():
    """Seed monthly/yearly Starter, Pro, Business plans with feature rows."""

    # Import models lazily to avoid "Apps aren't loaded yet" when module is imported
    from apps.subscription.models import SubscriptionPackage, Features

    plans = [
        {
            "plan_name": "Free Plan",
            "billing_period": "monthly",
            "custom_days": 30,
            "price": Decimal("0.00"),
            "downloads": 1,
            "save_percent": None,
            "most_popular": False,
            "features": [
                {"text": "1 document download total", "include": True},
                {"text": "PDF download only", "include": True},
            ],
        },
        {
            "plan_name": "Starter",
            "billing_period": "monthly",
            "custom_days": 30,
            "price": Decimal("19.00"),
            "downloads": 15,
            "save_percent": None,
            "most_popular": False,
            "features": [
                {"text": "Unlimited previews", "include": True},
                {"text": "Add custom logo", "include": True},
                {"text": "Up to 5 sends (Email/Sign)", "include": True},
                {"text": "Manual print & sign", "include": True},
            ],
        },
        {
            "plan_name": "Pro",
            "billing_period": "monthly",
            "custom_days": 30,
            "price": Decimal("39.99"),
            "downloads": 60,
            "save_percent": None,
            "most_popular": True,
            "features": [
                {"text": "Unlimited previews", "include": True},
                {"text": "Add custom logo", "include": True},
                {"text": "Full Email & E-sign", "include": True},
                {"text": "Download & Print", "include": True},
            ],
        },
        {
            "plan_name": "Business",
            "billing_period": "monthly",
            "custom_days": 30,
            "price": Decimal("99.99"),
            "downloads": 200,
            "save_percent": None,
            "most_popular": False,
            "features": [
                {"text": "Unlimited previews", "include": True},
                {"text": "Add custom logo", "include": True},
                {"text": "Full Email & E-sign", "include": True},
                {"text": "Priority support", "include": True},
                {"text": "Download & Print", "include": True},
            ],
        },
        {
            "plan_name": "Starter",
            "billing_period": "yearly",
            "custom_days": 365,
            "price": Decimal("182.40"),
            "downloads": 180,
            "save_percent": 20,
            "most_popular": False,
            "features": [
                {"text": "Standard visibility boost", "include": True},
                {"text": "Standard Reach", "include": True},
                {"text": "Maximum_exposures", "include": False},
                {"text": "priority", "include": False},
            ],
        },
        {
            "plan_name": "Pro",
            "billing_period": "yearly",
            "custom_days": 365,
            "price": Decimal("383.90"),
            "downloads": 720,
            "save_percent": 20,
            "most_popular": True,
            "features": [
                {"text": "Extend visibility boost", "include": True},
                {"text": "Extend Reach", "include": True},
                {"text": "Extend_exposures", "include": True},
                {"text": "Extend_priority", "include": True},
            ],
        },
        {
            "plan_name": "Business",
            "billing_period": "yearly",
            "custom_days": 365,
            "price": Decimal("959.90"),
            "downloads": 2400,
            "save_percent": 20,
            "most_popular": False,
            "features": [
                {"text": "Maximum visibility boost", "include": True},
                {"text": "Maximum Reach", "include": True},
                {"text": "maximum_exposures", "include": True},
                {"text": "maximum_priority", "include": True},
            ],
        },
    ]

    # Deactivate old preset packages so they no longer appear in active package API.
    SubscriptionPackage.objects.filter(
        billing_cycle_type="preset",
        billing_cycle__in=["7 Days", "14 Days", "30 Days"],
    ).update(is_active=False)

    for plan_data in plans:
        defaults = {
            "billing_cycle_type": "custom",
            "billing_cycle": None,
            "custom_days": plan_data["custom_days"],
            "price": plan_data["price"],
            "downloads": plan_data["downloads"],
            "save_percent": plan_data["save_percent"],
            "most_popular": plan_data["most_popular"],
            "is_active": True,
        }

        if plan_data["plan_name"] == "Free Plan" and plan_data["billing_period"] == "monthly":
            # Handle legacy naming ("Free") and keep a single active free package row.
            plan = (
                SubscriptionPackage.objects.filter(
                    billing_period=plan_data["billing_period"],
                    plan_name__in=["Free", "Free Plan"],
                )
                .order_by("id")
                .first()
            )
            if plan:
                for key, value in defaults.items():
                    setattr(plan, key, value)
                plan.plan_name = "Free Plan"
                plan.save()
            else:
                plan = SubscriptionPackage.objects.create(
                    plan_name="Free Plan",
                    billing_period=plan_data["billing_period"],
                    **defaults,
                )
        else:
            plan, _ = SubscriptionPackage.objects.update_or_create(
                plan_name=plan_data["plan_name"],
                billing_period=plan_data["billing_period"],
                defaults=defaults,
            )

        # Create features; keep ordering consistent
        for idx, feat in enumerate(plan_data["features"], start=1):
            Features.objects.update_or_create(
                subscriptionpackage=plan,
                text=feat["text"],
                defaults={"include": feat["include"], "order": idx},
            )

        # Remove legacy feature rows for this plan that are not in current seed list.
        feature_texts = [feat["text"] for feat in plan_data["features"]]
        Features.objects.filter(subscriptionpackage=plan).exclude(text__in=feature_texts).delete()

    print("✅ Subscription plans seeded successfully.")
