"""Consent purpose/status parity across code, OpenAPI and the contract doc.

The registry in ``jobsearch/consent_contract.py`` is authoritative. This test
pins the documented surface to it:

* each purpose has exactly the declared notice versions and lifecycle state;
* approved purposes carry a non-empty ``legalApprovalRef``, the draft does not;
* OpenAPI's purpose enum and returned status codes match the handler contract;
* ``docs/contracts/CONSENT-V1.md`` names every purpose and the 404 semantics.

No AWS, no deployment.
"""

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

from jobsearch.consent_contract import (  # noqa: E402
    APPROVED_NOTICE_STATES,
    CONSENT_PURPOSES,
    EXTERNAL_NOTICE_REFS,
    GRANTABLE_NOTICE_STATES,
    NOTICE_ACTIVE,
    NOTICE_APPROVED,
    NOTICE_DRAFT,
    NOTICE_REGISTRY,
)

SPEC = ROOT / "docs" / "api" / "openapi-platform.yaml"
CONTRACT_DOC = ROOT / "docs" / "contracts" / "CONSENT-V1.md"

EXPECTED = {
    "application-storage": (NOTICE_APPROVED, True),
    "cv-storage": (NOTICE_APPROVED, True),
    "search-profile-storage": (NOTICE_APPROVED, True),
    "analysis-processing": (NOTICE_DRAFT, False),
}


class TestRegistryParity(unittest.TestCase):
    def test_registry_keys_match_the_purpose_map(self):
        self.assertEqual(set(CONSENT_PURPOSES), set(NOTICE_REGISTRY))
        self.assertEqual(set(EXPECTED), set(CONSENT_PURPOSES))

    def test_each_purpose_declares_exactly_the_documented_versions(self):
        for purpose, versions in CONSENT_PURPOSES.items():
            with self.subTest(purpose=purpose):
                self.assertEqual({"1.0"}, set(versions))
                self.assertEqual(set(versions),
                                 set(NOTICE_REGISTRY[purpose]))

    def test_lifecycle_state_and_legal_reference(self):
        for purpose, (state, approved) in EXPECTED.items():
            notice = NOTICE_REGISTRY[purpose]["1.0"]
            with self.subTest(purpose=purpose):
                self.assertEqual(state, notice.state)
                self.assertEqual(approved, notice.approved)
                self.assertEqual(
                    notice.state in GRANTABLE_NOTICE_STATES, notice.grantable)
                if approved:
                    self.assertIn(notice.state, APPROVED_NOTICE_STATES)
                    self.assertTrue(notice.legal_approval_ref)
                else:
                    self.assertFalse(notice.legal_approval_ref)
                    self.assertFalse(notice.grantable)

    def test_analysis_processing_is_the_only_draft(self):
        drafts = [p for p, versions in NOTICE_REGISTRY.items()
                  for v in versions.values() if v.state == NOTICE_DRAFT]
        self.assertEqual(["analysis-processing"], drafts)
        self.assertNotIn("analysis-processing", EXTERNAL_NOTICE_REFS)

    def test_approved_external_refs_map_only_to_declared_versions(self):
        for purpose, refs in EXTERNAL_NOTICE_REFS.items():
            self.assertIn(purpose, CONSENT_PURPOSES)
            for ref, meta in refs.items():
                with self.subTest(purpose=purpose, ref=ref):
                    if meta.get("noticeVersion") is not None:
                        self.assertIn(meta["noticeVersion"],
                                      CONSENT_PURPOSES[purpose])
                        self.assertEqual("APPROVED", meta["noticeState"])
                    else:
                        self.assertIn(meta["noticeState"],
                                      {"DRAFT", "SUPERSEDED"})


class TestOpenApiParity(unittest.TestCase):
    def setUp(self):
        self.spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
        self.paths = self.spec["paths"]

    def _purpose_enum(self, path, method, location):
        operation = self.paths[path][method]
        parameter = next(
            item for item in operation["parameters"]
            if item.get("name") == "purpose" and item.get("in") == location)
        schema = parameter["schema"]
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            return self.spec["components"]["schemas"][name]["enum"]
        return schema["enum"]

    def test_purpose_enum_matches_the_registry(self):
        self.assertEqual(
            set(CONSENT_PURPOSES),
            set(self._purpose_enum("/v1/partner/me/consents", "get", "query")))
        self.assertEqual(
            set(CONSENT_PURPOSES),
            set(self._purpose_enum(
                "/v1/partner/me/consents/history", "get", "query")))

    def test_schema_enum_matches_the_registry(self):
        schema = self.spec["components"]["schemas"]["ConsentPurpose"]
        self.assertEqual(set(CONSENT_PURPOSES), set(schema["enum"]))

    def test_unknown_purpose_is_404_not_422(self):
        for path, method in (
                ("/v1/partner/me/consents", "get"),
                ("/v1/partner/me/consents", "post"),
                ("/v1/partner/me/consents/withdraw", "post"),
                ("/v1/partner/me/consents/history", "get")):
            with self.subTest(path=path, method=method):
                responses = self.paths[path][method]["responses"]
                self.assertIn("404", responses)
                self.assertIn("UNKNOWN_PURPOSE",
                              str(responses["404"]).upper())

    def test_grant_documents_the_stored_proof(self):
        schema = self.paths["/v1/partner/me/consents"]["post"][
            "requestBody"]["content"]["application/json"]["schema"]
        for field in ("specialCategoriesConsent", "specialCategories",
                      "externalTextVersion", "externalTextSha256"):
            self.assertIn(field, schema["properties"])
        categories = self.spec["components"]["schemas"][
            "ConsentSpecialCategory"]["enum"]
        self.assertEqual(9, len(categories))


class TestContractDocumentParity(unittest.TestCase):
    def setUp(self):
        self.text = CONTRACT_DOC.read_text(encoding="utf-8")

    def test_every_purpose_and_state_is_documented(self):
        for purpose in CONSENT_PURPOSES:
            self.assertIn("`%s`" % purpose, self.text)
        for state in ("DRAFT", "APPROVED", "ACTIVE", "SUPERSEDED"):
            self.assertIn(state, self.text)

    def test_unknown_purpose_and_pilot_codes_are_documented(self):
        for token in ("404", "UNKNOWN_PURPOSE",
                      "CV_STORAGE_PILOT_NOT_ALLOWED",
                      "SEARCH_PROFILE_STORAGE_PILOT_NOT_ALLOWED",
                      "CONSENT_NOTICE_STATE_ENFORCED",
                      "CONSENT_PILOT_ALLOWLIST"):
            self.assertIn(token, self.text)

    def test_cv_storage_art9_enforcement_is_documented(self):
        self.assertIn("Art. 9", self.text)
        self.assertIn("cv-storage", self.text)
        self.assertIn("SPECIAL_CATEGORIES_REQUIRED", self.text)
        self.assertIn("cv-storage-consent-2026-11-08-v1", self.text)
        # The technical control is documented; Privacy/Legal confirmation
        # remains a release gate, not an open implementation gap.
        self.assertIn("Privacy/Legal", self.text)


if __name__ == "__main__":
    unittest.main()
