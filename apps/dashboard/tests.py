import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test.client import RequestFactory
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cms.models import CMS
from apps.dashboard.models import DocumentTemplate, DocumentType, GeneratedDocument, TemplateCategory
from apps.dashboard.views import DocumentHistoryByCategoryAPIView, _build_landing_overview_data
from apps.system_setting.models import AboutSystem, LandingPageSection, LandingPreviewSample


class LandingOverviewPreviewSampleTests(TestCase):
	def _image_file(self, name):
		return SimpleUploadedFile(name, b"sample-image-bytes", content_type="image/png")

	def test_preview_samples_uses_cms_preview_images(self):
		factory = RequestFactory()
		request = factory.get("/api/dashboard/landing/overview/")

		with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			LandingPageSection.objects.create(
				page="landing",
				section_key="preview_samples",
				title="Landing Page Section Preview",
				order=0,
				is_active=True,
			)

			LandingPreviewSample.objects.create(
				title="Legacy Preview",
				image=self._image_file("legacy.png"),
				order=1,
				is_active=True,
			)

			CMS.objects.create(
				page="landing",
				section="preview_samples",
				title="Preview Samples",
				status="active",
				preview_image_1=self._image_file("cms-1.png"),
				preview_image_2=self._image_file("cms-2.png"),
				preview_image_3=self._image_file("cms-3.png"),
			)

			data = _build_landing_overview_data(request)

		preview_section = data["landing_page"]["sections"]["preview_samples"]
		self.assertEqual(preview_section["title"], "Preview Samples")
		self.assertEqual(
			[item["image"] for item in preview_section["items"]],
			[
				"http://testserver/media/cms/preview_samples/cms-1.png",
				"http://testserver/media/cms/preview_samples/cms-2.png",
				"http://testserver/media/cms/preview_samples/cms-3.png",
			],
		)


class LandingOverviewCmsMediaTests(TestCase):
	def _image_file(self, name):
		return SimpleUploadedFile(name, b"sample-image-bytes", content_type="image/png")

	def _pdf_file(self, name):
		return SimpleUploadedFile(name, b"sample-pdf-bytes", content_type="application/pdf")

	def test_watch_video_uses_video_link(self):
		factory = RequestFactory()
		request = factory.get("/api/dashboard/landing/overview/")

		with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			CMS.objects.create(
				page="landing",
				section="watch_video",
				title="Updated Title",
				sub_title="30 second demo",
				status="active",
				background_image=self._image_file("watch-video.png"),
				video_link="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
			)

			data = _build_landing_overview_data(request)

		watch_video = data["landing_page"]["sections"]["watch_video"]
		self.assertEqual(watch_video["video_url"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
		self.assertEqual(watch_video["image"], "http://testserver/media/cms/background/watch-video.png")

	def test_cms_media_urls_are_absolute(self):
		factory = RequestFactory()
		request = factory.get("/api/dashboard/landing/overview/")

		with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			CMS.objects.create(
				page="landing",
				section="faq",
				title="FAQ",
				status="active",
				background_image=self._image_file("faq.png"),
				file_url=self._pdf_file("faq.pdf"),
			)

			data = _build_landing_overview_data(request)

		faq_section = data["landing_page"]["sections"]["faq"]
		self.assertEqual(faq_section["image"], "http://testserver/media/cms/background/faq.png")
		self.assertEqual(faq_section["file_url"], "http://testserver/media/cms/files/faq.pdf")


class LandingOverviewContactInformationTests(TestCase):
	def test_contact_information_uses_about_system_values(self):
		factory = RequestFactory()
		request = factory.get("/api/dashboard/landing/overview/")

		AboutSystem.objects.create(
			name="Formexl",
			title="Formexl",
			email="admin@formexl.com",
			contact_phone="+880 1234 567890",
			office_address="Dhaka\nBangladesh",
			copyright="2026",
			description="System details",
		)

		data = _build_landing_overview_data(request)
		contact = data["landing_page"]["contact_information"]

		self.assertEqual(contact["email"], "admin@formexl.com")
		self.assertEqual(contact["phone"], "+880 1234 567890")
		self.assertEqual(contact["phone_link"], "tel:+8801234567890")
		self.assertEqual(contact["address"], "Dhaka\nBangladesh")
		self.assertEqual(contact["address_lines"], ["Dhaka", "Bangladesh"])


class DocumentHistoryCategoryFilterTests(TestCase):
	def test_category_name_filter_returns_only_matching_documents(self):
		user_model = get_user_model()
		user = user_model.objects.create_user(email="history@example.com", password="password123")

		legal_category = TemplateCategory.objects.create(name="Legal")
		billing_category = TemplateCategory.objects.create(name="Billing")

		legal_type = DocumentType.objects.create(category=legal_category, name="NDA")
		billing_type = DocumentType.objects.create(category=billing_category, name="Invoice")

		legal_template = DocumentTemplate.objects.create(document_type=legal_type, name="NDA Template")
		billing_template = DocumentTemplate.objects.create(document_type=billing_type, name="Invoice Template")

		legal_document = GeneratedDocument.objects.create(
			user=user,
			category=legal_category,
			document_type=legal_type,
			template=legal_template,
			name="Legal Doc",
		)
		GeneratedDocument.objects.create(
			user=user,
			category=billing_category,
			document_type=billing_type,
			template=billing_template,
			name="Billing Doc",
		)

		factory = APIRequestFactory()
		request = factory.get("/api/dashboard/documents/history/by-category/", {"category_name": "Legal"})
		force_authenticate(request, user=user)

		response = DocumentHistoryByCategoryAPIView.as_view()(request)

		self.assertEqual(response.status_code, 200)
		items = response.data["data"]["items"]
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["document_id"], legal_document.id)
		self.assertEqual(items[0]["title"], "Legal Doc")
		self.assertNotIn("filters", response.data["data"])
