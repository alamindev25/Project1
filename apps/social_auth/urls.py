from django.urls import path
from .views import GoogleLoginView

urlpatterns = [
    path('google-auth/', GoogleLoginView.as_view(), name='google-auth'),
]
