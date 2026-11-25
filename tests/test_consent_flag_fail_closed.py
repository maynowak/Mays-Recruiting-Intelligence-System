"""Consent enforcement switches must fail closed.

``lambda/handler.py`` and ``jobsearch/consent_contract.py`` read four
deployment switches. The historical parser treated *any* value other than
``"true"`` as ``false``. That is a silent weakening: a typo such as ``"ture"``,
an empty value injected by a broken deployment or a YAML-style ``"yes"``
disabled a legal gate.

Contract pinned here:

* unset            -> the documented, backwards-compatible default (``false``)
* ``"true"``/``"false"`` (case-insensitive, trimmed) -> that value
* anything else    -> **enforced** (fail closed) and logged

No AWS, no Terraform, no deployment.
"""

import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "lambda")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import handler  # noqa: E402
from jobsearch import consent_contract  # noqa: E402
from jobsearch.application_contract import ApplicationContext  # noqa: E402

INVALID_VALUES = ("", "   ", "1", "0", "yes", "no", "on", "off", "ture",
                  "enabled", "disabled", "TRUE1")

CTX = ApplicationContext("u1", "t1", "p1", "https://issuer.example")
CV_CTX = {
    "userId": "u1",
    "tenantId": "t1",
    "partnerApplicationId": "p1",
    "issuer": "https://issuer.example",
}


class _Repo:
    def __init__(self, allowed=False):
        self.allowed = allowed

    def has_consent(self, ctx, purpose):
        return self.allowed


def _clear(monkeypatch):
    for name in consent_contract.ENFORCEMENT_FLAG_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("CONSENT_PILOT_ALLOWLIST", raising=False)


class EnforcementFlagParserTests(unittest.TestCase):
    def test_unset_keeps_the_documented_default(self):
        with patch.dict(os.environ, {}, clear=False):
            for name in consent_contract.ENFORCEMENT_FLAG_NAMES:
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop(name, None)
                    self.assertFalse(
                        consent_contract.enforcement_flag(name),
                        "%s must default to off" % name)

    def test_explicit_booleans_are_parsed_case_insensitively(self):
        for raw, expected in (("true", True), ("TRUE", True), (" true ", True),
                              ("false", False), ("FALSE", False),
                              (" false ", False)):
            with patch.dict(os.environ, {"X_FLAG": raw}):
                self.assertIs(expected,
                              consent_contract.enforcement_flag("X_FLAG"))

    def test_invalid_values_enforce_and_log(self):
        for raw in INVALID_VALUES:
            with self.subTest(raw=raw), \
                    patch.dict(os.environ, {"X_FLAG": raw}), \
                    self.assertLogs(consent_contract.logger, logging.ERROR):
                self.assertTrue(consent_contract.enforcement_flag("X_FLAG"))

    def test_flag_name_registry_matches_the_runtime_reads(self):
        handler_source = (ROOT / "lambda" / "handler.py").read_text(
            encoding="utf-8")
        contract_source = (ROOT / "jobsearch" / "consent_contract.py").read_text(
            encoding="utf-8")
        for name in consent_contract.ENFORCEMENT_FLAG_NAMES:
            self.assertIn(name, handler_source + contract_source)


class HandlerGateFailClosedTests(unittest.TestCase):
    def test_application_gate_unset_is_inactive(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APPLICATION_CONSENT_ENFORCED", None)
            os.environ.pop("CONSENT_PILOT_ALLOWLIST", None)
            with patch.object(handler, "_consent_repo", lambda: _Repo(False)):
                self.assertIsNone(handler._application_consent_error(CTX))

    def test_application_gate_invalid_value_denies_the_write(self):
        for raw in INVALID_VALUES:
            with self.subTest(raw=raw), \
                    patch.dict(os.environ,
                               {"APPLICATION_CONSENT_ENFORCED": raw,
                                "CONSENT_PILOT_ALLOWLIST": ""}), \
                    patch.object(handler, "_consent_repo", lambda: _Repo(False)):
                response = handler._application_consent_error(CTX)
                self.assertIsNotNone(response)
                self.assertEqual(403, response["statusCode"])
                self.assertIn("CONSENT_REQUIRED", response["body"])

    def test_cv_gate_invalid_value_denies_the_write(self):
        for raw in INVALID_VALUES:
            with self.subTest(raw=raw), \
                    patch.dict(os.environ,
                               {"CV_STORAGE_CONSENT_ENFORCED": raw,
                                "CONSENT_PILOT_ALLOWLIST": ""}), \
                    patch.object(handler, "_consent_repo", lambda: _Repo(False)):
                response = handler._cv_storage_consent_error(CV_CTX)
                self.assertIsNotNone(response)
                self.assertEqual(403, response["statusCode"])
                self.assertIn("CV_STORAGE_CONSENT_REQUIRED", response["body"])

    def test_search_profile_gate_invalid_value_denies_the_write(self):
        for raw in INVALID_VALUES:
            with self.subTest(raw=raw), \
                    patch.dict(os.environ,
                               {"SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED": raw,
                                "CONSENT_PILOT_ALLOWLIST": ""}), \
                    patch.object(handler, "_consent_repo", lambda: _Repo(False)):
                response = handler._search_profile_storage_consent_error(
                    CV_CTX)
                self.assertIsNotNone(response)
                self.assertEqual(403, response["statusCode"])
                self.assertIn("SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED",
                              response["body"])

    def test_cv_and_search_gates_allow_with_consent(self):
        with patch.dict(os.environ, {
            "CV_STORAGE_CONSENT_ENFORCED": "true",
            "SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED": "true",
            "CONSENT_PILOT_ALLOWLIST": "",
        }), patch.object(handler, "_consent_repo", lambda: _Repo(True)):
            self.assertIsNone(handler._cv_storage_consent_error(CV_CTX))
            self.assertIsNone(
                handler._search_profile_storage_consent_error(CV_CTX))


class NoticeStateFailClosedTests(unittest.TestCase):
    def test_unset_notice_state_is_not_enforced(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONSENT_NOTICE_STATE_ENFORCED", None)
            self.assertFalse(consent_contract.notice_state_enforced())

    def test_invalid_notice_state_rejects_a_draft_grant(self):
        draft = consent_contract.notice_version(
            "analysis-processing", "1.0")
        self.assertEqual(consent_contract.NOTICE_DRAFT, draft.state)
        for raw in INVALID_VALUES:
            with self.subTest(raw=raw), \
                    patch.dict(os.environ,
                               {"CONSENT_NOTICE_STATE_ENFORCED": raw}):
                with self.assertRaises(
                        consent_contract.ConsentContractError) as caught:
                    consent_contract.validate_notice_version(
                        "analysis-processing", "1.0")
                self.assertEqual("NOTICE_NOT_ACTIVE",
                                 caught.exception.code)

    def test_invalid_notice_state_still_allows_an_approved_grant(self):
        with patch.dict(os.environ, {"CONSENT_NOTICE_STATE_ENFORCED": "ture"}):
            self.assertEqual(
                "1.0",
                consent_contract.validate_notice_version(
                    "application-storage", "1.0"))


if __name__ == "__main__":
    unittest.main()
