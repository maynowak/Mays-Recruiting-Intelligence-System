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
        "metadata": {
            "title": "QA Engineer",
            "titleTokens": ["Engineer"],
            "language": "en",
            "workMode": None,
            "jobTypes": [],
            "contractType": None,
            "contractTypeNoData": True,
        },
        "criticalGaps": [],
        "requirements": [
            {"id": "tag_0", "text": "Python", "category": "skill", "importance": "high", "source": "tags"},
            {"id": "criteria_0", "text": "AWS", "category": "skill", "importance": "medium", "source": "criteria"},
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
            "evidence": "Python, AWS, Docker",
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

    def test_missing_metadata_fails(self):
        broken = copy.deepcopy(VALID)
        del broken["analysis"]["metadata"]
        with self.assertRaises(ATSContractError) as ctx:
            validate_analysis_response(broken)
        self.assertIn("metadata", str(ctx.exception))

    def test_missing_requirement_source_fails(self):
        broken = copy.deepcopy(VALID)
        del broken["analysis"]["requirements"][0]["source"]
        with self.assertRaises(ATSContractError):
            validate_analysis_response(broken)

    def test_evidence_must_be_string_or_null(self):
        broken = copy.deepcopy(VALID)
        broken["recommendations"][0]["evidence"] = []
        with self.assertRaises(ATSContractError):
            validate_analysis_response(broken)

    def test_null_evidence_is_allowed(self):
        response = copy.deepcopy(VALID)
        response["recommendations"][0]["evidence"] = None
        self.assertIs(validate_analysis_response(response), response)

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


class FailClosedTest(unittest.TestCase):
    def setUp(self):
        self.agent = ATSAgent()

    def test_validate_work_rejects_missing_required_field(self):
        for field in ("workId", "type", "tenantId", "idempotencyKey"):
            work = work_item()
            del work[field]
            with self.subTest(field=field):
                self.assertFalse(self.agent.validate_work(work))

    def test_validate_work_rejects_unknown_capability(self):
        work = work_item()
        work["capability"] = "ats.delete"
        self.assertFalse(self.agent.validate_work(work))

    def test_validate_work_rejects_missing_job(self):
        work = work_item()
        work["payload"] = {}
        self.assertFalse(self.agent.validate_work(work))

    def test_process_work_rejects_unknown_capability(self):
        work = work_item()
        work["capability"] = "ats.delete"
        out = self.agent.process_work(work)
        self.assertFalse(out["success"])
        self.assertEqual(out["error"]["type"], "UnsupportedCapability")

    def test_profile_and_description_never_reach_the_log(self):
        sentinel = "RAW-CV-SENTINEL-DO-NOT-LOG"
        work = work_item()
        work["payload"] = {
            "job": {"title": "QA Engineer", "descriptionPlain": sentinel},
            "profile": {"skills": sentinel},
        }
        original = ATSHttpClient.analyze
        ATSHttpClient.analyze = lambda self, job, profile=None: copy.deepcopy(VALID)
        try:
            with self.assertLogs("agents.ats_agent.agent", level="DEBUG") as captured:
                out = self.agent.process_work(work)
        finally:
            ATSHttpClient.analyze = original
        self.assertTrue(out["success"])
        joined = "\n".join(captured.output)
        self.assertNotIn(sentinel, joined)
        self.assertNotIn("descriptionPlain", joined)


class TransactionClientTest(unittest.TestCase):
    """The fence transaction must not run through the resource marshaller."""

    def test_resource_client_is_replaced_by_a_plain_client(self):
        import boto3
        from agents.runtime.pipeline import _ddb_transaction_client

        table = boto3.resource("dynamodb", region_name="eu-central-1").Table(
            "ris-dev2-dev-work-items")
        client = _ddb_transaction_client(table)
        self.assertIsNot(client, table.meta.client)
        self.assertEqual(client.meta.service_model.service_name, "dynamodb")

    def test_parameters_are_not_double_marshalled(self):
        import boto3
        from agents.runtime.pipeline import _ddb_transaction_client

        table = boto3.resource("dynamodb", region_name="eu-central-1").Table("probe")

        class Stop(Exception):
            pass

        def capture(client):
            captured = {}

            def before_call(model, params, **kwargs):
                captured.update(params)
                raise Stop()

            client.meta.events.register("before-call.dynamodb.GetItem", before_call)
            try:
                with self.assertRaises(Stop):
                    client.get_item(
                        TableName="probe", Key={"workId": {"S": "probe-key"}})
            finally:
                client.meta.events.unregister(
                    "before-call.dynamodb.GetItem", before_call)
            return captured["body"]

        plain_body = capture(_ddb_transaction_client(table))
        resource_body = capture(table.meta.client)
        self.assertIn(b'"S": "probe-key"', plain_body)
        self.assertNotIn(b'"M"', plain_body)
        self.assertIn(b'"M"', resource_body)  # the resource client double-wraps

    def test_injected_fake_client_is_preserved(self):
        from agents.runtime.pipeline import _ddb_transaction_client

        class FakeClient:
            pass

        class FakeMeta:
            client = FakeClient()

        class FakeTable:
            meta = FakeMeta()

        table = FakeTable()
        self.assertIs(_ddb_transaction_client(table), table.meta.client)


class ConditionalFailureTest(unittest.TestCase):
    def test_transaction_conditional_failure_is_recognised(self):
        from botocore.exceptions import ClientError
        from agents.runtime.pipeline import _is_conditional_failed

        def error(code, reasons=None):
            response = {"Error": {"Code": code}}
            if reasons is not None:
                response["CancellationReasons"] = reasons
            return ClientError(response, "op")

        self.assertTrue(_is_conditional_failed(
            error("TransactionCanceledException",
                  [{"Code": "ConditionalCheckFailed"}, {"Code": "None"}])))
        self.assertFalse(_is_conditional_failed(
            error("TransactionCanceledException",
                  [{"Code": "ValidationError"}, {"Code": "None"}])))
        self.assertTrue(_is_conditional_failed(
            error("ConditionalCheckFailedException")))
        self.assertFalse(_is_conditional_failed(error("AccessDeniedException")))


if __name__ == "__main__":
    unittest.main()
