"""Notice-version lifecycle for partner consents.

A notice identifier is not a legal approval. Drafts may be grantable while
``CONSENT_NOTICE_STATE_ENFORCED`` is off (technical/synthetic runs); with
enforcement on only APPROVED/ACTIVE versions may be granted. Existing grants
survive a version becoming SUPERSEDED and are never silently rewritten.
"""

import json
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

try:
    import boto3
    from moto import mock_aws
    from jobsearch.consent_contract import (
        ConsentContext, ConsentContractError, NOTICE_ACTIVE, NOTICE_APPROVED,
        NOTICE_DRAFT,
        NOTICE_SUPERSEDED, STATUS_GRANTED, STATUS_NOT_GRANTED,
        catalog_payload, external_refs_payload, notice_version)
    from jobsearch import consent_contract
    from jobsearch.consent_repository import ConsentRepository
except ImportError:  # pragma: no cover
    boto3 = None
    mock_aws = lambda fn: fn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

CTX = ConsentContext("u1", "t1", "p1", "https://issuer")
PURPOSE = "application-storage"
VERSION = "1.0"


def _table():
    db = boto3.resource("dynamodb", region_name="eu-central-1")
    db.create_table(
        TableName="consents",
        KeySchema=[{"AttributeName": "scopeKey", "KeyType": "HASH"},
                   {"AttributeName": "entityKey", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "scopeKey", "AttributeType": "S"},
                              {"AttributeName": "entityKey", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return ConsentRepository("consents", db)


def _entry(**changes):
    return replace(notice_version(PURPOSE, VERSION), **changes)


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class NoticeLifecycleTests(unittest.TestCase):
    @mock_aws
    def test_draft_is_grantable_while_enforcement_is_off(self):
        draft = _entry(state=NOTICE_DRAFT, legal_approval_ref=None)
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: draft}):
            with patch.dict(os.environ,
                            {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
                repo = _table()
                granted = repo.grant(CTX, PURPOSE, VERSION)
            self.assertEqual(STATUS_GRANTED, granted["status"])
            self.assertEqual(NOTICE_DRAFT, granted["noticeState"])
            self.assertFalse(granted["noticeApproved"])
            self.assertTrue(granted["acceptedForNewGrant"])
            self.assertIsNone(notice_version(PURPOSE, VERSION).legal_approval_ref)

    @mock_aws
    def test_enforcement_rejects_draft_for_new_grant(self):
        draft = _entry(state=NOTICE_DRAFT, legal_approval_ref=None)
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: draft}):
            with patch.dict(os.environ,
                            {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
                repo = _table()
                with self.assertRaises(ConsentContractError) as caught:
                    repo.grant(CTX, PURPOSE, VERSION)
                self.assertEqual("NOTICE_NOT_ACTIVE", caught.exception.code)
                status = repo.get(CTX, PURPOSE)
        self.assertEqual(STATUS_NOT_GRANTED, status["status"])
        self.assertFalse(status["noticeApproved"])
        self.assertFalse(status["acceptedForNewGrant"])

    @mock_aws
    def test_enforcement_accepts_an_active_version(self):
        active = _entry(state=NOTICE_ACTIVE, legal_approval_ref="LEGAL-APPROVAL-1")
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE], {VERSION: active}):
            with patch.dict(os.environ, {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
                repo = _table()
                granted = repo.grant(CTX, PURPOSE, VERSION)
        self.assertEqual(STATUS_GRANTED, granted["status"])
        self.assertEqual(NOTICE_ACTIVE, granted["noticeState"])
        self.assertTrue(granted["noticeApproved"])

    @mock_aws
    def test_existing_grant_survives_superseding_and_stays_idempotent(self):
        repo = _table()
        repo.grant(CTX, PURPOSE, VERSION)
        superseded = _entry(state=NOTICE_SUPERSEDED, legal_approval_ref="LEGAL-1")
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE], {VERSION: superseded}):
            with patch.dict(os.environ, {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
                # The recorded consent is still valid; no downgrade.
                self.assertTrue(repo.has_consent(CTX, PURPOSE))
                status = repo.get(CTX, PURPOSE)
                self.assertEqual(NOTICE_SUPERSEDED, status["noticeState"])
                self.assertTrue(status["noticeApproved"])
                # Repeating the same grant is an idempotent read, not a new
                # consent against a superseded text.
                again = repo.grant(CTX, PURPOSE, VERSION)
                self.assertEqual(1, again["version"])
                # Withdrawal must stay possible under enforcement.
                withdrawn = repo.withdraw(CTX, PURPOSE)
                self.assertEqual("WITHDRAWN", withdrawn["status"])
        events, _ = repo.history(CTX, PURPOSE)
        self.assertEqual(["WITHDRAWN", "GRANTED"], [e["event"] for e in events])

    @mock_aws
    def test_jobsearch_draft_ref_is_known_but_not_equivalent(self):
        refs = external_refs_payload(PURPOSE)
        entry = next(r for r in refs
                     if r["externalRef"] == "2026-11-04-draft-1")
        self.assertEqual("mays-jobsearch", entry["source"])
        self.assertEqual(NOTICE_DRAFT, entry["noticeState"])
        self.assertIsNone(entry["noticeVersion"])
        repo = _table()
        with self.assertRaises(ConsentContractError) as caught:
            repo.grant(CTX, PURPOSE, "2026-11-04-draft-1")
        self.assertEqual("INVALID_NOTICE_VERSION", caught.exception.code)

    @mock_aws
    def test_catalog_reports_the_operator_approval(self):
        with patch.dict(os.environ, {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
            catalog = catalog_payload(PURPOSE)
            current = notice_version(PURPOSE, VERSION)
        self.assertEqual(1, len(catalog))
        entry = catalog[0]
        self.assertEqual(VERSION, entry["noticeVersion"])
        self.assertEqual(NOTICE_APPROVED, entry["noticeState"])
        self.assertTrue(entry["noticeApproved"])
        self.assertEqual("JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08",
                         entry["legalApprovalRef"])
        self.assertTrue(entry["acceptedForNewGrant"])
        self.assertEqual(NOTICE_APPROVED, current.state)
        self.assertEqual("JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08",
                         current.legal_approval_ref)

    def test_catalog_still_reports_a_draft_when_patched(self):
        draft = _entry(state=NOTICE_DRAFT, legal_approval_ref=None)
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: draft}):
            with patch.dict(os.environ,
                            {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
                entry = catalog_payload(PURPOSE)[0]
        self.assertEqual(NOTICE_DRAFT, entry["noticeState"])
        self.assertFalse(entry["noticeApproved"])
        self.assertIsNone(entry["legalApprovalRef"])

    @mock_aws
    def test_unknown_version_is_still_rejected(self):
        repo = _table()
        with self.assertRaises(ConsentContractError) as caught:
            repo.grant(CTX, PURPOSE, "9.9")
        self.assertEqual("INVALID_NOTICE_VERSION", caught.exception.code)


class ConsentStatusResponseShapeTests(unittest.TestCase):
    def test_status_response_exposes_catalog_and_external_refs(self):
        import handler  # noqa: E402
        from jobsearch.consent_contract import ConsentContext

        class _Repo:
            def get(self, ctx, purpose):
                return {"purpose": purpose, "status": STATUS_NOT_GRANTED}

        ctx = ConsentContext("u1", "t1", "p1", "https://issuer")
        event = {"httpMethod": "GET", "path": "/v1/partner/me/consents",
                 "headers": {}, "queryStringParameters": None, "body": None}
        with patch.object(handler, "_consent_ctx", return_value=(ctx, None)), \
                patch.object(handler, "_consent_repo", return_value=_Repo()):
            response = handler._handle_consent_routes(
                event, None, "GET", "/v1/partner/me/consents")
        body = json.loads(response["body"])
        self.assertEqual(
            ["application-storage", "cv-storage"],
            [item["purpose"] for item in body["items"]],
        )
        self.assertEqual(VERSION, body["catalog"][0]["noticeVersion"])
        self.assertEqual(NOTICE_APPROVED, body["catalog"][0]["noticeState"])
        self.assertEqual("JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08",
                         body["catalog"][0]["legalApprovalRef"])
        self.assertEqual("2026-11-04-draft-1",
                         body["externalRefs"][0]["externalRef"])


if __name__ == "__main__":
    unittest.main()
