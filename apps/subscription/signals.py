import logging
import stripe
from django.conf import settings
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models.signals import post_save, pre_delete

from .models import SubscriptionPackage, Subscription, PaymentHistory, IncomeReport

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


def _is_missing_stripe_resource(exc: Exception) -> bool:
    message = str(exc)
    return "No such price" in message or "No such product" in message or "resource_missing" in message

# Recurring billing
def _stripe_recurring_dict(pkg: SubscriptionPackage):
    days = pkg.get_billing_days() or 30
    return {"interval": "day", "interval_count": int(days)}

# Product name
def _product_name(pkg: SubscriptionPackage):
    if pkg.billing_cycle_type == "custom":
        label = f"{pkg.custom_days}-day Custom Plan"
    else:
        label = f"{pkg.billing_cycle} Plan"
    return f"{label} — ${pkg.price}"

# Signal to create/update Stripe Product and Price on SubscriptionPackage save
@receiver(post_save, sender=SubscriptionPackage)
def create_or_update_stripe_package(sender, instance, created, **kwargs):
    try:
        recurring = _stripe_recurring_dict(instance)
        name = _product_name(instance)
        target_amount = int(instance.price * 100)
        product_id = instance.stripe_product_id
        price_id = instance.stripe_price_id

        # Create product if missing
        if product_id:
            try:
                stripe.Product.retrieve(product_id)
            except Exception as exc:
                if _is_missing_stripe_resource(exc):
                    product_id = None
                else:
                    raise

        if not product_id:
            product = stripe.Product.create(name=name)
            product_id = product.id
            SubscriptionPackage.objects.filter(pk=instance.pk).update(stripe_product_id=product_id)

        # Create price if missing
        if price_id:
            try:
                price = stripe.Price.retrieve(price_id)
            except Exception as exc:
                if _is_missing_stripe_resource(exc):
                    price = None
                    price_id = None
                else:
                    raise
        else:
            price = None

        if not price_id:
            price = stripe.Price.create(
                product=product_id,
                currency=getattr(settings, "STRIPE_CURRENCY", "usd"),
                unit_amount=target_amount,
                recurring=recurring,
            )
            SubscriptionPackage.objects.filter(pk=instance.pk).update(stripe_price_id=price.id)
            return

        # Update existing product/price if necessary
        product = stripe.Product.retrieve(product_id)

        # Update product name if changed
        if product.get("name") != name:
            stripe.Product.modify(product_id, name=name)

        # Update price if unit_amount changed: deactivate old price and create a new one
        if price and price.get("unit_amount") != target_amount:
            stripe.Price.modify(price_id, active=False)
            new_price = stripe.Price.create(
                product=product_id,
                currency=getattr(settings, "STRIPE_CURRENCY", "usd"),
                unit_amount=target_amount,
                recurring=recurring,
            )
            SubscriptionPackage.objects.filter(pk=instance.pk).update(stripe_price_id=new_price.id)

    except Exception as exc:  # pragma: no cover - external API
        logger.exception("Stripe sync failed for SubscriptionPackage(id=%s): %s", instance.pk, exc)

# Safely deactivate Stripe product and price when a package is deleted.
@receiver(pre_delete, sender=SubscriptionPackage)
def deactivate_stripe_package(sender, instance, **kwargs):
    try:
        if instance.stripe_price_id:
            stripe.Price.modify(instance.stripe_price_id, active=False)
        if instance.stripe_product_id:
            stripe.Product.modify(instance.stripe_product_id, active=False)
    except Exception as exc:  # pragma: no cover - external API
        logger.exception("Failed to deactivate Stripe objects for SubscriptionPackage(id=%s): %s", instance.pk, exc)

# On successful payment, create or extend a Subscription and sync CreditWallet for the user atomically.
@receiver(post_save, sender=PaymentHistory)
def handle_successful_payment(sender, instance, created, **kwargs):
    # Only act on successful payments with an associated package
    if not created:
        return

    if instance.payment_status != "success":
        return

    pkg = instance.subscriptionpackage
    if not pkg:
        logger.debug("PaymentHistory(id=%s) has no subscription package; skipping subscription update.", instance.pk)
        return

    try:
        from apps.dashboard.models import CreditWallet

        with transaction.atomic():
            now = timezone.now()
            days = pkg.get_billing_days() or 30

            # 1. Deactivate other active subscriptions of this user to avoid multiple active plans
            Subscription.objects.filter(
                user=instance.user,
                status="active",
            ).exclude(
                subscriptionpackage=pkg,
            ).update(status="cancelled")

            # 2. Get or create subscription for this package
            sub = Subscription.objects.filter(
                user=instance.user,
                subscriptionpackage=pkg,
            ).order_by("-created_at").first()

            if sub:
                # If subscription already exists, extend if active or set new period if expired
                if sub.end_date and sub.end_date > now and sub.status == "active":
                    sub.end_date = sub.end_date + timedelta(days=days)
                else:
                    sub.start_date = now
                    sub.end_date = now + timedelta(days=days)
                    sub.status = "active"
                if instance.transaction_id:
                    sub.stripe_subscription_id = instance.transaction_id
                sub.save()
            else:
                sub = Subscription.objects.create(
                    user=instance.user,
                    subscriptionpackage=pkg,
                    start_date=now,
                    end_date=now + timedelta(days=days),
                    status="active",
                    stripe_subscription_id=instance.transaction_id or None,
                )

            # 3. Auto-sync CreditWallet atomically with the new package limits and reset usage
            wallet, _ = CreditWallet.objects.select_for_update().get_or_create(user=instance.user)
            credits_limit = pkg.downloads or 1
            wallet.credits_limit = credits_limit
            wallet.plan_download_limit = credits_limit
            wallet.credits_used = 0  # Reset used credits for newly purchased package/cycle
            wallet.cycle_start = sub.start_date
            wallet.cycle_end = sub.end_date
            wallet.save(update_fields=[
                "credits_limit",
                "credits_used",
                "plan_download_limit",
                "cycle_start",
                "cycle_end",
                "updated_at",
            ])

            # 4. Update IncomeReport total income
            try:
                income_report = IncomeReport.objects.select_for_update().first()
                if income_report is None:
                    income_report = IncomeReport.objects.create(total_income=instance.amount)
                else:
                    income_report.total_income += instance.amount
                    income_report.save(update_fields=["total_income"])
            except Exception as exc2:
                logger.exception("Failed to update IncomeReport for PaymentHistory(id=%s): %s", instance.pk, exc2)

    except Exception as exc:
        logger.exception("Failed to update Subscription and CreditWallet for PaymentHistory(id=%s): %s", instance.pk, exc)

