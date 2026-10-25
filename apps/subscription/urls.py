from django.urls import path
from .views import (
SubscriptionPackageView, StripeCheckoutAPIView, StripeWebhookAPIView, 
CurrentSubscriptionPlanAPIView, CancelSubscriptionAPIView, 
)

urlpatterns = [
    path('subscription/packages/', SubscriptionPackageView.as_view(), name='subscription-package'),
    path('stripe/checkout/', StripeCheckoutAPIView.as_view(), name='stripe-checkout'),
    path('stripe/webhook/', StripeWebhookAPIView.as_view(), name='stripe-webhook'),
    path('current/subscription/', CurrentSubscriptionPlanAPIView.as_view(), name='current-subscription'),
    path('cancel/subscription/', CancelSubscriptionAPIView.as_view(), name='cancel-subscription'),
]
