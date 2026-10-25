from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.user.models import User
from apps.dashboard.models import GeneratedDocument, SignatureRequest, SignatureAudit
import os
from django.conf import settings


class SignatureFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(email="owner@example.com", password="pass1234")
        self.recipient_email = "recipient@example.com"

        self.document = GeneratedDocument.objects.create(
            user=self.owner,
            name="Test Doc",
            form_data={"client_name": "ACME"},
            rendered_content="This is a test document for [Client Name].",
        )

    def test_send_and_sign_flow(self):
        # Owner sends signature request
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(f"/api/documents/{self.document.id}/send-signature/", {
            "recipient_email": self.recipient_email,
            "recipient_name": "Recipient",
            "message": "Please sign",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        data = resp.json().get("data") or resp.json()
        created = data.get("created_requests")
        self.assertEqual(len(created), 2)
        # client request is first
        client_token = created[0].get("token")
        owner_token = created[1].get("token")
        self.assertTrue(client_token and owner_token)

        # Public fetch - client request should be pending
        self.client.force_authenticate(user=None)
        resp = self.client.get(f"/api/signatures/{client_token}/")
        self.assertEqual(resp.status_code, 200)
        j = resp.json().get("data") or resp.json()
        self.assertEqual(j.get("status"), "pending")

        # Client signs
        resp = self.client.post(f"/api/signatures/{client_token}/sign/", {"signature_value": "Client Sign", "signature_type": "typed"}, format="json")
        self.assertEqual(resp.status_code, 200)

        client_req = SignatureRequest.objects.get(token=client_token)
        self.assertEqual(client_req.status, "signed")

        # Owner request should remain pending but have been emailed (email_sent True)
        owner_req = SignatureRequest.objects.get(token=owner_token)
        self.assertEqual(owner_req.status, "pending")

        # Owner signs
        resp = self.client.post(f"/api/signatures/{owner_token}/sign/", {"signature_value": "Owner Sign", "signature_type": "typed"}, format="json")
        self.assertEqual(resp.status_code, 200)

        owner_req.refresh_from_db()
        self.assertEqual(owner_req.status, "signed")

        # After owner signed, final signed PDF should be generated on document
        self.document.refresh_from_db()
        self.assertTrue(bool(self.document.signed_pdf_path))
        final_abs = os.path.join(settings.MEDIA_ROOT, self.document.signed_pdf_path)
        self.assertTrue(os.path.exists(final_abs))

        # Verify audit entries exist for both signed requests
        self.assertTrue(SignatureAudit.objects.filter(signature_request__token=client_token, action="signed").exists())
        self.assertTrue(SignatureAudit.objects.filter(signature_request__token=owner_token, action="signed").exists())

    def test_drawn_signature_base64_flow(self):
        # 1x1 transparent png base64
        sample_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(f"/api/documents/{self.document.id}/send-signature/", {
            "recipient_email": "client@example.com",
            "recipient_name": "Client",
            "message": "Please draw your signature",
            "sign_mode": "client_only",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        created = resp.json().get("data", {}).get("created_requests", [])
        token = created[0]["token"]

        # Sign with drawn base64 signature
        self.client.force_authenticate(user=None)
        resp = self.client.post(f"/api/signatures/{token}/sign/", {
            "signature_value": sample_b64,
            "signature_type": "drawn",
        }, format="json")
        self.assertEqual(resp.status_code, 200)

        # Verify preview loads PDF without error and contains the signed PDF
        preview_resp = self.client.get(f"/api/signatures/{token}/preview/")
        self.assertEqual(preview_resp.status_code, 200)
        self.assertEqual(preview_resp["Content-Type"], "application/pdf")

    def test_enterprise_standard_signature_block_rendering(self):
        from apps.dashboard.pdf_service import format_signing_timestamp, build_pdf_for_document
        from datetime import datetime

        # Test timestamp formatting
        dt = timezone.now()
        ts_str = format_signing_timestamp(dt)
        self.assertTrue(ts_str.startswith("Signed: "))
        self.assertIn(str(dt.year), ts_str)

        # 1x1 transparent png base64
        sample_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # Send signature request with custom role and title
        self.client.force_authenticate(user=self.owner)
        resp = self.client.post(f"/api/documents/{self.document.id}/send-signature/", {
            "recipient_email": "john.smith@example.com",
            "recipient_name": "John Smith",
            "signer_role": "Authorized Signer",
            "signer_title": "Director of Human Resources",
            "owner_role": "Employee",
            "owner_name": "Jane Doe",
            "owner_title": "Senior Engineer",
            "sign_mode": "both",
        }, format="json")
        self.assertEqual(resp.status_code, 201)

        reqs = resp.json().get("data", {}).get("created_requests", [])
        self.assertEqual(len(reqs), 2)
        client_token = reqs[0]["token"]
        owner_token = reqs[1]["token"]

        client_req = SignatureRequest.objects.get(token=client_token)
        self.assertEqual(client_req.signer_role, "Authorized Signer")
        self.assertEqual(client_req.signer_title, "Director of Human Resources")
        self.assertEqual(client_req.recipient_name, "John Smith")

        owner_req = SignatureRequest.objects.get(token=owner_token)
        self.assertEqual(owner_req.signer_role, "Employee")
        self.assertEqual(owner_req.signer_title, "Senior Engineer")
        self.assertEqual(owner_req.recipient_name, "Jane Doe")

        # Client signs with drawn signature and updates title
        self.client.force_authenticate(user=None)
        sign_resp = self.client.post(f"/api/signatures/{client_token}/sign/", {
            "signature_value": sample_b64,
            "signature_type": "drawn",
            "signer_name": "John Smith",
            "signer_title": "Director of Human Resources",
        }, format="json")
        self.assertEqual(sign_resp.status_code, 200)

        client_req.refresh_from_db()
        self.assertEqual(client_req.status, "signed")
        self.assertIsNotNone(client_req.signed_at)

        # Owner signs
        sign_resp2 = self.client.post(f"/api/signatures/{owner_token}/sign/", {
            "signature_value": sample_b64,
            "signature_type": "drawn",
            "signer_name": "Jane Doe",
            "signer_title": "Senior Engineer",
        }, format="json")
        self.assertEqual(sign_resp2.status_code, 200)

        # Final PDF generated
        self.document.refresh_from_db()
        self.assertTrue(bool(self.document.signed_pdf_path))
        pdf_abs = os.path.join(settings.MEDIA_ROOT, self.document.signed_pdf_path)
        self.assertTrue(os.path.exists(pdf_abs))
        self.assertGreater(os.path.getsize(pdf_abs), 1000)

        # Verify audit records exist with correct actors
        client_audit = SignatureAudit.objects.filter(signature_request=client_req, action="signed").first()
        self.assertIsNotNone(client_audit)
        self.assertEqual(client_audit.actor, "john.smith@example.com")

        owner_audit = SignatureAudit.objects.filter(signature_request=owner_req, action="signed").first()
        self.assertIsNotNone(owner_audit)
        self.assertEqual(owner_audit.actor, self.owner.email)

