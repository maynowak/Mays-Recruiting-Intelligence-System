"""Tests Gate 14: Secure Document Storage (Gate 14).

Fake-S3 (kein Netz/AWS): Presign-Semantik, Ownership, Spoof-Resistenz,
Tenant-Trennung, Delete, Unauth. Keine echten PII (synthetische IDs).
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_doc_spec = importlib.util.spec_from_file_location(
    "documents_uut", os.path.join(REPO_ROOT, "lambda", "documents.py"))
documents = importlib.util.module_from_spec(_doc_spec)
sys.modules["documents_uut"] = documents
_doc_spec.loader.exec_module(documents)
sys.modules["documents"] = documents  # Handler-Importpfad

_h_spec = importlib.util.spec_from_file_location(
    "gw_handler_14", os.path.join(REPO_ROOT, "lambda", "handler.py"))
handler = importlib.util.module_from_spec(_h_spec)
sys.modules["gw_handler_14"] = handler
_h_spec.loader.exec_module(handler)


class FakeS3:
    class NoSuchKey(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "NoSuchKey"}}

    def __init__(self):
        self.objects = {}
        self.signed = []

    def generate_presigned_url(self, op, Params, ExpiresIn):
        assert Params["Bucket"] == "documents-bucket"
        self.signed.append((op, Params["Key"], ExpiresIn))
        return f"https://s3.example/{op}/{Params['Key']}?exp={ExpiresIn}"

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise FakeS3.NoSuchKey()
        return {}

    def put_object(self, Bucket, Key, Body):
        self.objects[Key] = Body

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


def _env_bucket(monkeypatch=None):
    os.environ["DOCUMENTS_BUCKET"] = "documents-bucket"


class TestKeyScheme(unittest.TestCase):
    def test_key_structure_no_pii(self):
        key = documents.build_key("tenant-a", "user-123", "doc_ABC-09")
        self.assertEqual(key, "tenant/tenant-a/users/user-123/documents/doc_ABC-09")

    def test_bad_doc_id_rejected(self):
        for bad in ("", "../x", "a/b", "x" * 65, None):
            with self.assertRaises(ValueError):
                documents.build_key("t", "u", bad)

    def test_tenant_default(self):
        with self.assertRaises(ValueError):
            documents.build_key(None, "u", "d")


class TestPresign(unittest.TestCase):
    def setUp(self):
        _env_bucket()
        self.s3 = FakeS3()

    def tearDown(self):
        os.environ.pop("DOCUMENTS_BUCKET", None)

    def test_upload_returns_short_lived_url(self):
        out = documents.presign_upload(self.s3, "tenant-a", "user-1", "application/pdf")
        self.assertIn("documentId", out)
        self.assertIn("expiresAt", out)
        self.assertEqual(out["requiredHeaders"], {"Content-Type": "application/pdf"})
        self.assertNotIn("key", out)
        self.assertNotIn("expiresIn", out)
        op, key, exp = self.s3.signed[0]
        self.assertEqual(op, "put_object")
        self.assertLessEqual(exp, 900)

    def test_upload_rejects_content_type(self):
        with self.assertRaises(ValueError):
            documents.presign_upload(self.s3, "t", "u", "application/x-msdownload")

    def test_download_missing_is_none(self):
        self.assertIsNone(documents.presign_download(self.s3, "t", "u", "nope123"))

    def test_download_existing(self):
        self.s3.objects["tenant/t/users/u/documents/d1"] = b"x"
        out = documents.presign_download(self.s3, "t", "u", "d1")
        self.assertTrue(out["downloadUrl"].startswith("https://s3.example/get_object/"))
        self.assertIn("documentId", out)
        self.assertIn("expiresAt", out)
        self.assertNotIn("key", out)

    def test_delete_semantics(self):
        self.assertFalse(documents.delete_document(self.s3, "t", "u", "nope"))
        self.s3.objects["tenant/t/users/u/documents/d2"] = b"x"
        self.assertTrue(documents.delete_document(self.s3, "t", "u", "d2"))
        self.assertNotIn("tenant/t/users/u/documents/d2", self.s3.objects)


class TestHandlerAuth(unittest.TestCase):
    def _claims(self, sub="user-1", tenant=None):
        claims = {"sub": sub, "email": "t@example.com"}
        if tenant:
            claims["custom:tenant_id"] = tenant
        return claims

    def _event(self, method, path, body=None, claims=None):
        return {
            "httpMethod": method, "path": path,
            "requestContext": {"authorizer": {"jwt": {"claims": claims or self._claims()}}},
            "body": json.dumps(body) if body is not None else None,
        }

    def test_unauthenticated_denied(self):
        for method, path in (("POST", "/me/documents"),):
            resp = handler.handler(self._event(method, path, {}, {"sub": None}), None)
            self.assertEqual(resp["statusCode"], 401)

    def test_missing_tenant_denied_without_default_fallback(self):
        event = self._event("POST", "/me/documents", {}, self._claims(tenant=None))
        context = handler._documents_context(event)
        self.assertIsNotNone(context)
        self.assertEqual(context.get("_documentContextError"), "Tenant not resolvable")
        response = handler.handler(event, None)
        self.assertEqual(response["statusCode"], 403)

    def test_upload_response_is_canonical_and_context_bound(self):
        event = self._event("POST", "/me/documents", {"contentType": "application/pdf"},
                            self._claims(tenant="tenant-a"))
        ticket = {
            "documentId": "doc-1", "uploadUrl": "https://upload.invalid/1",
            "expiresAt": "2026-11-01T12:15:00+00:00",
            "requiredHeaders": {"Content-Type": "application/pdf"},
        }
        with patch.object(documents, "presign_upload", return_value=ticket) as mocked:
            response = handler.handler(event, None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body, ticket)
        self.assertNotIn("key", body)
        self.assertTrue(mocked.call_args.kwargs["require_tenant"])
        self.assertEqual(mocked.call_args.kwargs["tenant_id"], "tenant-a")

    def test_download_and_delete_responses_do_not_expose_storage_key(self):
        claims = self._claims(tenant="tenant-a")
        download = {
            "documentId": "doc-1", "downloadUrl": "https://download.invalid/1",
            "expiresAt": "2026-11-01T12:15:00+00:00",
        }
        with patch.object(documents, "presign_download", return_value=download), \
                patch.object(documents, "delete_document", return_value=True):
            get_response = handler.handler(self._event("GET", "/me/documents/doc-1", claims=claims), None)
            delete_response = handler.handler(self._event("DELETE", "/me/documents/doc-1", claims=claims), None)
        self.assertNotIn("key", json.loads(get_response["body"]))
        self.assertEqual(json.loads(delete_response["body"]),
                         {"deleted": True, "documentId": "doc-1"})

    def test_spoofed_identity_ignored(self):
        """Body-userId/tenantId/Key duerfen nie in Keys landen (Unit: build_key)."""
        with self.assertRaises(ValueError):
            documents.build_key("tenant-evil", "user-1", "../../evil")

    def test_regional_endpoint_no_redirect(self):
        """Presign-Endpoint regional (kein 307, sonst SigV4-Invalidierung)."""
        import inspect
        src = inspect.getsource(documents._s3_client)
        self.assertIn("endpoint_url", src)
        self.assertIn("amazonaws.com", src)


if __name__ == "__main__":
    unittest.main()
