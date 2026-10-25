from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.user.models import User
from apps.user.serializers import UpdateProfileAvatarSerializer


class UpdateProfileAvatarSerializerTests(TestCase):
    def test_validate_avatar_rejects_large_files(self):
        serializer = UpdateProfileAvatarSerializer()
        oversized_avatar = SimpleNamespace(size=6 * 1024 * 1024)

        with self.assertRaisesMessage(ValidationError, "Image is too large"):
            serializer.validate_avatar(oversized_avatar)


class UpdateProfileAvatarViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="avatar@test.com", password="password123")
        self.url = reverse("avatar-update")
        self.client.force_authenticate(user=self.user)

    @patch("apps.user.views.UpdateProfileAvatarSerializer.save", side_effect=Exception("upload backend error"))
    def test_avatar_update_returns_safe_error_when_upload_backend_fails(self, mocked_save):
        response = self.client.post(self.url, data={}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data.get("success"))
        self.assertIn("avatar", response.data.get("errors", {}))
        mocked_save.assert_called_once()
