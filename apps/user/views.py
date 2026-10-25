from .models import UserProfile
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .authentication import CookieJWTAuthentication
from rest_framework.validators import ValidationError
from rest_framework.response import Response

# Use hybrid response utility
from .utils import create_hybrid_auth_response

from .serializers import (
    SignUpSerializer,
    SignInSerializer,
    SignOutSerializer,
    ChangePasswordSerializer,
    SendOTPSerializer,
    ResendOTPSerializer,
    UserProfileGetSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
    UpdateProfileAvatarSerializer,
    UserProfileSerializer,
    DeleteUserSerializer,
)

from apps.utils.helpers import success, error


# Singup
class SignUpView(APIView):
    permission_classes = []

    def post(self, request):

        serializer = SignUpSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            result = serializer.data
            return success(data=result['user'], message="Signup successful.", status_code=status.HTTP_201_CREATED)
        raise ValidationError(serializer.errors)

# Signin
class SignInView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = SignInSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.data
            
            
            return success(data=result, message="Login successful.")
        raise ValidationError(serializer.errors)

# Signout
class SignOutView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        serializer = SignOutSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success(message="Logout successful.")
        raise ValidationError(serializer.errors)

# Change Password
class ChangePasswordView(APIView):
    
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return success(message="Password change successfully.", status_code=status.HTTP_200_OK)
        raise ValidationError(serializer.errors)

# Forgot Password (OTP Send)
class SendOTPView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            return success(message="OTP send to mail successfully.")
        errors = serializer.errors
        if "email" in errors:
            errors["error"] = errors.pop("email")
        raise ValidationError(errors)

# Reset Password (OTP Verify and Reset)
class ResetPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success(message="Password reset successfully.")
        errors = serializer.errors
        if "non_field_errors" in errors:
            errors["error"] = errors.pop("non_field_errors")
        return error(message="Password reset failed.", errors=errors)

# Resend OTP
class ResendOTPView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            return success(message="OTP send to mail successfully.")
        errors = serializer.errors
        if "email" in errors:
            errors["error"] = errors.pop("email")
        raise ValidationError(errors)

# Verify OTP (with purpose)
class VerifyOTPView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.save()
            data = result

            return success(data=data, message="OTP verified successfully.")
        
        # Extract error message from serializer errors
        error_message = ""
        if 'error' in serializer.errors:
            error_message = serializer.errors['error'][0] if isinstance(serializer.errors['error'], list) else serializer.errors['error']
        else:
            # Fallback to first error if 'error' key doesn't exist
            first_key = next(iter(serializer.errors))
            error_message = serializer.errors[first_key][0] if isinstance(serializer.errors[first_key], list) else serializer.errors[first_key]
        
        return error(message=error_message)

# Profile Views
class UpdataProfileAvatarView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        user = request.user

        serializer = UpdateProfileAvatarSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                serializer.save()
            except Exception as exc:
                return error(
                    message="Profile avatar update failed.",
                    errors={"avatar": [f"Avatar upload failed: {str(exc)}"]},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            avatar_url = serializer.data.get('avatar')
            return success(data=avatar_url, message="Profile avatar update successfully.")
        return error(message="Profile avatar update failed.", errors=serializer.errors)

# Profile Update
class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def put(self, request):
        user = request.user

        try:
            userProfile = UserProfile.objects.select_related('user').get(user=user)
        except UserProfile.DoesNotExist:
            return error(message="User not found.", status_code=status.HTTP_400_BAD_REQUEST, errors=[])

        serializer = UserProfileSerializer(userProfile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success(data=serializer.data, message="Profile update successfully.")
        return error(message="Profile update failed.", errors=serializer.errors)

# Profile Get
class ProfileGet(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            profile = UserProfile.objects.select_related('user').get(user=user)
        except UserProfile.DoesNotExist:
            return error(message="User not found.")
        
        serializer = UserProfileGetSerializer(profile)
        return success(data=serializer.data, message="Profile fetched successfully.")

# Hybrid Token Refresh View
class CookieTokenRefreshView(TokenRefreshView):
    """
    Hybrid Token Refresh View
    
    Supports both Web and Mobile clients:
    - Web: Reads refresh token from HttpOnly cookie, returns new tokens in cookies
    - Mobile: Reads refresh token from request body, returns new tokens in response body
    """
    
    def post(self, request, *args, **kwargs):
        # Inject refresh token from cookie into data if not present (for web clients)
        data = request.data.copy()
        if 'refresh' not in data and 'refresh_token' in request.COOKIES:
            data['refresh'] = request.COOKIES['refresh_token']
        
        serializer = self.get_serializer(data=data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        token_data = serializer.validated_data
        
        # Use hybrid response utility
        from .utils import create_hybrid_refresh_response
        
        tokens = {
            'access': token_data['access'],
            'refresh': token_data.get('refresh')  # May not exist if rotation is disabled
        }
        
        response = create_hybrid_refresh_response(
            tokens=tokens,
            request=request,
            message="Token refreshed successfully.",
            status_code=status.HTTP_200_OK
        )
        
        return response

# Hybrid Token Verify View
class CookieTokenVerifyView(TokenVerifyView):
    """
    Hybrid Token Verify View
    
    Supports both Web and Mobile clients:
    - Web: Reads access token from HttpOnly cookie
    - Mobile: Reads token from request body
    """
    
    def post(self, request, *args, **kwargs):
        # Inject access token from cookie into data if not present (for web clients)
        data = request.data.copy()
        if 'token' not in data and 'access_token' in request.COOKIES:
            data['token'] = request.COOKIES['access_token']
        
        serializer = self.get_serializer(data=data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])
        
        return success(data=[], message="Token is valid.", status_code=status.HTTP_200_OK)


# Delete Account
class DeleteAccountView(APIView):
    """
    Delete authenticated user account.
    Requires JWT authentication.
    
    DELETE /api/user/delete-account/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request):
        serializer = DeleteUserSerializer(context={'request': request})
        result = serializer.delete()
        return success(
            message=result['message'],
            status_code=status.HTTP_200_OK
        )
