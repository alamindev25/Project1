from django.urls import path

from apps.cms.views import (
    AboutUsAPIView,
    CMSPageBySlugAPIView,
    PrivacyPolicyAPIView,
    TermsAndConditionsAPIView,
)


urlpatterns = [
    path("cms/about-us/", AboutUsAPIView.as_view(), name="cms-about-us"),
    path("cms/privacy-policy/", PrivacyPolicyAPIView.as_view(), name="cms-privacy-policy"),
    path("cms/terms-and-conditions/", TermsAndConditionsAPIView.as_view(), name="cms-terms-and-conditions"),
    path("cms/pages/<slug:slug>/", CMSPageBySlugAPIView.as_view(), name="cms-page-by-slug"),
]
