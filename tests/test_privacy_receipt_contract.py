"""R08-G0 contract tests for PrivacyReceiptV1 and privacy context binding.

No API, no storage, no erasure. These tests pin the contract that R08-A/B/C
must implement.
"""

import dataclasses
import json
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.privacy_receipt import (  # noqa: E402
    MAX_RECEIPT_BYTES, PRIVACY_CAPABILITY_OPERATIONS, PrivacyContextV1,
    PrivacyReceiptError, PrivacyReceiptV1, privacy_notice_digest,
    receipt_matches_context,
)

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64


def receipt(**overrides):
    data = dict(
        receipt_id="rcpt_0123456789abcdef",
        subject_ref="sub_synthetic_123",
        tenant_ref="tenant-synthetic",
        partner_application_ref="app-synthetic",
        issuer_ref="https://issuer.example/pool",
        event_type="PROFILE_CREATED",
        purpose="profile_management",
        legal_basis_ref="REVIEW_REQUIRED",
        privacy_notice_version=None,
        privacy_notice_digest=None,
        data_categories=("cv_metadata",),
        processing_domain="ris",
        operation_ref="op_0123456789abcdef",
        recorded_at=NOW.isoformat(),
        status="completed",
        retention_policy_ref="REVIEW_REQUIRED",
        evidence_level="server_verified",
        schema_version=1,
    )
    data.update(overrides)
    return PrivacyReceiptV1(**data)


def valid(**overrides):
    return receipt(**overrides).validate(now=NOW)


class TestReceiptSchema(unittest.TestCase):
    def test_valid_receipt_roundtrip(self):
        item = valid()
        self.assertEqual(item, PrivacyReceiptV1.from_dict(
            item.to_dict(), now=NOW))
        self.assertEqual(1, item.schema_version)

    def test_schema_version_is_integer_one(self):
        for value in (True, 2, "1", None):
            with self.assertRaises(PrivacyReceiptError):
                valid(schema_version=value)

    def test_unknown_field_rejected(self):
        payload = valid().to_dict()
        payload["cvText"] = "raw CV must never be in a receipt"
        with self.assertRaises(PrivacyReceiptError):
            PrivacyReceiptV1.from_dict(payload, now=NOW)

    def test_unknown_event_rejected(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(event_type="SOMETHING_ELSE")

    def test_unknown_purpose_domain_category_evidence_status(self):
        cases = (
            {"purpose": "marketing"},
            {"processing_domain": "unknown"},
            {"data_categories": ("raw_cv",)},
            {"evidence_level": "claimed"},
            {"status": "nonsense"},
        )
        for case in cases:
            with self.assertRaises(PrivacyReceiptError, msg=case):
                valid(**case)

    def test_identity_fields_are_required_and_opaque(self):
        for field in ("subject_ref", "tenant_ref",
                      "partner_application_ref", "issuer_ref"):
            with self.assertRaises(PrivacyReceiptError, msg=field):
                valid(**{field: ""})
        with self.assertRaises(PrivacyReceiptError):
            valid(subject_ref="user@example.com")
        with self.assertRaises(PrivacyReceiptError):
            valid(subject_ref="user name with spaces")

    def test_no_duplicate_or_unknown_data_categories(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(data_categories=("cv_metadata", "cv_metadata"))
        with self.assertRaises(PrivacyReceiptError):
            valid(data_categories=("cv_metadata", "unknown"))
        with self.assertRaises(PrivacyReceiptError):
            valid(data_categories=())

    def test_receipt_is_bounded(self):
        item = valid(data_categories=tuple(
            sorted({"identity", "cv_metadata", "cv_document",
                    "manual_search_profile", "cv_search_profile",
                    "ats_search_profile", "cursor", "idempotency"})))
        self.assertLess(len(item.canonical_json().encode("utf-8")),
                        MAX_RECEIPT_BYTES)

    def test_receipt_is_immutable(self):
        item = valid()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.status = "failed"
        copy = item.to_dict()
        copy["dataCategories"].append("identity")
        self.assertNotIn("identity", item.to_dict()["dataCategories"])

    def test_canonical_json_is_stable(self):
        item = valid()
        self.assertEqual(item.canonical_json(), item.canonical_json())
        self.assertEqual(sorted(json.loads(item.canonical_json())),
                         sorted(item.to_dict()))


class TestNoticeAndConsent(unittest.TestCase):
    def test_notice_event_requires_version_and_digest(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(event_type="PRIVACY_NOTICE_PRESENTED")
        with self.assertRaises(PrivacyReceiptError):
            valid(event_type="PRIVACY_NOTICE_PRESENTED",
                  privacy_notice_version="v1")
        with self.assertRaises(PrivacyReceiptError):
            valid(event_type="PRIVACY_NOTICE_PRESENTED",
                  privacy_notice_version="v1", privacy_notice_digest="short")

    def test_consent_records_event_not_legal_validity(self):
        item = valid(
            event_type="CONSENT_GRANTED",
            purpose="cv_processing",
            legal_basis_ref="REVIEW_REQUIRED",
            privacy_notice_version="2026-10-31",
            privacy_notice_digest=DIGEST,
            data_categories=("identity", "cv_metadata"))
        self.assertEqual("CONSENT_GRANTED", item.event_type)
        self.assertEqual("REVIEW_REQUIRED", item.legal_basis_ref)

    def test_withdrawn_consent_requires_notice(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(event_type="CONSENT_WITHDRAWN")

    def test_notice_digest_helper(self):
        first = privacy_notice_digest("Privacy notice v1")
        second = privacy_notice_digest("Privacy notice v1")
        self.assertEqual(first, second)
        self.assertEqual(64, len(first))
        self.assertNotEqual(first, privacy_notice_digest("Privacy notice v2"))


class TestEvidenceRules(unittest.TestCase):
    def test_ai_transfer_requested_can_be_client_reported(self):
        item = valid(
            event_type="AI_TRANSFER_REQUESTED",
            purpose="ai_processing",
            processing_domain="ai_provider",
            evidence_level="client_reported",
            status="requested",
            data_categories=("cv_metadata",))
        self.assertEqual("client_reported", item.evidence_level)

    def test_ai_transfer_confirmed_rejects_weak_evidence(self):
        for level in ("client_reported", "requested", "not_provable"):
            with self.assertRaises(PrivacyReceiptError, msg=level):
                valid(event_type="AI_TRANSFER_CONFIRMED",
                      purpose="ai_processing",
                      processing_domain="ai_provider",
                      evidence_level=level,
                      data_categories=("ai_provider",))

    def test_ai_transfer_confirmed_accepts_third_party_evidence(self):
        item = valid(
            event_type="AI_TRANSFER_CONFIRMED",
            purpose="ai_processing",
            processing_domain="ai_provider",
            evidence_level="third_party_confirmed",
            data_categories=("ai_provider",))
        self.assertEqual("third_party_confirmed", item.evidence_level)

    def test_erasure_completed_rejects_weak_evidence(self):
        for level in ("client_reported", "requested", "not_provable"):
            with self.assertRaises(PrivacyReceiptError, msg=level):
                valid(event_type="ERASURE_COMPLETED",
                      purpose="privacy_request",
                      operation_ref="op_erase_00000001",
                      evidence_level=level,
                      data_categories=("cv_document",))

    def test_erasure_completed_requires_completed_status(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(event_type="ERASURE_COMPLETED",
                  purpose="privacy_request",
                  status="partially_completed",
                  data_categories=("cv_document",))

    def test_erasure_partial_status_is_explicit(self):
        item = valid(
            event_type="ERASURE_PARTIALLY_COMPLETED",
            purpose="privacy_request",
            status="partially_completed",
            evidence_level="server_verified",
            data_categories=("cv_document", "audit_log"))
        self.assertEqual("partially_completed", item.status)

    def test_new_v1_profile_events_are_supported(self):
        for event, purpose in (
            ("USER_PROFILE_UPDATED", "profile_management"),
            ("PROFILE_DELETED", "privacy_request"),
        ):
            item = valid(event_type=event, purpose=purpose)
            self.assertEqual(event, item.event_type)
        self.assertEqual("completed",
                         valid(event_type="PROFILE_DELETED",
                               purpose="privacy_request").status)

    def test_notice_acknowledgement_requires_notice_version_and_digest(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(event_type="PRIVACY_NOTICE_ACKNOWLEDGED")
        item = valid(event_type="PRIVACY_NOTICE_ACKNOWLEDGED",
                     privacy_notice_version="v1",
                     privacy_notice_digest=DIGEST)
        self.assertEqual("PRIVACY_NOTICE_ACKNOWLEDGED", item.event_type)

    def test_event_status_must_match(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(event_type="ERASURE_REQUESTED",
                  purpose="privacy_request", status="completed")


class TestContentAndTimestampSafety(unittest.TestCase):
    def test_receipt_has_no_cv_raw_data_fields(self):
        item = valid()
        serialized = item.canonical_json()
        for forbidden in ("cvText", "cvContent", "prompt", "authorization",
                          "presignedUrl", "secret", "token"):
            self.assertNotIn(forbidden, serialized)

    def test_forbidden_value_is_rejected(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(privacy_notice_version="X-Amz-Signature=abc",
                  privacy_notice_digest=DIGEST,
                  event_type="PRIVACY_NOTICE_PRESENTED")

    def test_timestamp_requires_timezone(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(recorded_at="2026-10-31T12:00:00")

    def test_future_timestamp_is_rejected(self):
        with self.assertRaises(PrivacyReceiptError):
            valid(recorded_at="2026-10-31T12:10:00+00:00")

    def test_historical_timestamp_is_accepted(self):
        item = valid(recorded_at="2026-10-01T12:00:00+00:00")
        self.assertTrue(item.recorded_at.startswith("2026-10-01"))


class TestContextBinding(unittest.TestCase):
    def setUp(self):
        self.context = PrivacyContextV1(
            user_id="sub_synthetic_123",
            tenant_id="tenant-synthetic",
            partner_application_id="app-synthetic",
            issuer="https://issuer.example/pool")
        self.item = valid()

    def test_matching_context(self):
        self.assertTrue(receipt_matches_context(self.item, self.context))

    def test_each_identity_dimension_is_bound(self):
        for field, value in (
            ("user_id", "sub_other"),
            ("tenant_id", "tenant-other"),
            ("partner_application_id", "app-other"),
            ("issuer", "https://other/pool"),
        ):
            other = dataclasses.replace(self.context, **{field: value})
            self.assertFalse(receipt_matches_context(self.item, other))

    def test_context_rejects_email_subject(self):
        with self.assertRaises(PrivacyReceiptError):
            PrivacyContextV1(
                user_id="user@example.com", tenant_id="t",
                partner_application_id="a", issuer="https://i/pool")

    def test_capability_operations_are_declared(self):
        self.assertEqual(
            ("inspect", "export", "erase", "receipts", "request_status"),
            PRIVACY_CAPABILITY_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
