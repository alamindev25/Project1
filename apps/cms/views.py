from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.cms.models import Page
from apps.cms.serializers import AboutUsSerializer, PageSerializer
from apps.system_setting.models import AboutSystem
from apps.utils.helpers import error, success


class AboutUsAPIView(APIView):
	permission_classes = [AllowAny]
	authentication_classes = []

	def get(self, request):
		page = Page.objects.filter(type=Page.Type.ABOUT_US, status=True).first()
		if page:
			serializer = PageSerializer(page, context={"request": request})
			return success(serializer.data, "About us retrieved successfully.", 200)

		about_system = AboutSystem.objects.first()
		if not about_system:
			return error(message="About us data not found.", errors=None, status_code=404)

		serializer = AboutUsSerializer(about_system)
		return success(serializer.data, "About us retrieved successfully.", 200)


class PrivacyPolicyAPIView(APIView):
	permission_classes = [AllowAny]
	authentication_classes = []

	def get(self, request):
		page = Page.objects.filter(type=Page.Type.PRIVACY_POLICY, status=True).first()
		if not page:
			return error(message="Privacy policy not found.", errors=None, status_code=404)

		serializer = PageSerializer(page, context={"request": request})
		return success(serializer.data, "Privacy policy retrieved successfully.", 200)


class TermsAndConditionsAPIView(APIView):
	permission_classes = [AllowAny]
	authentication_classes = []

	def get(self, request):
		page = Page.objects.filter(type=Page.Type.TERMS_AND_CONDITIONS, status=True).first()
		if not page:
			return error(message="Terms and conditions not found.", errors=None, status_code=404)

		serializer = PageSerializer(page, context={"request": request})
		return success(serializer.data, "Terms and conditions retrieved successfully.", 200)


class CMSPageBySlugAPIView(APIView):
	permission_classes = [AllowAny]
	authentication_classes = []

	def get(self, request, slug):
		page = Page.objects.filter(slug=slug, status=True).first()
		if not page:
			return error(message="Page not found.", errors=None, status_code=404)

		serializer = PageSerializer(page, context={"request": request})
		return success(serializer.data, "Page retrieved successfully.", 200)
