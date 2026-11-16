"""ORCH-03: the ATS agent validates the pinned Jobsearch contract.

No network and no ATS logic: the transport is stubbed and the validator is
exercised directly.
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ats_agent.agent import ATSAPIError, ATSAgent, ATSHttpClient
from agents.ats_agent.contract import (
    ATSContractError,
    CONTRACT_VERSION,
    validate_analysis_response,
)


VALID = {
    "analysis": {
        "score": 50,
        "keywordCoverage": {"overall": 50},
        "requirementCoverage": 50,
        "profileEvidenceCoverage": 50,
        "roleMatch": None,
        "analysisStatus": "limited",
        "basis": {
            "requirementCount": 2,
            "titleRequirementCount": 1,
            "hasDescription": False,
            "roleMatchAvailable": False,
        },
        "criticalGaps": [],
        "requirements": [
            {"id": "tag_0", "text": "Python", "category": "skill", "importance": "high"},
            {"id": "criteria_0", "text": "AWS", "category": "skill", "importance": "medium"},
        ],
        "matches": [
            {"requirementId": "tag_0", "status": "MATCHED", "confidence": "HIGH"},
            {"requirementId": "criteria_0", "status": "PARTIAL", "confidence": "MEDIUM"},
        ],
    },
    "recommendations": [
        {
            "requirementId": "criteria_0",
            "changeType": "add_skill",
            "priority": "medium",
            "proposedChange": "Add evidence",
            "rationale": "Partial match",
            "evidence": [],
        }
    ],
    "ai": {
        "requested": False,
        "executed": False,
        "consentRequired": True,
        "consentGiven": False,
    },
}


def work_item():
    return {
        "workId": "ats-contract-1",
        "type": "ats_process",
        "tenantId": "tenant-contract",
        "idempotencyKey": "key-contract-1",
        "agentId": "ats-agent",
        "capability": "analyze.job",
        "payload": {"job": {"title": "QA Engineer"}, "profile": {}},
    }


class ContractValidationTest(unittest.TestCase):
    def test_valid_response_is_returned_unchanged(self):
        self.assertIs(validate_analysis_response(VALID), VALID)

    def test_missing_required_field_fails(self):
        broken = copy.deepcopy(VALID)
        del broken["analysis"]["keywordCoverage"]
        with self.assertRaises(ATSContractError) as ctx:
            validate_analysis_response(broken)
        self.assertIn("keywordCoverage", str(ctx.exception))

    def test_score_out_of_range_fails(self):
        broken = copy.deepcopy(VALID)
        broken["analysis"]["score"] = 101
        with self.assertRaises(ATSContractError):
            validate_analysis_response(broken)

    def test_score_must_be_integer(self):
        broken = copy.deepcopy(VALID)
        broken["analysis"]["score"] = 50.0
        with self.assertRaises(ATSContractError):
            validate_analysis_response(broken)

    def test_unknown_match_status_fails(self):
        broken = copy.deepcopy(VALID)
        broken["analysis"]["matches"][0]["status"] = "GAP"
        with self.assertRaises(ATSContractError):
            validate_analysis_response(broken)

    def test_unknown_analysis_status_fails(self):
        broken = copy.deepcopy(VALID)
        broken["analysis"]["analysisStatus"] = "unknown"
        with self.assertRaises(ATSContractError):
            validate_analysis_response(broken)

    def test_role_match_null_is_allowed(self):
        response = copy.deepcopy(VALID)
        response["analysis"]["roleMatch"] = None
        self.assertIs(validate_analysis_response(response), response)

    def test_additional_fields_are_allowed(self):
        response = copy.deepcopy(VALID)
        response["analysis"]["futureField"] = "ok"
        response["futureTopLevel"] = True
        self.assertIs(validate_analysis_response(response), response)


class AgentContractIntegrationTest(unittest.TestCase):
    def _run_with(self, analyze):
        original = ATSHttpClient.analyze
        ATSHttpClient.analyze = analyze
        try:
            return ATSAgent().process_work(work_item())
        finally:
            ATSHttpClient.analyze = original

    def test_success_carries_contract_version(self):
        out = self._run_with(lambda self, job, profile=None: copy.deepcopy(VALID))
        self.assertTrue(out["success"])
        self.assertEqual(out["metrics"]["contractVersion"], CONTRACT_VERSION)

    def test_schema_mismatch_is_controlled(self):
        broken = copy.deepcopy(VALID)
        del broken["analysis"]["matches"]

        def analyze(self, job, profile=None):
            return broken

        out = self._run_with(analyze)
        self.assertFalse(out["success"])
        self.assertEqual(out["error"]["type"], "ATSContractError")
        self.assertEqual(out["error"]["code"], "ATS_CONTRACT_MISMATCH")

    def test_timeout_is_controlled(self):
        def analyze(self, job, profile=None):
            raise ATSAPIError("timeout", "ATS_TIMEOUT")

        out = self._run_with(analyze)
        self.assertFalse(out["success"])
        self.assertEqual(out["error"]["type"], "ATSAPIError")
        self.assertEqual(out["error"]["code"], "ATS_TIMEOUT")

    def test_http_error_keeps_status_code(self):
        error = ATSAPIError("HTTP 503", "ATS_UPSTREAM_ERROR", 503)
        self.assertEqual(error.status, 503)
        self.assertEqual(error.code, "ATS_UPSTREAM_ERROR")


if __name__ == "__main__":
    unittest.main()
