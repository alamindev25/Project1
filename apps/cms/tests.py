from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cms.models import Page
from apps.system_setting.models import AboutSystem


class CMSPublicAPITests(APITestCase):
	def setUp(self):
		AboutSystem.objects.create(
			name="FORMEXL",
			title="About FORMEXL",
			email="info@example.com",
			copyright="2026",
			description="FORMEXL helps generate business documents.",
		)

		Page.objects.create(
			title="About Us",
			slug="about-us",
			content="About us content",
			type=Page.Type.ABOUT_US,
			status=True,
		)

		Page.objects.create(
			title="Privacy Policy",
			slug="privacy-policy",
			content="Privacy policy content",
			type=Page.Type.PRIVACY_POLICY,
			status=True,
		)

		Page.objects.create(
			title="Terms and Conditions",
			slug="terms-and-conditions",
			content="Terms content",
			type=Page.Type.TERMS_AND_CONDITIONS,
			status=True,
		)

	def test_about_us_api_success(self):
		url = reverse("cms-about-us")
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data["success"])
		self.assertEqual(response.data["data"]["slug"], "about-us")
		self.assertIn("image_url", response.data["data"])

	def test_privacy_policy_api_success(self):
		url = reverse("cms-privacy-policy")
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["data"]["slug"], "privacy-policy")

	def test_terms_and_conditions_api_success(self):
		url = reverse("cms-terms-and-conditions")
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["data"]["slug"], "terms-and-conditions")

	def test_cms_page_by_slug_api_success(self):
		url = reverse("cms-page-by-slug", kwargs={"slug": "privacy-policy"})
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["data"]["type"], Page.Type.PRIVACY_POLICY)

	def test_cms_page_by_slug_api_not_found(self):
		url = reverse("cms-page-by-slug", kwargs={"slug": "not-found"})
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertFalse(response.data["success"])
