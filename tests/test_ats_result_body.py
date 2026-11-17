"""ORCH-04: versioned ATSAnalysisResultBody V1.

Fixtures are synthetic API responses that satisfy the pinned Jobsearch
contract. The body builder must project them without leaking upstream
internals or profile input.
"""

import copy
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ats_agent.agent import ATSAgent, ATSHttpClient
from agents.ats_agent.contract import (
    SOURCE_CONTRACT_COMMIT,
    validate_analysis_response,
)
from agents.ats_agent.result_body import (
    RESULT_BODY_TYPE,
    RESULT_BODY_VERSION,
    build_ats_analysis_result_body,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ats_result_body"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ResultBodyProjectionTest(unittest.TestCase):
    def test_score_zero_empty(self):
        body = build_ats_analysis_result_body(load("score-0-empty.json"))
        self.assertEqual(body["bodyType"], RESULT_BODY_TYPE)
        self.assertEqual(body["bodyVersion"], RESULT_BODY_VERSION)
        self.assertEqual(body["analysis"]["score"], 0)
        self.assertEqual(body["analysis"]["keywordCoverage"]["overall"], 0)
        self.assertEqual(body["analysis"]["analysisStatus"], "insufficient")
        self.assertEqual(body["analysis"]["requirements"], [])
        self.assertEqual(body["analysis"]["matches"], [])
        self.assertEqual(body["recommendations"], [])

    def test_score_fifty_partial(self):
        body = build_ats_analysis_result_body(load("score-50-partial.json"))
        self.assertEqual(body["analysis"]["score"], 50)
        self.assertEqual(body["analysis"]["keywordCoverage"]["overall"], 50)
        self.assertEqual(
            [match["status"] for match in body["analysis"]["matches"]],
            ["MATCHED", "UNKNOWN"],
        )
        self.assertEqual(body["recommendations"][0]["changeType"], "add_skill")

    def test_score_hundred_matched(self):
        body = build_ats_analysis_result_body(load("score-100-matched.json"))
        self.assertEqual(body["analysis"]["score"], 100)
        self.assertEqual(body["analysis"]["keywordCoverage"]["overall"], 100)
        self.assertEqual(body["analysis"]["matches"][0]["status"], "MATCHED")

    def test_duplicates_are_preserved(self):
        body = build_ats_analysis_result_body(load("duplicates.json"))
        self.assertEqual(len(body["analysis"]["requirements"]), 2)
        self.assertEqual(len(body["analysis"]["matches"]), 2)
        self.assertEqual(
            body["analysis"]["requirements"][0]["id"],
            body["analysis"]["requirements"][1]["id"],
        )

    def test_optional_fields_are_omitted_without_error(self):
        body = build_ats_analysis_result_body(load("optional-missing.json"))
        self.assertEqual(
            set(body["ai"]),
            {"requested", "executed", "consentRequired", "consentGiven"},
        )
        self.assertIsNone(body["analysis"]["roleMatch"])
        self.assertEqual(body["analysis"]["analysisStatus"], "limited")


class ResultBodyShapeTest(unittest.TestCase):
    def setUp(self):
        self.body = build_ats_analysis_result_body(
            load("score-50-partial.json"), job_title="QA Engineer"
        )

    def test_upstream_internals_are_not_leaked(self):
        requirement = self.body["analysis"]["requirements"][0]
        self.assertEqual(
            set(requirement),
            {"id", "text", "category", "importance", "source"},
        )
        match = self.body["analysis"]["matches"][0]
        self.assertEqual(set(match), {"requirementId", "status", "confidence"})
        recommendation = self.body["recommendations"][0]
        self.assertEqual(
            set(recommendation),
            {
                "requirementId",
                "changeType",
                "priority",
                "proposedChange",
                "rationale",
                "evidence",
            },
        )

    def test_job_metadata_is_projected(self):
        self.assertEqual(
            set(self.body["analysis"]["metadata"]),
            {
                "title",
                    "language",
                "workMode",
                "jobTypes",
                "contractType",
                "contractTypeNoData",
            },
        )

    def test_source_metadata_is_minimal_and_pinned(self):
        source = self.body["source"]
        self.assertEqual(source["system"], "mays-jobsearch")
        self.assertEqual(source["contract"], "MAYS-JOBSEARCH-ATS-ANALYSIS-V1")
        self.assertEqual(source["contractVersion"], "1.2")
        self.assertEqual(source["contractCommit"], SOURCE_CONTRACT_COMMIT)

    def test_no_profile_input_in_body(self):
        self.assertNotIn("candidateSkills", self.body)
        self.assertNotIn("profile", self.body)
        self.assertEqual(self.body["jobTitle"], "QA Engineer")

    def test_body_version_is_stable(self):
        self.assertEqual(RESULT_BODY_VERSION, "2.0")
        self.assertEqual(self.body["bodyVersion"], "2.0")


class ResultBodyIntegrationTest(unittest.TestCase):
    def test_agent_emits_versioned_body_and_metrics(self):
        response = load("score-100-matched.json")
        original = ATSHttpClient.analyze
        ATSHttpClient.analyze = lambda self, job, profile=None: copy.deepcopy(response)
        try:
            out = ATSAgent().process_work(
                {
                    "workId": "ats-body-1",
                    "type": "ats_process",
                    "tenantId": "tenant-body",
                    "idempotencyKey": "key-body-1",
                    "agentId": "ats-agent",
                    "capability": "analyze.job",
                    "payload": {"job": {"title": "QA Engineer"}, "profile": {}},
                }
            )
        finally:
            ATSHttpClient.analyze = original

        self.assertTrue(out["success"])
        self.assertEqual(out["data"]["bodyType"], RESULT_BODY_TYPE)
        self.assertEqual(out["data"]["bodyVersion"], RESULT_BODY_VERSION)
        self.assertEqual(out["metrics"]["resultBodyVersion"], RESULT_BODY_VERSION)
        self.assertEqual(out["metrics"]["contractVersion"], "1.2")
        self.assertNotIn("candidateSkills", out["data"])

    def test_source_commit_matches_the_manifest(self):
        manifest = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "docs/contracts/mays-jobsearch-api.manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["source"]["commit"], SOURCE_CONTRACT_COMMIT)

    def test_all_fixtures_pass_the_contract_validator(self):
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(fixture=path.name):
                validate_analysis_response(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
