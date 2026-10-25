# Google Signin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework_simplejwt.tokens import RefreshToken

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from apps.user.models import UserProfile


User = get_user_model()


class GoogleLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        token = request.data.get("id_token")

        if not token:
            return Response(
                {"message": "id_token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Quick check: must be JWT (3 parts)
        if token.count(".") != 2:
            return Response(
                {
                    "message": (
                        "Invalid token format. "
                        "Send Google ID token (JWT), not access_token."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify Google ID token (NOT Firebase)
        try:
            decoded = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=settings.GOOGLE_OAUTH_AUD_ID,  # must match token's aud
            )
        except Exception as e:
            return Response(
                {
                    "message": "Invalid Google ID token",
                    "error": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract fields
        email = decoded.get("email")
        name = decoded.get("name") or ""

        if not email:
            return Response(
                {"message": "No email in token"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create / Get Django user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "is_verified": True,  # Google users are automatically verified
                "term_and_condition_accepted": True,
                "privacy_policy_accepted": True
            }
        )

        # Handle user profile with name
        if name:
            # Split name into first and last name
            name_parts = name.strip().split()
            first_name = name_parts[0] if name_parts else ""
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            # Create or update user profile
            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "accepted_terms": True
                }
            )
            
            # Update profile if name changed
            if not profile_created:
                profile.first_name = first_name
                profile.last_name = last_name
                profile.save(update_fields=["first_name", "last_name"])

        # Issue JWT (SimpleJWT)
        refresh_token = RefreshToken.for_user(user)

        return Response({
            "status": "success",
            "message": "Signin successful.",
            "data": {
                'id': user.id,
                'email': user.email,
                'avatar': user.avatar.url if user.avatar else None,
                'role': user.role,
            },
            "access_token": str(refresh_token.access_token),
            "refresh_token": str(refresh_token),
        }, status=status.HTTP_200_OK)
