from apps.system_setting.models import AboutSystem, SMTPSetting
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.user.authentication import JWTAuthentication
from apps.system_setting.serializers import AboutSystemSerializer, ContactInformationSerializer, ContactUsSerializer
from apps.utils.helpers import success, error
from apps.utils.tasks import dispatch_email_task
from django.conf import settings
# Create your views here.   

class AboutSystemAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):

        about_system = AboutSystem.objects.first()
   
        if about_system:
            serializer = AboutSystemSerializer(about_system)
            return success(serializer.data, "About system retrieved successfully.",200)
        return error(message="About system not found.", errors=None, status_code=404)


class ContactInformationAPIView(APIView):
    
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        about_system = AboutSystem.objects.first()
        if not about_system:
            return error(message="Contact information not found.", errors=None, status_code=404)

        serializer = ContactInformationSerializer(about_system)
        return success(serializer.data, "Contact information retrieved successfully.", 200)


class ContactUsAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ContactUsSerializer(data=request.data)
        if not serializer.is_valid():
            return error(message="Invalid contact form data.", errors=serializer.errors)

        contact = serializer.save()

        about_system = AboutSystem.objects.first()
        notify_email = None
        if about_system:
            notify_email = about_system.contact_notification_email or about_system.email
        if not notify_email:
            notify_email = getattr(settings, "EMAIL_HOST_USER", None)

        if notify_email:
            subject = f"New Contact Us Request - {contact.get_purpose_display()}"
            body = (
                "A new contact request has been submitted.\n\n"
                f"Name: {contact.name}\n"
                f"Email: {contact.email}\n"
                f"Purpose: {contact.get_purpose_display()}\n"
                f"Message:\n{contact.message}\n"
            )
            smtp_setting = SMTPSetting.objects.filter(is_active=True).first()
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)
            if smtp_setting and smtp_setting.sender_email:
                from_email = smtp_setting.sender_email

            email_sent = dispatch_email_task(
                subject=subject,
                body=body,
                to_emails=[notify_email],
                from_email=from_email,
            )

            if not email_sent:
                return error(
                    message="Contact request was saved, but email notification failed.",
                    errors=None,
                    status_code=500,
                )

        return success(
            data=ContactUsSerializer(contact).data,
            message="Contact request submitted successfully.",
            status_code=201,
        )
