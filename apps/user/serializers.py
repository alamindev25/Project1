
from apps.system_setting.models import AboutSystem
from .models import User, UserProfile, OTP
from rest_framework import  serializers
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from django.utils.timezone import timedelta
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from .utils import generate_otp
from django.utils import timezone
from apps.utils.helpers import success, error
from apps.utils.tasks import dispatch_email_task
from django.template.loader import render_to_string
from .utils import get_user_agent_hash, get_cloudinary_url

class CustomRefreshToken(RefreshToken):

    @classmethod
    def for_user(cls, user, remember_me=False, user_agent_hash=None):
        token = super().for_user(user)

        token["user_id"] = user.id
        token["role"] = user.role
        token["uah"] = user_agent_hash

        if remember_me:
            token.set_exp(lifetime=settings.SIMPLE_JWT["REMEMBER_ME_REFRESH_LIFETIME"])
        else:
            token.set_exp(lifetime=settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"])

        return token

# Signup
class SignUpSerializer(serializers.ModelSerializer):

    # user
    full_name = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    term_and_condition_accepted = serializers.BooleanField(required=False, default=False)
    privacy_policy_accepted = serializers.BooleanField(required=True)

    # user profile
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    avatar = serializers.ImageField(write_only=True, required=False)
    gender = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    dob = serializers.DateField(write_only=True, required=False, allow_null=True)
    purpose = serializers.CharField(write_only=True)

    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'full_name',
            'email',
            'password',
            'term_and_condition_accepted',
            'privacy_policy_accepted',

            'purpose',
            'role',
            'phone',
            'avatar',
            'gender',
            'dob',
        ]

    def validate(self, attrs):
        full_name = (attrs.get('full_name') or '').strip()
        email = attrs.get('email')
        password = attrs.get('password')
        privacy_policy_accepted = attrs.get('privacy_policy_accepted')
        purpose = (attrs.get('purpose') or '').strip()

        # full_name required
        if not full_name:
            raise serializers.ValidationError({'full_name': 'Full name is required.'})
        
        # Check email already exists
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'User with this email already exists.'})
        
        # Validate password
        if not password:
            raise serializers.ValidationError({'password': 'Password is required.'})

        # Check privacy policy accepted
        if privacy_policy_accepted is not True:
            raise serializers.ValidationError({
                'privacy_policy_accepted': 'You must accept the privacy policy to proceed.'
            })

        allowed_purposes = {'signup'}
        if purpose and purpose not in allowed_purposes:
            raise serializers.ValidationError({'purpose': 'Invalid purpose.'})

        return attrs

    def create(self, validated_data):
        full_name = (validated_data.pop('full_name', '') or '').strip()
        email = validated_data.pop('email')
        password = validated_data.pop('password')

        avatar = validated_data.pop('avatar', None)
        gender = validated_data.pop('gender', None)
        dob = validated_data.pop('dob', None)
        phone = validated_data.pop('phone', None)
        purpose = validated_data.pop('purpose', None)
        privacy_policy_accepted = validated_data.get('privacy_policy_accepted', False)
        terms_accepted = validated_data.get('term_and_condition_accepted', privacy_policy_accepted)

        # Split full_name -> first_name, last_name
        parts = full_name.split()
        first_name = " ".join(parts[:-1]) if len(parts) > 1 else (parts[0] if parts else "")
        last_name = parts[-1] if len(parts) > 1 else ""
        
        # Create user
        user = User.objects.create_user(
            email=email,
            password=password,
            term_and_condition_accepted=terms_accepted,
            privacy_policy_accepted=privacy_policy_accepted,
        )

        if avatar:
            user.avatar = avatar
            user.save(update_fields=['avatar'])

        # Create profile
        UserProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            dob=dob,
            phone=phone,
            accepted_terms=terms_accepted,
        )

        # OTP create
        otp_code = generate_otp(6)
        otp_hashed = make_password(otp_code)
        expires_at = timezone.now() + timedelta(minutes=3)

        otp_purpose = purpose or 'signup'

        OTP.objects.update_or_create(
            user=user,
            purpose=otp_purpose,
            defaults={
                'otp': otp_hashed,
                'is_verify': False,
                'purpose': otp_purpose,
                'created_at': timezone.now(),
                'expires_at': expires_at
            }
        )

        system_info = AboutSystem.objects.first()
        html_content = render_to_string(
            'email/signup_otp_verification_template.html',
            {'otp_code': otp_code, 'system_info': system_info}
        )

        dispatch_email_task(
            subject='Verification OTP',
            body=f'Your OTP is {otp_code}. Expire in 3 minutes.',
            to_emails=[user.email],
            from_email=settings.EMAIL_HOST_USER,
            html_body=html_content
        )

        return user

    def to_representation(self, instance):
        request = self.context.get('request')
        user_agent_hash = get_user_agent_hash(request) if request else None

        refresh = CustomRefreshToken.for_user(instance, user_agent_hash=user_agent_hash)

        return {
            'user': {
                'id': instance.id,
                'email': instance.email,
                'message': 'User created successfully. Please verify OTP sent to your email to activate your account.',
                'role': instance.role,
            },
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        }

# Signin
class SignInSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    refresh_token = serializers.CharField(read_only=True)
    access_token = serializers.CharField(read_only=True)
    remember_me = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        password = attrs.get('password')
        user = User.objects.filter(email=attrs['email']).first()
        if not user:
           raise serializers.ValidationError({'email': 'User with this email does not exist.'})
        if not user.check_password(password):
            raise serializers.ValidationError({'password': 'Invalid password.'})
        
        #OTP verification check
        if not user.is_verified: 
            raise serializers.ValidationError({
            'otp': 'Your account is not verified. Please verify OTP first.'
        })

        self.user = user
        return attrs
    

    def to_representation(self, instance):
        user = self.user
        request = self.context.get('request')

        user_agent_hash = get_user_agent_hash(request) if request else None

        refresh = CustomRefreshToken.for_user(
            user,
            user_agent_hash=user_agent_hash
        )

        return {
            'user': {
                'id': user.id,
                'email': user.email,
                'avatar': get_cloudinary_url(user.avatar) if user.avatar else None,
                'role': user.role,
            },
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

# SignOut
class SignOutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        self.refresh_token = attrs.get('refresh_token')
        return attrs
    
    def save(self, **kwargs):
        try:
            token = RefreshToken(self.refresh_token)
            token.blacklist()
        except Exception as e:
            return ValidationError({'error': str(e)})

# Change Password
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['old_password', 'new_password', 'confirm_password']

    def validate(self, attrs):
        
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        user = self.context['request'].user
        if not user:
            raise ValidationError({'error': 'User not found.'})
        
        if not user.check_password(old_password):
            raise ValidationError({'error': 'Old password is incorrect.'})
        
        if new_password != confirm_password:
            raise ValidationError({'error': 'New password and confirm password is not match.'})
        
        if old_password == new_password:
            raise ValidationError({'error': 'The new password is not the same as the old password.'})
        
        try:
            validate_password(new_password)
        except Exception as e:
            raise ValidationError({'error': str(e.messages)})
        
        self.user = user
        return attrs
    
    def save(self):
        new_password = self.validated_data['new_password']
        user = self.user
        user.set_password(new_password)
        user.save()
        return user

# Forgot Password (OTP Send)
class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.CharField()

    def validate(self, attrs):
        try:
            user = User.objects.get(email=attrs['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({'error': 'User not found.'})
        
        otp_code = generate_otp(6)
        otp_hashed = make_password(otp_code)
        purpose = attrs['purpose']

        expires_at = timezone.now() + timedelta(minutes=3)

        OTP.objects.update_or_create(
            user=user,
            purpose=purpose,
            defaults={
                'otp': otp_hashed,
                'is_verify': False,
                'purpose': purpose,
                'created_at': timezone.now(),
                'expires_at': expires_at,
            },
        )
        
        system_info = AboutSystem.objects.first()
        html_content = render_to_string('email/forgetpass_otp_verification_template.html', {'otp_code': otp_code, 'system_info': system_info})

        email_sent = dispatch_email_task(
            subject='Verification OTP',
            body=f'Your OTP is {otp_code}. Expire in 3 minutes.',
            to_emails=[user.email],
            from_email=settings.EMAIL_HOST_USER,
            html_body=html_content,
        )
        if not email_sent:
            raise serializers.ValidationError("SMTP NOT VALID!")
        return attrs

# Reset Password (OTP Verify and Reset)
class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data['email']
        purpose = data['purpose']
        new_password = data['new_password']
        confirm_password = data['confirm_password']

        try:
            user = User.objects.get(email=email)
            otp_obj = OTP.objects.get(user=user, purpose=purpose)
        except (User.DoesNotExist, OTP.DoesNotExist):
            raise serializers.ValidationError({'error': "Invalid credentials or OTP."})

        if otp_obj.is_expired():
            otp_obj.delete()
            raise serializers.ValidationError({'error': "OTP has expired."})
        
        if not otp_obj.is_verify:
            raise serializers.ValidationError({'error': 'OTP not verified yet. Please verify OTP first.'})

        if new_password != confirm_password:
            raise serializers.ValidationError({'error': "Passwords do not match."})

        try:
            validate_password(new_password, user)
        except serializers.ValidationError as e:
            raise serializers.ValidationError({'error': str(e.messages)})

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        new_password = self.validated_data['new_password']
        user.set_password(new_password)
        user.save()
        OTP.objects.filter(user=user, purpose=self.validated_data['purpose']).delete()

# Resend OTP
class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get('email')
        purpose = attrs.get('purpose')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as e:
            raise serializers.ValidationError({'error': 'User not found.'})

        otp_code = generate_otp(6)
        otp_hashed = make_password(otp_code)
        purpose = attrs['purpose']

        expires_at = timezone.now() + timedelta(minutes=3)

        OTP.objects.update_or_create(
            user=user,
            purpose=purpose,
            defaults={
                'otp': otp_hashed,
                'is_verify': False,
                'purpose': purpose,
                'created_at': timezone.now(),
                'expires_at': expires_at,
            },
        )

        system_info = AboutSystem.objects.first()
        html_content = render_to_string('email/forgetpass_otp_verification_template.html', {'otp_code': otp_code, 'system_info': system_info})

        email_sent = dispatch_email_task(
            subject='Verification OTP',
            body=f'Your OTP is {otp_code}. Expire in 3 minutes.',
            to_emails=[user.email],
            from_email=settings.EMAIL_HOST_USER,
            html_body=html_content,
        )
        if not email_sent:
            raise serializers.ValidationError("SMTP NOT VALID!")
        return attrs

# Verify OTP (with purpose)
class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=4, max_length=6)
    purpose = serializers.CharField()

    PURPOSE_ALIASES = {
        'account_create': 'signup',
        'signup': 'signup',
        'password_reset': 'password_reset',
        'login': 'login',
        'delete_account': 'delete_account',
    }

    def validate(self, data):
        email = data.get("email")
        otp_input = str(data.get("otp") or "").strip()
        raw_purpose = str(data.get("purpose") or "").strip().lower()
        purpose = self.PURPOSE_ALIASES.get(raw_purpose, raw_purpose)

        if not otp_input.isdigit() or len(otp_input) not in (4, 6):
            raise serializers.ValidationError({'error': "OTP must be a 4 or 6-digit code."})

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'error': "Invalid email."})

        purpose_filters = [purpose]
        if purpose == 'signup':
            purpose_filters.append('account_create')

        otp_obj = OTP.objects.filter(user=user, purpose__in=purpose_filters).order_by('-created_at').first()
        if not otp_obj:
            available_purposes = list(
                OTP.objects.filter(user=user, is_verify=False)
                .values_list('purpose', flat=True)
                .distinct()
            )
            if available_purposes:
                raise serializers.ValidationError({
                    'error': f"OTP পাওয়া গেছে কিন্তু purpose mismatch. Available purpose: {', '.join(available_purposes)}"
                })
            raise serializers.ValidationError({'error': "OTP not found. Please request a new one."})

        if otp_obj.is_verify:
            raise serializers.ValidationError({'error': "OTP already vrified."})

        if otp_obj.is_expired():
            otp_obj.delete()
            raise serializers.ValidationError({'error': "OTP expired. Please request a new one."})

        if not otp_obj.check_otp(otp_input):
            otp_obj.attempts += 1
            if otp_obj.attempts >= 3:
                otp_obj.delete()
                raise serializers.ValidationError({'error': "Too many incorrect attempts. Please request a new one."})
            otp_obj.save()
            raise serializers.ValidationError({'error': f"Incorrect OTP. Attempt {otp_obj.attempts}/3."})

        data['purpose'] = purpose
        self.user = user
        self.otp_obj = otp_obj
        return data

    def save(self):
        # OTP verified
        self.otp_obj.is_verify = True
        self.otp_obj.attempts = 0
        self.otp_obj.save()

        # Handle different purposes
        if self.otp_obj.purpose == 'signup':
            self.user.is_verified = True
            self.user.save()
            
        elif self.otp_obj.purpose == 'password_reset':
            return {
                'id': self.user.id,
                'email': self.user.email,
                'message': 'OTP verified successfully.',
                'verified': True
            }

        # Generate tokens for signup and other purposes
        request = self.context.get('request')
        user_agent_hash = get_user_agent_hash(request) if request else None
        refresh = CustomRefreshToken.for_user(
            self.user,
            remember_me=False,
            user_agent_hash=user_agent_hash
        )
        
        return {
            'user': {
            'id': self.user.id,
            'email': self.user.email,
            'avatar': get_cloudinary_url(self.user.avatar) if self.user.avatar else None,
            'is_verified': self.user.is_verified,
        },
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh)
    }

# Profile Update Avatar
class UpdateProfileAvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['avatar']

    def validate_avatar(self, avatar):
        max_size_mb = getattr(settings, "MAX_AVATAR_UPLOAD_SIZE_MB", 5)
        max_size_bytes = int(max_size_mb * 1024 * 1024)

        if avatar and getattr(avatar, "size", 0) > max_size_bytes:
            raise serializers.ValidationError(
                f"Image is too large. Maximum allowed size is {max_size_mb} MB."
            )

        return avatar

    def update(self, instance, validated_data):
        avatar = validated_data.get('avatar', None)
        if avatar is not None:
            instance.avatar = avatar
            instance.save(update_fields=['avatar'])
        return instance

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['avatar'] = get_cloudinary_url(instance.avatar) if instance.avatar else None
        return ret

#user
class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "is_staff",
            "is_active",
            "date_joined",
            "profile",
        ]

# UserProfile
class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(source='user.email', required=False)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "address",
            "linkedin",
            "github",
            "twitter",
        ]

    def to_representation(self, instance):
        # Compute full name and preserve the order specified in Meta.fields
        computed_full_name = f"{instance.first_name} {instance.last_name}".strip()
        ret = super().to_representation(instance)

        ordered = {}
        for field in self.Meta.fields:
            if field == 'full_name':
                ordered['full_name'] = computed_full_name
            else:
                ordered[field] = ret.get(field)
        return ordered

    def _split_full_name(self, full_name):
        parts = (full_name or '').strip().split()
        first_name = " ".join(parts[:-1]) if len(parts) > 1 else (parts[0] if parts else "")
        last_name = parts[-1] if len(parts) > 1 else ""
        return first_name, last_name

    def create(self, validated_data):
        full_name = validated_data.pop('full_name', None)
        if full_name is not None:
            first_name, last_name = self._split_full_name(full_name)
            validated_data['first_name'] = first_name
            validated_data['last_name'] = last_name
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Update first/last name when full_name is supplied, then update other fields
        full_name = validated_data.pop('full_name', None)
        user_data = validated_data.pop('user', None)

        if user_data and 'email' in user_data:
            email = (user_data.get('email') or '').strip().lower()
            if User.objects.filter(email__iexact=email).exclude(pk=instance.user_id).exists():
                raise serializers.ValidationError({'email': 'User with this email already exists.'})
            instance.user.email = email
            instance.user.save(update_fields=['email'])

        if full_name is not None:
            first_name, last_name = self._split_full_name(full_name)
            instance.first_name = first_name
            instance.last_name = last_name
            instance.save(update_fields=['first_name', 'last_name'])
        return super().update(instance, validated_data)

# Get UserProfile
class UserProfileGetSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField(source='user.avatar')
    email = serializers.EmailField(source='user.email', read_only=True)
    name = serializers.SerializerMethodField()
    joining_date = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "avatar",
            "name",
            "email",
            "phone",
            "address",
            "joining_date",
            "linkedin",
            "github",
            "twitter",
        ]

    def get_avatar(self, obj):
        if obj.user.avatar:
            return get_cloudinary_url(obj.user.avatar)
        return None

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def get_joining_date(self, obj):
        if obj.user.created_at:
            return obj.user.created_at.strftime("%d %B %Y")
        return None


# Delete Account
class DeleteUserSerializer(serializers.Serializer):
   
    
    def delete(self):
        user = self.context['request'].user
        if not user or not user.is_authenticated:
            raise serializers.ValidationError({'error': 'User not authenticated.'})
        
        user_email = user.email
        user.delete()
        return {'message': f'Account {user_email} has been deleted successfully.'}
