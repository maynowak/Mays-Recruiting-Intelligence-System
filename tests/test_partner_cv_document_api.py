"""R04 tests: partner CV metadata + secure document lifecycle.

Real handler -> real R02 repository -> in-memory DynamoDB fake, with a fake S3
client. The credential/registry boundary is the REAL one backed by fake stores
(inherited from the R03 harness).
"""

import json
import os
import sys
import threading
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import documents  # noqa: E402
import handler as h  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    Harness, _meta, _profile, _registry,
)

CVS = "/v1/partner/me/cvs"
BUCKET = "test-documents"


class TestCvDocumentCanonicalProjection(unittest.TestCase):
    def _cv(self, status="upload_pending", size=0, document_id=None,
            metadata=None):
        return SimpleNamespace(
            cv_id="cv-1", name="resume.pdf", content_type="application/pdf",
            processing_status=status, size=size, document_id=document_id,
            created_at="2026-11-01T00:00:00+00:00",
            updated_at="2026-11-01T00:00:00+00:00", version=3,
            metadata=metadata or {})

    def test_pending_legacy_status_is_canonical_and_unverified_size_is_hidden(self):
        body = json.loads(h._cv_response(self._cv(size=4096, document_id="doc-1"))["body"])
        self.assertEqual(body["processingStatus"], "pending")
        self.assertEqual(body["documentId"], "doc-1")
        self.assertNotIn("sizeBytes", body)
        self.assertNotIn("name", body)
        self.assertNotIn("size", body)

    def test_failed_and_deleted_statuses_are_preserved_as_canonical_states(self):
        self.assertEqual(json.loads(h._cv_response(self._cv("error"))["body"])
                         ["processingStatus"], "failed")
        self.assertEqual(json.loads(h._cv_response(self._cv("deleted"))["body"])
                         ["processingStatus"], "deleted")

    def test_only_verified_ready_size_is_emitted_and_metadata_is_allowlisted(self):
        body = json.loads(h._cv_response(self._cv(
            status="ready", size=2048, document_id="doc-1",
            metadata={"pageCount": 2, "language": "en", "internal": "no"}))[
                "body"])
        self.assertEqual(body["sizeBytes"], 2048)
        self.assertEqual(body["metadata"], {"pageCount": 2, "language": "en"})
        self.assertNotIn("internal", body["metadata"])


class _S3NotFound(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "404"}}


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.presigned = []
        self.deleted = []
        self.fail_presign = False

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        if self.fail_presign:
            raise RuntimeError("presign unavailable")
        self.presigned.append((operation, dict(Params), ExpiresIn))
        return "https://example.invalid/%s?X-Amz-Signature=test" % operation

    def head_object(self, Bucket, Key):
        obj = self.objects.get((Bucket, Key))
        if obj is None:
            raise _S3NotFound()
        return dict(obj)

    def delete_object(self, Bucket, Key):
        existed = (Bucket, Key) in self.objects
        self.objects.pop((Bucket, Key), None)
        self.deleted.append((Bucket, Key))
        return {"VersionId": "v-delete-marker"} if existed else {}


class CvHarness(Harness):
    def setUp(self):
        super().setUp()
        self.s3 = FakeS3()
        self._old_bucket = os.environ.get("DOCUMENTS_BUCKET")
        os.environ["DOCUMENTS_BUCKET"] = BUCKET
        self.s3_patch = patch("documents._s3_client", return_value=self.s3)
        self.s3_patch.start()

    def tearDown(self):
        self.s3_patch.stop()
        if self._old_bucket is None:
            os.environ.pop("DOCUMENTS_BUCKET", None)
        else:
            os.environ["DOCUMENTS_BUCKET"] = self._old_bucket
        super().tearDown()

    # helpers ---------------------------------------------------------- #
    def create_cv(self, name="cv.pdf", content_type="application/pdf", **overrides):
        payload = {"name": name, "contentType": content_type}
        payload.update(overrides)
        return self.call("POST", CVS, body=payload)

    def ticket(self, cv_id, content_type="application/pdf"):
        return self.call("POST", f"{CVS}/{cv_id}/document/upload",
                         body={"contentType": content_type})

    def simulate_put(self, cv_id, document_id=None, size=2048, etag="etag-1",
                     content_type="application/pdf", tenant=None, user=None):
        tenant = tenant or "tenant-1"
        user = user or "user-1"
        if document_id is None:
            document_id = self.body(self.call("GET", f"{CVS}/{cv_id}"))["documentId"]
        key = documents.build_key(tenant, user, document_id)
        self.s3.objects[(BUCKET, key)] = {
            "ContentLength": size,
            "ETag": '"%s"' % etag,
            "ContentType": content_type,
            "LastModified": datetime.now(timezone.utc),
        }
        return key

    def complete(self, cv_id):
        return self.call("POST", f"{CVS}/{cv_id}/document/complete", body={})


# --------------------------------------------------------------------------- #
# CV CRUD
# --------------------------------------------------------------------------- #

class TestCvCrud(CvHarness):
    def test_create_returns_201_pending(self):
        resp = self.create_cv()
        self.assertEqual(resp["statusCode"], 201)
        b = self.body(resp)
        self.assertTrue(b["cvId"])
        self.assertEqual(b["schemaVersion"], 1)
        self.assertEqual(b["filename"], "cv.pdf")
        self.assertEqual(b["contentType"], "application/pdf")
        self.assertEqual(b["processingStatus"], "pending")
        self.assertIsNone(b.get("documentId"))
        self.assertNotIn("name", b)
        self.assertNotIn("sizeBytes", b)
        self.assertEqual(b["version"], 1)

    def test_get_and_list(self):
        created = self.body(self.create_cv())
        cv_id = created["cvId"]
        self.assertEqual(self.call("GET", f"{CVS}/{cv_id}")["statusCode"], 200)
        listed = self.body(self.call("GET", CVS))
        self.assertEqual(len(listed["items"]), 1)
        self.assertEqual(listed["items"][0]["cvId"], cv_id)
        self.assertIsNone(listed["nextCursor"])

    def test_list_paginates_with_scoped_next_cursor(self):
        created = [self.body(self.create_cv(name=f"cv{i}.pdf"))["cvId"]
                   for i in range(3)]
        first = self.body(self.call("GET", CVS, query={"limit": "2"}))
        self.assertEqual(len(first["items"]), 2)
        self.assertIsNotNone(first["nextCursor"])
        second = self.body(self.call(
            "GET", CVS, query={"limit": "2", "cursor": first["nextCursor"]}))
        self.assertEqual(len(second["items"]), 1)
        self.assertIsNone(second["nextCursor"])
        self.assertEqual(
            set(created), {item["cvId"] for item in first["items"] + second["items"]})

    def test_list_rejects_invalid_and_foreign_cursors(self):
        self.create_cv()
        invalid = self.call("GET", CVS, query={"cursor": "not-a-cursor"})
        self.assertEqual(invalid["statusCode"], 400)

        self.create_cv(name="second.pdf")
        first = self.body(self.call("GET", CVS, query={"limit": "1"}))
        foreign = self.call("GET", CVS, sub="user-2",
                            query={"cursor": first["nextCursor"]})
        self.assertEqual(foreign["statusCode"], 400)

    def test_patch_updates_name_and_keeps_lifecycle_fields(self):
        created = self.body(self.create_cv())
        cv_id = created["cvId"]
        resp = self.call("PATCH", f"{CVS}/{cv_id}",
                         body={"filename": "renamed.pdf", "version": 1})
        self.assertEqual(resp["statusCode"], 200)
        b = self.body(resp)
        self.assertEqual(b["filename"], "renamed.pdf")
        self.assertNotIn("name", b)
        self.assertEqual(b["processingStatus"], "pending")
        self.assertEqual(b["version"], 2)

    def test_delete_returns_200(self):
        created = self.body(self.create_cv())
        cv_id = created["cvId"]
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(resp["statusCode"], 200)
        self.assertTrue(self.body(resp)["deleted"])
        self.assertEqual(self.call("GET", f"{CVS}/{cv_id}")["statusCode"], 404)

    def test_invalid_metadata_422(self):
        resp = self.create_cv(name="")
        self.assertEqual(resp["statusCode"], 422)

    def test_invalid_content_type_422(self):
        resp = self.create_cv(content_type="application/x-msdownload")
        self.assertEqual(resp["statusCode"], 422)

    def test_unknown_metadata_is_rejected(self):
        resp = self.create_cv(metadata={"cvText": "secret"})
        self.assertEqual(resp["statusCode"], 422)

    def test_capacity_limit_10(self):
        for i in range(10):
            self.assertEqual(self.create_cv(name=f"cv{i}.pdf")["statusCode"], 201)
        resp = self.create_cv(name="cv11.pdf")
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(self.body(resp)["code"], "capacity_exceeded")

    def test_concurrent_creates_cap_at_10(self):
        results = []
        lock = threading.Lock()

        def create_one(i):
            r = self.create_cv(name=f"c{i}.pdf")
            with lock:
                results.append(r["statusCode"])

        threads = [threading.Thread(target=create_one, args=(i,)) for i in range(11)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count(201), 10)
        self.assertEqual(results.count(409), 1)

    def test_version_conflict_409(self):
        created = self.body(self.create_cv())
        cv_id = created["cvId"]
        resp = self.call("PATCH", f"{CVS}/{cv_id}",
                         body={"name": "x.pdf", "version": 99})
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(self.body(resp)["code"], "conflict")

    def test_patch_accepts_if_match_version(self):
        created = self.body(self.create_cv())
        response = self.call(
            "PATCH", f"{CVS}/{created['cvId']}",
            body={"filename": "if-match.pdf"},
            extra_headers={"If-Match": '"1"'})
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(self.body(response)["version"], 2)

    def test_forged_identity_rejected(self):
        resp = self.create_cv(userId="victim", tenantId="other")
        self.assertEqual(resp["statusCode"], 400)
        self.assertEqual(self.body(resp)["code"], "CLIENT_IDENTITY_FORBIDDEN")


# --------------------------------------------------------------------------- #
# Document lifecycle
# --------------------------------------------------------------------------- #

class TestDocumentLifecycle(CvHarness):
    def test_upload_ticket_200(self):
        cv_id = self.body(self.create_cv())["cvId"]
        resp = self.ticket(cv_id)
        self.assertEqual(resp["statusCode"], 200)
        b = self.body(resp)
        self.assertEqual(b["cvId"], cv_id)
        self.assertTrue(b["documentId"])
        self.assertIn("uploadUrl", b)
        self.assertNotEqual(b["documentId"], cv_id)

    def test_complete_after_put_marks_ready(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id, size=4096, etag="abc")
        resp = self.complete(cv_id)
        self.assertEqual(resp["statusCode"], 200)
        b = self.body(resp)
        self.assertEqual(b["processingStatus"], "ready")
        self.assertEqual(b["sizeBytes"], 4096)
        self.assertNotIn("size", b)
        self.assertEqual(b["documentId"], doc_id)

    def test_complete_is_idempotent_without_a_second_version_increment(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id)
        first = self.body(self.complete(cv_id))
        second = self.body(self.complete(cv_id))
        self.assertEqual(first["processingStatus"], "ready")
        self.assertEqual(second["processingStatus"], "ready")
        self.assertEqual(first["version"], 3)
        self.assertEqual(second["version"], 3)

    def test_complete_rejects_wrong_ticket_document_id(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.ticket(cv_id)
        response = self.call("POST", f"{CVS}/{cv_id}/document/complete",
                             body={"documentId": "forged-document"})
        self.assertEqual(response["statusCode"], 409)
        self.assertEqual(self.body(self.call("GET", f"{CVS}/{cv_id}"))[
            "processingStatus"], "pending")

    def test_complete_rejects_non_pdf_object(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id, content_type="text/plain")
        response = self.complete(cv_id)
        self.assertEqual(response["statusCode"], 409)
        self.assertEqual(self.body(self.call("GET", f"{CVS}/{cv_id}"))[
            "processingStatus"], "pending")

    def test_complete_without_object_409_not_ready(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.ticket(cv_id)
        resp = self.complete(cv_id)
        self.assertEqual(resp["statusCode"], 409)
        self.assertEqual(self.body(self.call("GET", f"{CVS}/{cv_id}"))["processingStatus"],
                         "pending")

    def test_complete_empty_object_409(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id, size=0)
        self.assertEqual(self.complete(cv_id)["statusCode"], 409)

    def test_retry_interrupted_upload(self):
        cv_id = self.body(self.create_cv())["cvId"]
        first = self.body(self.ticket(cv_id))
        # failure: no object yet
        self.assertEqual(self.complete(cv_id)["statusCode"], 409)
        # retry re-issues the SAME document id
        second = self.body(self.ticket(cv_id))
        self.assertEqual(second["documentId"], first["documentId"])
        # then the upload completes
        self.simulate_put(cv_id, second["documentId"])
        self.assertEqual(self.complete(cv_id)["statusCode"], 200)

    def test_no_reupload_once_ready(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id)
        self.assertEqual(self.complete(cv_id)["statusCode"], 200)
        self.assertEqual(self.ticket(cv_id)["statusCode"], 409)

    def test_download_owner_only(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id)
        self.complete(cv_id)
        resp = self.call("GET", f"{CVS}/{cv_id}/document")
        self.assertEqual(resp["statusCode"], 200)
        self.assertIn("downloadUrl", self.body(resp))
        # foreign user cannot reach the CV at all
        other = self.call("GET", f"{CVS}/{cv_id}/document", sub="user-2")
        self.assertEqual(other["statusCode"], 404)

    def test_download_before_ready_409(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.ticket(cv_id)
        self.assertEqual(
            self.call("GET", f"{CVS}/{cv_id}/document")["statusCode"], 409)

    def test_upload_presign_failure_is_500(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.s3.fail_presign = True
        resp = self.ticket(cv_id)
        self.assertEqual(resp["statusCode"], 500)
        # metadata reserved but not ready
        b = self.body(self.call("GET", f"{CVS}/{cv_id}"))
        self.assertEqual(b["processingStatus"], "pending")

    def test_delete_document_failure_keeps_metadata(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id)
        self.complete(cv_id)
        with patch("documents.delete_document_report",
                   side_effect=RuntimeError("s3 down")):
            resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(resp["statusCode"], 502)
        self.assertTrue(self.body(resp)["metadataRetained"])
        # metadata still present, not falsely deleted
        self.assertEqual(self.call("GET", f"{CVS}/{cv_id}")["statusCode"], 200)

    def test_delete_classifies_versioned_marker(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        self.simulate_put(cv_id, doc_id)
        self.complete(cv_id)
        resp = self.call("DELETE", f"{CVS}/{cv_id}")
        self.assertEqual(resp["statusCode"], 200)
        b = self.body(resp)
        self.assertTrue(b["document"]["existed"])
        self.assertTrue(b["document"]["deleteMarker"])
        self.assertFalse(b["document"]["physicalPurge"])
        self.assertFalse(b["physicalPurge"])

    def test_no_presigned_url_persisted(self):
        cv_id = self.body(self.create_cv())["cvId"]
        doc_id = self.body(self.ticket(cv_id))["documentId"]
        stored = self.dynamo.resources[cv_id]
        serialized = json.dumps(stored)
        self.assertNotIn("X-Amz-Signature", serialized)
        self.assertNotIn("uploadUrl", serialized)
        self.assertEqual(stored["payload"]["documentId"], doc_id)


# --------------------------------------------------------------------------- #
# Security
# --------------------------------------------------------------------------- #

class TestCvSecurity(CvHarness):
    def test_cross_user_isolation(self):
        cv_id = self.body(self.create_cv())["cvId"]
        self.assertEqual(self.call("GET", f"{CVS}/{cv_id}", sub="user-2")["statusCode"], 404)
        self.assertEqual(self.call("DELETE", f"{CVS}/{cv_id}", sub="user-2")["statusCode"], 404)
        self.assertEqual(self.body(self.call("GET", CVS, sub="user-2"))["items"], [])

    def test_cross_tenant_403(self):
        self.assertEqual(self.call("GET", CVS, tenant="tenant-other")["statusCode"], 403)

    def test_cross_partner_403(self):
        self.registry = None
        self.assertEqual(self.call("GET", CVS)["statusCode"], 403)

    def test_cross_issuer_404(self):
        cv_id = self.body(self.create_cv())["cvId"]
        resp = self.call("GET", f"{CVS}/{cv_id}",
                         issuer="https://other-issuer.example/pool")
        self.assertEqual(resp["statusCode"], 404)

    def test_missing_tenant_rejected(self):
        self.cred_store.meta = _meta(tenant="")
        self.prof_store.profile = _profile(tenant="")
        self.assertEqual(self.call("GET", CVS)["statusCode"], 403)

    def test_invalid_partner_permission_403(self):
        self.registry = _registry(status="INACTIVE")
        self.assertEqual(self.call("GET", CVS)["statusCode"], 403)

    def test_no_agent_or_model_call(self):
        self.create_cv()
        self.assertEqual(self.enqueued, [])


if __name__ == "__main__":
    unittest.main()
