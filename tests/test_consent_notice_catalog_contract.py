"""Cross-repository contract lock for the consent notice catalogue.

Companion to ``JM-RIS-STORAGE-ACTIVATION-01`` (RIS side). The Jobsearch BFF
gates durable ``application-storage`` grants on the catalogue returned by
``GET /v1/partner/me/consents``. These tests pin the pieces that gate relies
on, so a later RIS change cannot silently invalidate it:

* the catalogue is a **top-level array** on the GET response and is scoped to
  the requested purpose (it is *not* part of the POST grant response);
* ``noticeState`` is exactly ``DRAFT | APPROVED | ACTIVE | SUPERSEDED``;
* ``noticeApproved`` / ``acceptedForNewGrant`` are real booleans;
* ``acceptedForNewGrant`` depends on ``CONSENT_NOTICE_STATE_ENFORCED`` and is
  therefore **not** a substitute for a state check (a DRAFT is technically
  accepted while enforcement is off; a SUPERSEDED version looks approved and
  accepted);
* the grant endpoint itself rejects non-grantable states when enforcement is
  on, while withdrawal stays possible in every state.

No AWS, deployment, or activation is involved: DynamoDB is moto-local and all
flags are set per test.
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
    from jobsearch import consent_contract
    from jobsearch.consent_contract import (
        GRANTABLE_NOTICE_STATES, NOTICE_ACTIVE, NOTICE_APPROVED,
        NOTICE_DRAFT, NOTICE_STATES, NOTICE_SUPERSEDED, STATUS_GRANTED,
        STATUS_NOT_GRANTED, STATUS_WITHDRAWN, ConsentContext,
        ConsentContractError, NoticeVersion, catalog_payload, notice_version,
    )
    from jobsearch.consent_repository import ConsentRepository
except ImportError:  # pragma: no cover - dependency-free fallback
    boto3 = None
    mock_aws = lambda fn: fn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

CTX = ConsentContext("u1", "t1", "p1", "https://issuer")
PURPOSE = "application-storage"
VERSION = "1.0"
OTHER_PURPOSE = "marketing"


def _table(name="consents"):
    db = boto3.resource("dynamodb", region_name="eu-central-1")
    db.create_table(
        TableName=name,
        KeySchema=[{"AttributeName": "scopeKey", "KeyType": "HASH"},
                   {"AttributeName": "entityKey", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "scopeKey", "AttributeType": "S"},
                              {"AttributeName": "entityKey", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return ConsentRepository(name, db)


def _entry(**changes):
    return replace(notice_version(PURPOSE, VERSION), **changes)


def _catalog(enforced, entry=None):
    glob = {VERSION: entry} if entry is not None \
        else dict(consent_contract.NOTICE_REGISTRY[PURPOSE])
    with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE], glob):
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": enforced}):
            return catalog_payload(PURPOSE)


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class CatalogShapeTests(unittest.TestCase):
    """GET contract: top-level arrays, exact flags, per-purpose scoping."""

    def _get(self, query=None):
        import handler

        class _Repo:
            def get(self, ctx, purpose):
                return {"purpose": purpose, "status": STATUS_NOT_GRANTED,
                        "noticeVersion": None, "version": 0}

        event = {"httpMethod": "GET", "path": "/v1/partner/me/consents",
                 "headers": {}, "queryStringParameters": query, "body": None}
        with patch.object(handler, "_consent_ctx", return_value=(CTX, None)), \
                patch.object(handler, "_consent_repo", return_value=_Repo()):
            return handler._handle_consent_routes(
                event, None, "GET", "/v1/partner/me/consents")

    def test_catalog_is_a_top_level_array_of_objects(self):
        body = json.loads(self._get({"purpose": PURPOSE})["body"])
        self.assertIsInstance(body, dict)
        self.assertIsInstance(body["items"], list)
        self.assertIsInstance(body["catalog"], list)
        self.assertIsInstance(body["externalRefs"], list)
        self.assertGreaterEqual(len(body["catalog"]), 1)

    def test_catalog_entry_carries_the_fields_the_partner_gate_reads(self):
        body = json.loads(self._get({"purpose": PURPOSE})["body"])
        entry = body["catalog"][0]
        for key in ("purpose", "noticeVersion", "noticeState",
                    "noticeApproved", "acceptedForNewGrant"):
            self.assertIn(key, entry)
        self.assertEqual(PURPOSE, entry["purpose"])
        self.assertEqual(VERSION, entry["noticeVersion"])
        # Strict JSON booleans, never "true"/1/null.
        self.assertIs(type(entry["noticeApproved"]), bool)
        self.assertIs(type(entry["acceptedForNewGrant"]), bool)
        # Legal references stay server-side metadata but are still not secrets.
        self.assertIn("legalApprovalRef", entry)
        self.assertNotIn("privacyPolicyVersion", entry)

    def test_catalog_is_scoped_to_the_requested_purpose(self):
        extra = NoticeVersion(purpose=OTHER_PURPOSE, version="2.0",
                              state=NOTICE_ACTIVE,
                              legal_approval_ref="LEGAL-OTHER-2")
        with patch.dict(consent_contract.CONSENT_PURPOSES,
                        {OTHER_PURPOSE: frozenset({"2.0"})}), \
                patch.dict(consent_contract.NOTICE_REGISTRY,
                           {OTHER_PURPOSE: {"2.0": extra}}):
            single = json.loads(self._get({"purpose": PURPOSE})["body"])
            everything = json.loads(self._get(None)["body"])
        self.assertEqual([PURPOSE],
                         [e["purpose"] for e in single["catalog"]])
        self.assertEqual([PURPOSE],
                         [i["purpose"] for i in single["items"]])
        self.assertEqual(
            sorted([PURPOSE, OTHER_PURPOSE]),
            sorted([e["purpose"] for e in everything["catalog"]]))

    def test_unknown_purpose_fails_closed_instead_of_returning_an_empty_catalog(self):
        import handler

        event = {"httpMethod": "GET", "path": "/v1/partner/me/consents",
                 "headers": {}, "queryStringParameters": {"purpose": "unknown"},
                 "body": None}
        with patch.object(handler, "_consent_ctx", return_value=(CTX, None)), \
                patch.object(handler, "_consent_repo", return_value=object()):
            response = handler._handle_consent_routes(
                event, None, "GET", "/v1/partner/me/consents")
        body = json.loads(response["body"])
        self.assertEqual(404, response["statusCode"])
        self.assertEqual("UNKNOWN_PURPOSE", body["code"])

    def test_grant_response_does_not_include_a_catalog(self):
        """The catalogue lives on GET; POST must be re-read, not assumed."""
        import handler

        class _Repo:
            def grant(self, ctx, purpose, notice_version):
                return {"purpose": purpose, "status": STATUS_GRANTED,
                        "noticeVersion": notice_version, "version": 1}

        event = {"httpMethod": "POST", "path": "/v1/partner/me/consents",
                 "headers": {}, "body": json.dumps(
                     {"purpose": PURPOSE, "noticeVersion": VERSION})}
        with patch.object(handler, "_consent_ctx", return_value=(CTX, None)), \
                patch.object(handler, "_consent_repo", return_value=_Repo()):
            response = handler._handle_consent_routes(
                event, None, "POST", "/v1/partner/me/consents")
        self.assertEqual({"consent"}, set(json.loads(response["body"])))


class NoticeStateSemanticsTests(unittest.TestCase):
    """Enum, flag matrix, and the reason a state check is mandatory."""

    def test_state_enum_is_exactly_four_uppercase_values(self):
        self.assertEqual(
            {"DRAFT", "APPROVED", "ACTIVE", "SUPERSEDED"}, set(NOTICE_STATES))
        self.assertEqual({"APPROVED", "ACTIVE"}, set(GRANTABLE_NOTICE_STATES))
        self.assertEqual("ACTIVE", NOTICE_ACTIVE)
        self.assertNotIn("PUBLISHED", NOTICE_STATES)

    def test_flag_matrix_with_enforcement_on_and_off(self):
        expected = {
            NOTICE_DRAFT: (False, True, False),
            NOTICE_APPROVED: (True, True, True),
            NOTICE_ACTIVE: (True, True, True),
            NOTICE_SUPERSEDED: (True, True, False),
        }
        for state, (approved, accepted_off, accepted_on) in expected.items():
            entry = _entry(state=state, legal_approval_ref="LEGAL-1")
            off = _catalog("false", entry)[0]
            on = _catalog("true", entry)[0]
            self.assertEqual(approved, off["noticeApproved"], state)
            self.assertEqual(approved, on["noticeApproved"], state)
            self.assertEqual(state in GRANTABLE_NOTICE_STATES,
                             off["grantableWhenEnforced"], state)
            self.assertEqual(accepted_off, off["acceptedForNewGrant"], state)
            self.assertEqual(accepted_on, on["acceptedForNewGrant"], state)
            # acceptedForNewGrant is always a strict boolean.
            self.assertIs(type(off["acceptedForNewGrant"]), bool)
            self.assertIs(type(on["acceptedForNewGrant"]), bool)

    def test_approved_is_legitimately_grantable_under_enforcement(self):
        """APPROVED is grantable, so an ACTIVE-only gate is over-strict.

        This is the documented contract (CONSENT-V1 §9a) and matches
        ``GRANTABLE_NOTICE_STATES``. A partner that accepts only ACTIVE still
        fails safe, but it would block a correctly approved notice.
        """
        entry = _entry(state=NOTICE_APPROVED, legal_approval_ref="LEGAL-1")
        catalog = _catalog("true", entry)[0]
        self.assertEqual(NOTICE_APPROVED, catalog["noticeState"])
        self.assertIn(catalog["noticeState"], GRANTABLE_NOTICE_STATES)
        self.assertTrue(catalog["noticeApproved"])
        self.assertTrue(catalog["acceptedForNewGrant"])
        self.assertNotEqual(NOTICE_ACTIVE, catalog["noticeState"])

    def test_approved_and_accepted_flags_alone_do_not_imply_grantable(self):
        """SUPERSEDED looks approved+accepted while enforcement is off.

        Relying on ``noticeApproved && acceptedForNewGrant`` without a state
        check would therefore accept a superseded notice for a *new* grant.
        """
        entry = _entry(state=NOTICE_SUPERSEDED, legal_approval_ref="LEGAL-1")
        catalog = _catalog("false", entry)[0]
        self.assertTrue(catalog["noticeApproved"])
        self.assertTrue(catalog["acceptedForNewGrant"])
        self.assertFalse(catalog["grantableWhenEnforced"])

    def test_current_notice_1_0_is_draft_without_legal_approval(self):
        current = notice_version(PURPOSE, VERSION)
        self.assertIsNotNone(current)
        self.assertEqual(NOTICE_DRAFT, current.state)
        self.assertIsNone(current.legal_approval_ref)
        self.assertFalse(current.approved)
        self.assertFalse(current.grantable)


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class GrantAndWithdrawGateTests(unittest.TestCase):
    """Server-side defence in depth and withdrawal availability."""

    @mock_aws
    def test_draft_grant_is_accepted_only_while_enforcement_is_off(self):
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
            granted = _table().grant(CTX, PURPOSE, VERSION)
        self.assertEqual(STATUS_GRANTED, granted["status"])
        self.assertEqual(NOTICE_DRAFT, granted["noticeState"])
        self.assertFalse(granted["noticeApproved"])

    @mock_aws
    def test_draft_grant_is_rejected_with_422_semantics_under_enforcement(self):
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
            repo = _table()
            with self.assertRaises(ConsentContractError) as caught:
                repo.grant(CTX, PURPOSE, VERSION)
            # The handler maps this to 422 NOTICE_NOT_ACTIVE.
            self.assertEqual("NOTICE_NOT_ACTIVE", caught.exception.code)
            self.assertEqual(STATUS_NOT_GRANTED,
                             repo.get(CTX, PURPOSE)["status"])

    @mock_aws
    def test_approved_and_active_grants_pass_under_enforcement(self):
        for state in (NOTICE_APPROVED, NOTICE_ACTIVE):
            entry = _entry(state=state, legal_approval_ref="LEGAL-1")
            with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                            {VERSION: entry}):
                with patch.dict(
                        os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
                    granted = _table(f"consents-{state.lower()}").grant(
                        CTX, PURPOSE, VERSION)
            self.assertEqual(STATUS_GRANTED, granted["status"])
            self.assertEqual(state, granted["noticeState"])
            self.assertTrue(granted["noticeApproved"])

    @mock_aws
    def test_superseded_new_grant_is_rejected_under_enforcement(self):
        entry = _entry(state=NOTICE_SUPERSEDED, legal_approval_ref="LEGAL-1")
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: entry}):
            with patch.dict(os.environ,
                            {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
                repo = _table()
                with self.assertRaises(ConsentContractError) as caught:
                    repo.grant(CTX, PURPOSE, VERSION)
        self.assertEqual("NOTICE_NOT_ACTIVE", caught.exception.code)

    @mock_aws
    def test_withdrawal_remains_possible_in_every_notice_state(self):
        for state in (NOTICE_DRAFT, NOTICE_SUPERSEDED):
            # Record the grant while enforcement is off (technical state).
            with patch.dict(os.environ,
                            {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
                repo = _table(f"consents-{state.lower()}")
                repo.grant(CTX, PURPOSE, VERSION)
            entry = _entry(state=state)
            with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                            {VERSION: entry}):
                with patch.dict(
                        os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
                    withdrawn = repo.withdraw(CTX, PURPOSE)
            self.assertEqual(STATUS_WITHDRAWN, withdrawn["status"], state)
            self.assertEqual(2, withdrawn["version"], state)

    @mock_aws
    def test_republishing_a_draft_does_not_rewrite_an_existing_grant(self):
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
            repo = _table()
            repo.grant(CTX, PURPOSE, VERSION)
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
            status = repo.get(CTX, PURPOSE)
        self.assertEqual(STATUS_GRANTED, status["status"])
        self.assertEqual(VERSION, status["noticeVersion"])
        self.assertEqual(NOTICE_DRAFT, status["noticeState"])


if __name__ == "__main__":
    unittest.main()
