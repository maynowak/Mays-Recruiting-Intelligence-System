"""ApplicationV1 consent proof: Art. 9 categories and external text identity.

Companion to the Jobsearch v3 consent text
``application-storage-consent-2026-11-07-v3``. The RIS backend must store an
explicit, verifiable proof: user consent for special categories, the exact
category subset, and the external text version/hash. The proof is never
inferred from the notice version and never upgraded silently.
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
        ART9_EXTERNAL_TEXT_SHA256, ART9_EXTERNAL_TEXT_VERSION,
        NOTICE_ACTIVE, NOTICE_DRAFT, NOTICE_SUPERSEDED, SPECIAL_CATEGORY_CODES,
        SPECIAL_CATEGORY_ORDER, STATUS_GRANTED, STATUS_NOT_GRANTED,
        STATUS_WITHDRAWN, ConsentContext, ConsentContractError,
        notice_version, validate_consent_proof, validate_external_text,
        validate_special_category_consent,
    )
    from jobsearch.consent_repository import ConsentRepository
except ImportError:  # pragma: no cover - dependency-free fallback
    boto3 = None
    mock_aws = lambda fn: fn

from tests.application_e2e_harness import synthetic_create
from tests.consent_e2e_harness import (
    PRIMARY, ConsentGateDenied, JointConsentE2EHarness,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

import handler  # noqa: E402

PURPOSE = "application-storage"
VERSION = "1.0"
LEGAL_REF = "SYNTHETIC-LEGAL-REF-NOT-REAL"

V3 = "application-storage-consent-2026-11-07-v3"
V3_SHA256 = "696f9e66d8098b2dce56a93418ba598145b669934662e2b52d9a332731517668"
V2 = "application-storage-consent-2026-11-07-v2"
V2_SHA256 = "232cc8206261b5d14f7a269f63a58320f76eea435a65f7e039b25c62d26da0ca"

CATEGORIES = [
    "health",
    "religious_or_philosophical_beliefs",
    "trade_union_membership",
    "political_opinions",
    "sexual_orientation",
    "biometric_data",
    "genetic_data",
    "racial_or_ethnic_origin",
]


def _ctx(sub="u1"):
    return ConsentContext(sub, "t1", "p1", "https://issuer")


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


def _grant(repo, *, categories=CATEGORIES, consent=True, version=V3,
           sha256=V3_SHA256, sub="u1", enforce=None):
    return repo.grant(
        _ctx(sub), PURPOSE, VERSION,
        enforce_notice_state=enforce,
        special_categories_consent=consent,
        special_categories=categories,
        external_text_version=version,
        external_text_sha256=sha256,
    )


class SpecialCategoryValidationTests(unittest.TestCase):
    def test_all_codes_are_the_stable_v3_set(self):
        self.assertEqual(frozenset(CATEGORIES), SPECIAL_CATEGORY_CODES)
        self.assertEqual(tuple(CATEGORIES), tuple(SPECIAL_CATEGORY_ORDER))

    def test_true_requires_a_non_empty_subset(self):
        for value in (None, [], ()):
            with self.assertRaises(ConsentContractError) as caught:
                validate_special_category_consent(True, value)
            self.assertEqual("SPECIAL_CATEGORIES_REQUIRED",
                             caught.exception.code)

    def test_false_requires_no_categories(self):
        self.assertEqual((False, []),
                         validate_special_category_consent(False, None))
        self.assertEqual((False, []),
                         validate_special_category_consent(False, []))
        with self.assertRaises(ConsentContractError) as caught:
            validate_special_category_consent(False, ["health"])
        self.assertEqual("SPECIAL_CATEGORIES_WITHOUT_CONSENT",
                         caught.exception.code)

    def test_consent_must_be_a_real_boolean(self):
        for value in (1, "true", None, "yes"):
            with self.assertRaises(ConsentContractError) as caught:
                validate_special_category_consent(value, ["health"])
            self.assertEqual("INVALID_SPECIAL_CATEGORY_CONSENT",
                             caught.exception.code)

    def test_unknown_and_duplicate_codes_are_rejected(self):
        with self.assertRaises(ConsentContractError) as caught:
            validate_special_category_consent(True, ["health", "salary"])
        self.assertEqual("UNKNOWN_SPECIAL_CATEGORY", caught.exception.code)
        with self.assertRaises(ConsentContractError) as caught:
            validate_special_category_consent(True, ["health", "health"])
        self.assertEqual("DUPLICATE_SPECIAL_CATEGORY", caught.exception.code)

    def test_category_order_is_canonical_and_not_caller_order(self):
        consent, ordered = validate_special_category_consent(
            True, ["genetic_data", "health", "political_opinions"])
        self.assertTrue(consent)
        self.assertEqual(
            [code for code in CATEGORIES
             if code in {"genetic_data", "health", "political_opinions"}],
            ordered)


class ExternalTextValidationTests(unittest.TestCase):
    def test_v3_and_historical_v2_are_known_with_exact_hash(self):
        self.assertEqual((V3, V3_SHA256),
                         validate_external_text(PURPOSE, V3, V3_SHA256))
        self.assertEqual((V2, V2_SHA256),
                         validate_external_text(PURPOSE, V2, V2_SHA256))

    def test_absent_pair_is_allowed(self):
        self.assertEqual((None, None),
                         validate_external_text(PURPOSE, None, None))

    def test_partial_or_malformed_pair_is_rejected(self):
        for version, digest in (
                (V3, None), (None, V3_SHA256), ("", V3_SHA256),
                (V3, ""), (V3, "not-a-hash")):
            with self.assertRaises(ConsentContractError) as caught:
                validate_external_text(PURPOSE, version, digest)
            self.assertEqual("INVALID_EXTERNAL_TEXT", caught.exception.code)

    def test_unknown_version_is_rejected(self):
        with self.assertRaises(ConsentContractError) as caught:
            validate_external_text(PURPOSE, "application-storage-consent-x",
                                   V3_SHA256)
        self.assertEqual("UNKNOWN_EXTERNAL_TEXT_VERSION",
                         caught.exception.code)

    def test_hash_mismatch_and_unpinned_ref_are_rejected(self):
        with self.assertRaises(ConsentContractError) as caught:
            validate_external_text(PURPOSE, V3, V2_SHA256)
        self.assertEqual("EXTERNAL_TEXT_HASH_MISMATCH", caught.exception.code)
        with self.assertRaises(ConsentContractError) as caught:
            validate_external_text(PURPOSE, "2026-11-04-draft-1", V3_SHA256)
        self.assertEqual("EXTERNAL_TEXT_HASH_MISMATCH", caught.exception.code)


class Art9TextBindingTests(unittest.TestCase):
    """Special-category consent requires the current Art. 9 text."""

    def _proof(self, consent, categories, version, digest):
        return validate_consent_proof(
            PURPOSE,
            special_categories_consent=consent,
            special_categories=categories,
            external_text_version=version,
            external_text_sha256=digest)

    def test_true_without_text_pair_is_rejected(self):
        for version, digest in (
                (None, None), ("", ""), (V3, None), (None, V3_SHA256)):
            with self.assertRaises(ConsentContractError) as caught:
                self._proof(True, ["health"], version, digest)
            self.assertEqual(
                "EXTERNAL_TEXT_REQUIRED_FOR_SPECIAL_CATEGORIES",
                caught.exception.code)

    def test_true_with_historical_v2_text_is_not_art9(self):
        with self.assertRaises(ConsentContractError) as caught:
            self._proof(True, ["health"], V2, V2_SHA256)
        self.assertEqual("EXTERNAL_TEXT_NOT_ART9", caught.exception.code)

    def test_true_with_v3_text_is_accepted(self):
        consent, categories, version, digest = self._proof(
            True, ["health", "genetic_data"], V3, V3_SHA256)
        self.assertTrue(consent)
        self.assertEqual(["health", "genetic_data"], categories)
        self.assertEqual(ART9_EXTERNAL_TEXT_VERSION, version)
        self.assertEqual(ART9_EXTERNAL_TEXT_SHA256, digest)

    def test_false_without_text_is_accepted(self):
        self.assertEqual(
            (False, [], None, None),
            self._proof(False, None, None, None))

    def test_false_with_historical_text_keeps_legacy_compatibility(self):
        self.assertEqual(
            (False, [], V2, V2_SHA256),
            self._proof(False, [], V2, V2_SHA256))


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class GrantProofPersistenceTests(unittest.TestCase):
    @mock_aws
    def test_v3_grant_stores_proof_in_status_and_history(self):
        repo = _table()
        granted = _grant(repo, categories=CATEGORIES)
        self.assertEqual(STATUS_GRANTED, granted["status"])
        self.assertEqual(V3, granted["externalTextVersion"])
        self.assertEqual(V3_SHA256, granted["externalTextSha256"])
        self.assertTrue(granted["specialCategoriesConsent"])
        self.assertEqual(CATEGORIES, granted["specialCategories"])

        status = repo.get(_ctx(), PURPOSE)
        self.assertEqual(V3, status["externalTextVersion"])
        self.assertEqual(V3_SHA256, status["externalTextSha256"])
        self.assertTrue(status["specialCategoriesConsent"])
        self.assertEqual(CATEGORIES, status["specialCategories"])

        events, _ = repo.history(_ctx(), PURPOSE)
        self.assertEqual(1, len(events))
        self.assertEqual(V3, events[0]["externalTextVersion"])
        self.assertEqual(V3_SHA256, events[0]["externalTextSha256"])
        self.assertTrue(events[0]["specialCategoriesConsent"])
        self.assertEqual(CATEGORIES, events[0]["specialCategories"])

    @mock_aws
    def test_subset_is_stored_in_canonical_order(self):
        granted = _grant(
            _table(), categories=["health", "genetic_data",
                                  "racial_or_ethnic_origin"])
        self.assertEqual(["health", "genetic_data", "racial_or_ethnic_origin"],
                         granted["specialCategories"])

    @mock_aws
    def test_legacy_grant_without_proof_reports_fail_closed_defaults(self):
        granted = _grant(_table(), consent=False, categories=None,
                         version=None, sha256=None)
        self.assertFalse(granted["specialCategoriesConsent"])
        self.assertEqual([], granted["specialCategories"])
        self.assertIsNone(granted["externalTextVersion"])
        self.assertIsNone(granted["externalTextSha256"])

    @mock_aws
    def test_invalid_proof_is_rejected_before_any_write(self):
        repo = _table()
        cases = [
            dict(consent=False, categories=["health"]),
            dict(consent=True, categories=[]),
            dict(consent=True, categories=["health", "salary"]),
            dict(consent=True, categories=["health"], version="unknown",
                 sha256=V3_SHA256),
            dict(consent=True, categories=["health"], version=V3,
                 sha256=V2_SHA256),
        ]
        for kwargs in cases:
            with self.assertRaises(ConsentContractError):
                _grant(repo, **kwargs)
            self.assertEqual(STATUS_NOT_GRANTED,
                             repo.get(_ctx(), PURPOSE)["status"])
        events, _ = repo.history(_ctx(), PURPOSE)
        self.assertEqual([], events)

    @mock_aws
    def test_art9_consent_requires_the_external_text_pair(self):
        repo = _table()
        for version, digest in ((None, None), (V3, None), (None, V3_SHA256)):
            with self.assertRaises(ConsentContractError) as caught:
                _grant(repo, categories=["health"], version=version,
                       sha256=digest)
            self.assertEqual(
                "EXTERNAL_TEXT_REQUIRED_FOR_SPECIAL_CATEGORIES",
                caught.exception.code)
        self.assertEqual(STATUS_NOT_GRANTED,
                         repo.get(_ctx(), PURPOSE)["status"])

    @mock_aws
    def test_art9_consent_rejects_historical_v2_text(self):
        repo = _table()
        with self.assertRaises(ConsentContractError) as caught:
            _grant(repo, categories=["health"], version=V2, sha256=V2_SHA256)
        self.assertEqual("EXTERNAL_TEXT_NOT_ART9", caught.exception.code)
        self.assertEqual(STATUS_NOT_GRANTED,
                         repo.get(_ctx(), PURPOSE)["status"])
        events, _ = repo.history(_ctx(), PURPOSE)
        self.assertEqual([], events)

    @mock_aws
    def test_art9_grant_with_v3_text_is_accepted(self):
        granted = _grant(_table(), categories=["health"])
        self.assertTrue(granted["specialCategoriesConsent"])
        self.assertEqual(V3, granted["externalTextVersion"])
        self.assertEqual(V3_SHA256, granted["externalTextSha256"])

    @mock_aws
    def test_repeat_with_same_proof_is_idempotent(self):
        repo = _table()
        _grant(repo)
        again = _grant(repo)
        self.assertEqual(1, again["version"])
        events, _ = repo.history(_ctx(), PURPOSE)
        self.assertEqual(1, len(events))

    @mock_aws
    def test_existing_v3_grant_rejects_v2_art9_request(self):
        repo = _table()
        _grant(repo, categories=["health"])
        with self.assertRaises(ConsentContractError) as caught:
            _grant(repo, categories=["health"], version=V2, sha256=V2_SHA256)
        self.assertEqual("EXTERNAL_TEXT_NOT_ART9", caught.exception.code)
        status = repo.get(_ctx(), PURPOSE)
        self.assertEqual(V3, status["externalTextVersion"])
        self.assertEqual(V3_SHA256, status["externalTextSha256"])

    @mock_aws
    def test_different_valid_text_scope_requires_reconsent(self):
        v4 = "application-storage-consent-2026-11-07-v4"
        v4_sha = "a" * 64
        repo = _table()
        _grant(repo, categories=["health"])
        with patch.dict(
                consent_contract.EXTERNAL_NOTICE_REFS[PURPOSE],
                {v4: {"source": "mays-jobsearch",
                      "noticeState": NOTICE_DRAFT,
                      "noticeVersion": None,
                      "textSha256": v4_sha}}), \
                patch.object(consent_contract,
                             "ART9_EXTERNAL_TEXT_VERSION", v4), \
                patch.object(consent_contract,
                             "ART9_EXTERNAL_TEXT_SHA256", v4_sha):
            with self.assertRaises(ConsentContractError) as caught:
                _grant(repo, categories=["health"], version=v4,
                       sha256=v4_sha)
        self.assertEqual("RECONSENT_REQUIRED", caught.exception.code)
        status = repo.get(_ctx(), PURPOSE)
        self.assertEqual(V3, status["externalTextVersion"])
        self.assertEqual(1, status["version"])

    @mock_aws
    def test_different_category_scope_requires_reconsent(self):
        repo = _table()
        _grant(repo, categories=["health"])
        with self.assertRaises(ConsentContractError) as caught:
            _grant(repo, categories=["health", "genetic_data"])
        self.assertEqual("RECONSENT_REQUIRED", caught.exception.code)
        status = repo.get(_ctx(), PURPOSE)
        self.assertEqual(["health"], status["specialCategories"])

    @mock_aws
    def test_withdrawal_preserves_proof_and_allows_new_proof_after(self):
        repo = _table()
        _grant(repo, categories=["health"])
        withdrawn = repo.withdraw(_ctx(), PURPOSE)
        self.assertEqual(STATUS_WITHDRAWN, withdrawn["status"])
        self.assertTrue(withdrawn["specialCategoriesConsent"])
        self.assertEqual(["health"], withdrawn["specialCategories"])
        self.assertEqual(V3, withdrawn["externalTextVersion"])
        self.assertEqual(V3_SHA256, withdrawn["externalTextSha256"])

        events, _ = repo.history(_ctx(), PURPOSE)
        self.assertEqual(["WITHDRAWN", "GRANTED"], [e["event"] for e in events])
        for event in events:
            self.assertEqual(V3, event["externalTextVersion"])
            self.assertEqual(["health"], event["specialCategories"])

        regranted = _grant(repo, categories=["health", "genetic_data"])
        self.assertEqual(3, regranted["version"])
        self.assertEqual(V3, regranted["externalTextVersion"])
        self.assertEqual(["health", "genetic_data"],
                         regranted["specialCategories"])


class HandlerProofWiringTests(unittest.TestCase):
    def _post(self, body):
        recorded = {}

        class _Repo:
            def grant(self, ctx, purpose, notice_version, **kwargs):
                recorded.update(kwargs)
                recorded["notice_version"] = notice_version
                return {"purpose": purpose, "status": STATUS_GRANTED,
                        "noticeVersion": notice_version, "version": 1,
                        "specialCategoriesConsent": True,
                        "specialCategories": CATEGORIES,
                        "externalTextVersion": V3,
                        "externalTextSha256": V3_SHA256}

        event = {"httpMethod": "POST", "path": "/v1/partner/me/consents",
                 "headers": {}, "queryStringParameters": None,
                 "body": json.dumps(body)}
        with patch.object(handler, "_consent_ctx", return_value=(_ctx(), None)), \
                patch.object(handler, "_consent_repo", return_value=_Repo()):
            return handler._handle_consent_routes(
                event, None, "POST", "/v1/partner/me/consents"), recorded

    def test_post_passes_all_four_server_owned_fields(self):
        response, recorded = self._post({
            "purpose": PURPOSE, "noticeVersion": VERSION,
            "specialCategoriesConsent": True,
            "specialCategories": CATEGORIES,
            "externalTextVersion": V3,
            "externalTextSha256": V3_SHA256,
        })
        self.assertEqual(200, response["statusCode"])
        self.assertTrue(recorded["special_categories_consent"])
        self.assertEqual(CATEGORIES, recorded["special_categories"])
        self.assertEqual(V3, recorded["external_text_version"])
        self.assertEqual(V3_SHA256, recorded["external_text_sha256"])

    def test_post_defaults_to_no_special_consent(self):
        _, recorded = self._post({"purpose": PURPOSE, "noticeVersion": VERSION})
        self.assertIs(False, recorded["special_categories_consent"])
        self.assertIsNone(recorded["special_categories"])
        self.assertIsNone(recorded["external_text_version"])
        self.assertIsNone(recorded["external_text_sha256"])

    def test_reconsent_required_maps_to_409(self):
        class _Repo:
            def grant(self, ctx, purpose, notice_version, **kwargs):
                raise ConsentContractError(
                    "RECONSENT_REQUIRED", "different proof")

        event = {"httpMethod": "POST", "path": "/v1/partner/me/consents",
                 "headers": {}, "queryStringParameters": None,
                 "body": json.dumps({"purpose": PURPOSE,
                                     "noticeVersion": VERSION})}
        with patch.object(handler, "_consent_ctx", return_value=(_ctx(), None)), \
                patch.object(handler, "_consent_repo", return_value=_Repo()):
            response = handler._handle_consent_routes(
                event, None, "POST", "/v1/partner/me/consents")
        self.assertEqual(409, response["statusCode"])
        self.assertEqual("RECONSENT_REQUIRED",
                         json.loads(response["body"])["code"])

    def test_get_and_history_are_passed_through(self):
        class _Repo:
            def get(self, ctx, purpose):
                return {"purpose": purpose, "status": STATUS_GRANTED,
                        "noticeVersion": VERSION, "version": 1,
                        "specialCategoriesConsent": True,
                        "specialCategories": CATEGORIES,
                        "externalTextVersion": V3,
                        "externalTextSha256": V3_SHA256}

            def history(self, ctx, purpose, **kwargs):
                return ([{"event": "GRANTED",
                          "specialCategoriesConsent": True,
                          "specialCategories": CATEGORIES,
                          "externalTextVersion": V3,
                          "externalTextSha256": V3_SHA256}], None)

        get_event = {"httpMethod": "GET", "path": "/v1/partner/me/consents",
                     "headers": {}, "queryStringParameters": {"purpose": PURPOSE},
                     "body": None}
        hist_event = {"httpMethod": "GET",
                      "path": "/v1/partner/me/consents/history",
                      "headers": {},
                      "queryStringParameters": {"purpose": PURPOSE},
                      "body": None}
        with patch.object(handler, "_consent_ctx", return_value=(_ctx(), None)), \
                patch.object(handler, "_consent_repo", return_value=_Repo()):
            get_response = handler._handle_consent_routes(
                get_event, None, "GET", "/v1/partner/me/consents")
            hist_response = handler._handle_consent_routes(
                hist_event, None, "GET", "/v1/partner/me/consents/history")
        item = json.loads(get_response["body"])["items"][0]
        self.assertEqual(V3, item["externalTextVersion"])
        self.assertEqual(CATEGORIES, item["specialCategories"])
        event = json.loads(hist_response["body"])["items"][0]
        self.assertEqual(V3_SHA256, event["externalTextSha256"])


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class ProofAfterWithdrawalApplicationRightsTests(unittest.TestCase):
    APPS = "synthetic-proof-applications"
    CONSENTS = "synthetic-proof-consents"

    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SESSION_TOKEN": "testing",
            "AWS_DEFAULT_REGION": "eu-central-1",
            "AWS_EC2_METADATA_DISABLED": "true",
            "RIS_CURSOR_SECRET": "local-only-proof-secret",
            "APPLICATION_CONSENT_ENFORCED": "true",
            "CONSENT_NOTICE_STATE_ENFORCED": "true",
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
            KeySchema=[{"AttributeName": "scopeKey", "KeyType": "HASH"},
                       {"AttributeName": "entityKey", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "scopeKey", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        self.harness = JointConsentE2EHarness(
            db, self.APPS, self.CONSENTS, enforced=True)
        self.active = replace(notice_version(PURPOSE, VERSION),
                              state=NOTICE_ACTIVE,
                              legal_approval_ref=LEGAL_REF)

    def tearDown(self):
        self.aws.stop()
        self.env.stop()

    def _handler_gate(self):
        with patch.object(handler, "_consent_repo",
                          lambda: self.harness.consent):
            return handler._application_consent_error(
                PRIMARY.consent_context())

    def test_withdrawal_keeps_proof_and_rights_stay_available(self):
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: self.active}):
            granted = self.harness.consent.grant(
                PRIMARY.consent_context(), PURPOSE, VERSION,
                enforce_notice_state=True,
                special_categories_consent=True,
                special_categories=["health"],
                external_text_version=V3,
                external_text_sha256=V3_SHA256)
            self.assertTrue(granted["specialCategoriesConsent"])
            self.assertIsNone(self._handler_gate())
            app_id = self.harness.create(synthetic_create(1))["applicationId"]

            withdrawn = self.harness.withdraw()
            self.assertEqual(STATUS_WITHDRAWN, withdrawn["status"])
            self.assertTrue(withdrawn["specialCategoriesConsent"])
            self.assertEqual(["health"], withdrawn["specialCategories"])
            self.assertEqual(V3_SHA256, withdrawn["externalTextSha256"])

            denied = self._handler_gate()
            self.assertEqual(403, denied["statusCode"])
            with self.assertRaises(ConsentGateDenied):
                self.harness.create(synthetic_create(2))

            current = self.harness.get(app_id)
            self.assertEqual(app_id, current["applicationId"])
            self.assertEqual(
                app_id,
                self.harness.export(app_id)["application"]["applicationId"])
            self.harness.delete(app_id, current["version"])
            with self.assertRaises(Exception):
                self.harness.get(app_id)

            events = self.harness.history()
            self.assertEqual(["WITHDRAWN", "GRANTED"],
                             [e["event"] for e in events])
            for event in events:
                self.assertEqual(V3, event["externalTextVersion"])
                self.assertEqual(V3_SHA256, event["externalTextSha256"])
                self.assertTrue(event["specialCategoriesConsent"])


if __name__ == "__main__":
    unittest.main()
