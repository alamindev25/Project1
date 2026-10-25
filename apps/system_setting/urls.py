from django.urls import path
from django.conf.urls.static import static
from project import settings

from .views import (
    AboutSystemAPIView,
    ContactInformationAPIView,
    ContactUsAPIView,
)

urlpatterns = [
    path("about-system/", AboutSystemAPIView.as_view(), name="about_system"),
    path("contact-information/", ContactInformationAPIView.as_view(), name="contact-information"),
    path("contact-us/", ContactUsAPIView.as_view(), name="contact-us"),
]

