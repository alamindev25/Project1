from rest_framework.views import APIView
from rest_framework.response import Response
from .models import SubscriptionPackage, Subscription, PaymentHistory
from .serializers import SubscriptionPackageSerializer, CurrentPlanSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
import logging
import stripe
from decimal import Decimal
logger = logging.getLogger(__name__)
from apps.user.authentication import JWTAuthentication
from apps.user.models import User
from django.http import HttpResponse
from apps.utils.helpers import success, error
from django.conf import settings
from django.db.models import Case, IntegerField, Value, When


def _is_missing_stripe_resource(exc: Exception) -> bool:
    message = str(exc)
    return "No such price" in message or "No such product" in message or "resource_missing" in message


def _stripe_recurring_dict(package: SubscriptionPackage):
    days = package.get_billing_days() or 30
    return {"interval": "day", "interval_count": int(days)}


def _ensure_stripe_price(package: SubscriptionPackage):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    recurring = _stripe_recurring_dict(package)
    product_name = f"{package.plan_name or 'Subscription'} Plan"

    product_id = package.stripe_product_id
    if product_id:
        try:
            stripe.Product.retrieve(product_id)
        except Exception as exc:
            if _is_missing_stripe_resource(exc):
                product_id = None
            else:
                raise

    if not product_id:
        product = stripe.Product.create(name=product_name)
        product_id = product.id
        package.stripe_product_id = product_id
        package.save(update_fields=["stripe_product_id"])

    if package.stripe_price_id:
        try:
            price = stripe.Price.retrieve(package.stripe_price_id)
            if price:
                return price.id
        except Exception as exc:
            if _is_missing_stripe_resource(exc):
                package.stripe_price_id = None
            else:
                raise

    price = stripe.Price.create(
        product=product_id,
        currency=getattr(settings, "STRIPE_CURRENCY", "usd"),
        unit_amount=int(package.price * 100),
        recurring=recurring,
    )
    package.stripe_price_id = price.id
    package.save(update_fields=["stripe_price_id"])
    return price.id


# Subscription Package List
class SubscriptionPackageView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            billing_period = (request.query_params.get('billing_period') or '').strip().lower()

            subscription_packages = SubscriptionPackage.objects.filter(is_active=True)
            if billing_period in {'monthly', 'yearly'}:
                subscription_packages = subscription_packages.filter(billing_period=billing_period)

            # Keep a stable card order: Free -> Starter -> Pro -> Business -> others.
            plan_order = Case(
                When(plan_name__iexact='Free', then=Value(1)),
                When(plan_name__iexact='Starter', then=Value(2)),
                When(plan_name__iexact='Pro', then=Value(3)),
                When(plan_name__iexact='Business', then=Value(4)),
                default=Value(99),
                output_field=IntegerField(),
            )

            subscription_packages = subscription_packages.annotate(plan_order=plan_order).order_by(
                'billing_period', 'plan_order', 'price', 'id'
            ).prefetch_related('features')

            serializer = SubscriptionPackageSerializer(subscription_packages, many=True)

            return Response({
                "status": status.HTTP_200_OK,
                "success": True,
                "message": "Active subscription packages retrieved successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "success": False,
                "message": f"An error occurred: {str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Stripe Checkout
class StripeCheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        price_id = request.data.get('price_id')
        subscriptionpackage_id = request.data.get('subscriptionpackage_id')
        success_url = request.data.get('success_url')
        cancel_url = request.data.get('cancel_url')

        stripe.api_key = settings.STRIPE_SECRET_KEY
        

 
        if not success_url or not cancel_url:
            return error(message="Missing required parameters", errors="success_url and cancel_url are required")

        try:
            package = None
            if subscriptionpackage_id:
                package = SubscriptionPackage.objects.filter(pk=subscriptionpackage_id).first()

            if not package and price_id:
                package = SubscriptionPackage.objects.filter(stripe_price_id=price_id).first()

            if package:
                price_id = _ensure_stripe_price(package)
            elif price_id:
                stripe.Price.retrieve(price_id)
            else:
                return error(message="Missing required parameters", errors="price_id or subscriptionpackage_id is required")

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                customer_email=request.user.email if request.user.is_authenticated else None,
                
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
            )

            return success(checkout_session.url, message="Stripe checkout initiated successfully")
        except Exception as e:
            if not _is_missing_stripe_resource(e):
                return error(message="Failed to initiate Stripe checkout", errors=str(e))
            return error(message="Failed to initiate Stripe checkout", errors=str(e))

# Stripe Webhook
class StripeWebhookAPIView(APIView):
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError as e:
            logger.error("Invalid payload: %s", e)
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            logger.error("Invalid signature: %s", e)
            return HttpResponse(status=400)

        try:
            event_type = event.get('type')

            # Handle initial checkout session completion
            if event_type == 'checkout.session.completed':
                session = event['data']['object']
                session_id = session.get('id')
                checkout_session = stripe.checkout.Session.retrieve(session_id, expand=['line_items'])

                customer_email = session.get('customer_email')
                user = User.objects.filter(email=customer_email).first()
                if not user:
                    return HttpResponse(status=200)

                line_items = checkout_session.get('line_items', {}).get('data', [])
                price_id = line_items[0].get('price', {}).get('id') if line_items else None
                package = SubscriptionPackage.objects.filter(stripe_price_id=price_id).first()
                if not package:
                    return HttpResponse(status=200)

                transaction_id = session.get('subscription') or session.get('payment_intent') or session_id

                # Idempotency: skip if we've already processed this transaction
                if PaymentHistory.objects.filter(transaction_id=transaction_id, payment_gateway='stripe').exists():
                    return HttpResponse(status=200)

                PaymentHistory.objects.create(
                    user=user,
                    subscriptionpackage=package,
                    amount=package.price,
                    payment_gateway='stripe',
                    payment_status='success',
                    transaction_id=transaction_id,
                )

                return HttpResponse(status=200)

            # Handle recurring invoice payments (e.g., monthly charge)
            if event_type == 'invoice.payment_succeeded':
                invoice = event['data']['object']
                invoice_id = invoice.get('id')
                subscription_id = invoice.get('subscription')
                amount_paid = (invoice.get('amount_paid') or 0) / 100

                # Idempotency
                if PaymentHistory.objects.filter(transaction_id=invoice_id, payment_gateway='stripe').exists():
                    return HttpResponse(status=200)

                sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first() if subscription_id else None
                pkg = sub.subscriptionpackage if sub else None

                # Fallback: try price id in lines
                if not pkg:
                    lines = invoice.get('lines', {}).get('data', [])
                    price_id = lines[0].get('price', {}).get('id') if lines else None
                    pkg = SubscriptionPackage.objects.filter(stripe_price_id=price_id).first() if price_id else None

                if not pkg or not sub or not sub.user:
                    # Nothing we can link to; ignore
                    return HttpResponse(status=200)

                amount = Decimal(amount_paid) if amount_paid else pkg.price

                PaymentHistory.objects.create(
                    user=sub.user,
                    subscriptionpackage=pkg,
                    amount=amount,
                    payment_gateway='stripe',
                    payment_status='success',
                    transaction_id=invoice_id,
                )

                return HttpResponse(status=200)

        except Exception as e:
            logger.exception("Error handling Stripe webhook event: %s", str(e))
            return HttpResponse(status=500)

        return HttpResponse(status=200)  # Always return a response

# Current Subscription Plan
class CurrentSubscriptionPlanAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        try:
            subscription = Subscription.objects.filter(user=user, status='active').first()
            if(not subscription):
                return error(message="No subscription found for the user", errors="User does not have a subscription", status_code=200)
            if subscription:
                serializer = CurrentPlanSerializer(subscription)
                return success(serializer.data, message="Current subscription plan fetched successfully")
        except Exception as e:
            return error(message="Failed to fetch current subscription plan", errors=str(e))

# Cancel Subscription
class CancelSubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        user = request.user
        try:
            subscription = Subscription.objects.filter(user=user, status='active').first()
            if not subscription:
                return error(message="No active subscription found to cancel", errors="User does not have an active subscription", status_code=200)

            subscription.status = 'cancelled'
            subscription.save()

            return success(message="Subscription cancelled successfully")
        except Exception as e:
            return error(message="Failed to cancel subscription", errors=str(e))
