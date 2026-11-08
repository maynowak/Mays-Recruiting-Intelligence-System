"""Scoped ``ris-dev`` pilot: CONSENT_PILOT_ALLOWLIST and effective gates.

The pilot must activate consent/notice enforcement only for explicitly listed
synthetic identities, while the global flags stay ``false`` for the shared
Jobsearch partner edge. No AWS, deployment or live identity is involved.
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
        NOTICE_ACTIVE, NOTICE_APPROVED, NOTICE_DRAFT, NOTICE_SUPERSEDED,
        STATUS_GRANTED, STATUS_WITHDRAWN, ConsentContext,
        ConsentContractError, notice_version,
    )
    from jobsearch.consent_repository import ConsentRepository
except ImportError:  # pragma: no cover - dependency-free fallback
    boto3 = None
    mock_aws = lambda fn: fn

from tests.application_e2e_harness import synthetic_create
from tests.consent_e2e_harness import (
    PRIMARY, SECONDARY_USER, ConsentGateDenied, JointConsentE2EHarness,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

import handler  # noqa: E402

PURPOSE = "application-storage"
VERSION = "1.0"
LEGAL_REF = "SYNTHETIC-PILOT-LEGAL-REF-NOT-REAL"
ISSUER = "https://synthetic.invalid/issuer/pilot"
SUB = "synthetic-pilot-user-1"
PILOT_ENTRY = f"{ISSUER}|{SUB}"


def _env(**values):
    base = {
        "APPLICATION_CONSENT_ENFORCED": "false",
        "CONSENT_NOTICE_STATE_ENFORCED": "false",
        "CONSENT_PILOT_ALLOWLIST": "",
    }
    base.update(values)
    return patch.dict(os.environ, base)


def _entry(**changes):
    return replace(notice_version(PURPOSE, VERSION), **changes)


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


def _ctx(sub=SUB, issuer=ISSUER):
    return ConsentContext(sub, "t1", "p1", issuer)


class PilotAllowlistParsingTests(unittest.TestCase):
    def test_empty_or_unset_means_no_pilot_identity(self):
        for value in ("", "   ", ",", "\n", "|", "||", "issuer-only"):
            with _env(CONSENT_PILOT_ALLOWLIST=value):
                self.assertEqual(frozenset(), handler._consent_pilot_identities())
                self.assertFalse(handler._is_consent_pilot_identity(ISSUER, SUB))

    def test_comma_and_newline_separated_entries_are_parsed(self):
        other = f"https://other.invalid|user-2"
        with _env(CONSENT_PILOT_ALLOWLIST=f"{PILOT_ENTRY},{other}"):
            self.assertEqual(
                frozenset({(ISSUER, SUB), ("https://other.invalid", "user-2")}),
                handler._consent_pilot_identities())
        with _env(CONSENT_PILOT_ALLOWLIST=f"{PILOT_ENTRY}\n{other}"):
            self.assertEqual(2, len(handler._consent_pilot_identities()))

    def test_issuer_and_sub_are_trimmed_and_trailing_slash_normalized(self):
        with _env(CONSENT_PILOT_ALLOWLIST=f"  {ISSUER}/ | {SUB} "):
            self.assertTrue(handler._is_consent_pilot_identity(ISSUER, SUB))
            self.assertTrue(handler._is_consent_pilot_identity(ISSUER + "/", SUB))

    def test_malformed_entries_are_ignored_and_cannot_widen_the_scope(self):
        with _env(CONSENT_PILOT_ALLOWLIST=f"garbage,{ISSUER}|,|{SUB},{PILOT_ENTRY}"):
            self.assertEqual(frozenset({(ISSUER, SUB)}),
                             handler._consent_pilot_identities())

    def test_match_is_exact_on_both_fields(self):
        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY):
            self.assertTrue(handler._is_consent_pilot_identity(ISSUER, SUB))
            self.assertFalse(handler._is_consent_pilot_identity(ISSUER, SUB + "x"))
            self.assertFalse(handler._is_consent_pilot_identity(ISSUER + "x", SUB))
            self.assertFalse(handler._is_consent_pilot_identity(
                "https://other.invalid", SUB))


class EffectiveGateTests(unittest.TestCase):
    def test_global_false_plus_pilot_identity_enables_both_gates(self):
        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY):
            self.assertTrue(
                handler._consent_enforced_for(_ctx()))
            self.assertTrue(
                handler._consent_notice_state_enforced_for(_ctx()))

    def test_global_false_plus_non_pilot_keeps_gates_off(self):
        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY):
            other = _ctx(sub="someone-else")
            self.assertFalse(handler._consent_enforced_for(other))
            self.assertFalse(handler._consent_notice_state_enforced_for(other))

    def test_global_true_applies_to_non_pilot(self):
        with _env(APPLICATION_CONSENT_ENFORCED="true",
                  CONSENT_NOTICE_STATE_ENFORCED="true",
                  CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY):
            other = _ctx(sub="someone-else")
            self.assertTrue(handler._consent_enforced_for(other))
            self.assertTrue(handler._consent_notice_state_enforced_for(other))


class HandlerGateTests(unittest.TestCase):
    def _denied(self, ctx):
        class _Repo:
            def has_consent(self, consent_ctx, purpose):
                return False

        with patch.object(handler, "_consent_repo", return_value=_Repo()):
            return handler._application_consent_error(ctx)

    def test_pilot_identity_is_gated_while_global_flag_is_false(self):
        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY):
            denied = self._denied(_ctx())
        self.assertIsNotNone(denied)
        self.assertEqual(403, denied["statusCode"])
        self.assertEqual("CONSENT_REQUIRED", json.loads(denied["body"])["code"])

    def test_non_pilot_identity_is_not_gated_by_the_pilot_list(self):
        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY):
            self.assertIsNone(self._denied(_ctx(sub="someone-else")))

    def test_pilot_gate_fails_closed_when_the_store_fails(self):
        def broken():
            raise RuntimeError("store down")

        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY), \
                patch.object(handler, "_consent_repo", side_effect=broken):
            denied = handler._application_consent_error(_ctx())
        self.assertIsNotNone(denied)
        self.assertEqual(403, denied["statusCode"])

    def test_pilot_gate_allows_when_consent_exists(self):
        class _Repo:
            def has_consent(self, consent_ctx, purpose):
                return True

        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY), \
                patch.object(handler, "_consent_repo", return_value=_Repo()):
            self.assertIsNone(handler._application_consent_error(_ctx()))


class HandlerGrantWiringTests(unittest.TestCase):
    def _grant(self, ctx):
        calls = []

        class _Repo:
            def grant(self, ctx, purpose, notice_version,
                      enforce_notice_state=None, **kwargs):
                calls.append(enforce_notice_state)
                return {"purpose": purpose, "status": STATUS_GRANTED,
                        "noticeVersion": notice_version, "version": 1}

        event = {"httpMethod": "POST", "path": "/v1/partner/me/consents",
                 "headers": {}, "queryStringParameters": None,
                 "body": json.dumps(
                     {"purpose": PURPOSE, "noticeVersion": VERSION})}
        with patch.object(handler, "_consent_ctx", return_value=(ctx, None)), \
                patch.object(handler, "_consent_repo", return_value=_Repo()):
            response = handler._handle_consent_routes(
                event, None, "POST", "/v1/partner/me/consents")
        self.assertEqual(200, response["statusCode"])
        return calls[0]

    def test_pilot_identity_forces_notice_enforcement(self):
        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY):
            self.assertIs(True, self._grant(_ctx()))

    def test_non_pilot_identity_keeps_global_false(self):
        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY):
            self.assertIs(False, self._grant(_ctx(sub="someone-else")))

    def test_global_notice_flag_still_applies_to_non_pilot(self):
        with _env(CONSENT_PILOT_ALLOWLIST=PILOT_ENTRY,
                  CONSENT_NOTICE_STATE_ENFORCED="true"):
            self.assertIs(True, self._grant(_ctx(sub="someone-else")))


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class ScopedRepositoryGrantTests(unittest.TestCase):
    @mock_aws
    def test_draft_grant_rejected_for_pilot_enforcement(self):
        draft = _entry(state=NOTICE_DRAFT, legal_approval_ref=None)
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: draft}):
            with patch.dict(os.environ,
                            {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
                repo = _table()
                with self.assertRaises(ConsentContractError) as caught:
                    repo.grant(_ctx(), PURPOSE, VERSION,
                               enforce_notice_state=True)
        self.assertEqual("NOTICE_NOT_ACTIVE", caught.exception.code)
        self.assertEqual("NOT_GRANTED",
                         repo.get(_ctx(), PURPOSE)["status"])

    @mock_aws
    def test_draft_grant_allowed_for_non_pilot_global_false(self):
        draft = _entry(state=NOTICE_DRAFT, legal_approval_ref=None)
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: draft}):
            with patch.dict(os.environ,
                            {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
                granted = _table().grant(
                    _ctx(), PURPOSE, VERSION, enforce_notice_state=False)
        self.assertEqual(STATUS_GRANTED, granted["status"])
        self.assertEqual(NOTICE_DRAFT, granted["noticeState"])

    @mock_aws
    def test_superseded_rejected_and_approved_active_allowed(self):
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
            for state, name, allowed in (
                    (NOTICE_SUPERSEDED, "consents-superseded", False),
                    (NOTICE_DRAFT, "consents-draft", False),
                    (NOTICE_APPROVED, "consents-approved", True),
                    (NOTICE_ACTIVE, "consents-active", True)):
                entry = _entry(state=state, legal_approval_ref=LEGAL_REF)
                with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                                {VERSION: entry}):
                    repo = _table(name)
                    if allowed:
                        granted = repo.grant(
                            _ctx(), PURPOSE, VERSION,
                            enforce_notice_state=True)
                        self.assertEqual(STATUS_GRANTED, granted["status"])
                    else:
                        with self.assertRaises(ConsentContractError) as caught:
                            repo.grant(_ctx(), PURPOSE, VERSION,
                                       enforce_notice_state=True)
                        self.assertEqual("NOTICE_NOT_ACTIVE",
                                         caught.exception.code, state)

    @mock_aws
    def test_idempotent_repeat_and_withdrawal_survive_pilot_enforcement(self):
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "false"}):
            repo = _table()
            repo.grant(_ctx(), PURPOSE, VERSION, enforce_notice_state=False)
        superseded = _entry(state=NOTICE_SUPERSEDED,
                            legal_approval_ref=LEGAL_REF)
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: superseded}):
            again = repo.grant(_ctx(), PURPOSE, VERSION,
                               enforce_notice_state=True)
            self.assertEqual(1, again["version"])
            withdrawn = repo.withdraw(_ctx(), PURPOSE)
            self.assertEqual(STATUS_WITHDRAWN, withdrawn["status"])
            with self.assertRaises(ConsentContractError) as caught:
                repo.grant(_ctx(), PURPOSE, VERSION,
                           enforce_notice_state=True)
            self.assertEqual("NOTICE_NOT_ACTIVE", caught.exception.code)


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class SyntheticActivePilotE2ETests(unittest.TestCase):
    """Pilot identity + ACTIVE fixture: full storage flow with global gates off."""

    APPS = "synthetic-pilot-scoped-applications"
    CONSENTS = "synthetic-pilot-scoped-consents"

    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SESSION_TOKEN": "testing",
            "AWS_DEFAULT_REGION": "eu-central-1",
            "AWS_EC2_METADATA_DISABLED": "true",
            "RIS_CURSOR_SECRET": "local-only-pilot-scope-secret",
            # Global gates stay off for the shared partner edge.
            "APPLICATION_CONSENT_ENFORCED": "false",
            "CONSENT_NOTICE_STATE_ENFORCED": "false",
            "CONSENT_PILOT_ALLOWLIST": (
                f"{PRIMARY.issuer}|{PRIMARY.user_id}"),
        })
        self.env.start()
        self.aws = mock_aws()
        self.aws.start()
        db = boto3.resource("dynamodb", region_name="eu-central-1")
        db.create_table(
            TableName=self.APPS,
            KeySchema=[
                {"AttributeName": "applicationId", "KeyType": "HASH"},
                {"AttributeName": "entityKey", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "applicationId", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"},
                {"AttributeName": "ownerKey", "AttributeType": "S"},
                {"AttributeName": "updatedAt", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "gsi-owner",
                "KeySchema": [
                    {"AttributeName": "ownerKey", "KeyType": "HASH"},
                    {"AttributeName": "updatedAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 1,
                                          "WriteCapacityUnits": 1},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        db.create_table(
            TableName=self.CONSENTS,
            KeySchema=[
                {"AttributeName": "scopeKey", "KeyType": "HASH"},
                {"AttributeName": "entityKey", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "scopeKey", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        self.harness = JointConsentE2EHarness(
            db, self.APPS, self.CONSENTS, enforced=True)
        self.active = _entry(state=NOTICE_ACTIVE, legal_approval_ref=LEGAL_REF)

    def tearDown(self):
        self.aws.stop()
        self.env.stop()

    def _handler_gate(self, identity=PRIMARY):
        with patch.object(handler, "_consent_repo",
                          lambda: self.harness.consent):
            return handler._application_consent_error(
                identity.consent_context())

    def test_active_notice_full_flow_for_the_pilot_identity(self):
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: self.active}):
            harness = self.harness

            # No consent -> pilot write denied even though the global flag is off.
            self.assertFalse(harness.write_allowed())
            with self.assertRaises(ConsentGateDenied):
                harness.create(synthetic_create(1))
            denied = self._handler_gate()
            self.assertEqual(403, denied["statusCode"])
            self.assertEqual("CONSENT_REQUIRED",
                             json.loads(denied["body"])["code"])

            # The scoped notice enforcement allows the ACTIVE grant.
            granted = harness.consent.grant(
                PRIMARY.consent_context(), PURPOSE, VERSION,
                enforce_notice_state=True)
            self.assertEqual(STATUS_GRANTED, granted["status"])
            self.assertEqual(NOTICE_ACTIVE, granted["noticeState"])
            self.assertTrue(granted["noticeApproved"])
            self.assertTrue(granted["acceptedForNewGrant"])
            self.assertIsNone(self._handler_gate())

            created = harness.create(synthetic_create(1))
            app_id = created["applicationId"]
            updated = harness.patch(app_id, {
                "job": {"jobId": "synthetic-pilot-updated"},
                "expectedVersion": 1,
            })
            self.assertEqual(2, updated["version"])

            withdrawn = harness.withdraw()
            self.assertEqual(STATUS_WITHDRAWN, withdrawn["status"])
            self.assertEqual(403, self._handler_gate()["statusCode"])
            with self.assertRaises(ConsentGateDenied):
                harness.create(synthetic_create(2))

            current = harness.get(app_id)
            self.assertEqual(2, current["version"])
            self.assertEqual(app_id, harness.get(app_id)["applicationId"])
            self.assertEqual(
                app_id,
                harness.export(app_id)["application"]["applicationId"])
            harness.delete(app_id, current["version"])
            with self.assertRaises(Exception):
                harness.get(app_id)

    def test_non_pilot_identity_keeps_global_false_behavior(self):
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: self.active}):
            # A second user in the same partner scope is not in the allowlist.
            self.assertIsNone(self._handler_gate(SECONDARY_USER))
            # No consent row exists for that user and no 403 is produced.
            self.assertFalse(
                self.harness.consent.has_consent(
                    SECONDARY_USER.consent_context(), PURPOSE))


if __name__ == "__main__":
    unittest.main()
