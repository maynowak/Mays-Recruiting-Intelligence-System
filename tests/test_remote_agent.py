"""RIS-ANALYSIS-ECOSYSTEM-INTEGRATION-13 — remote agent adapter tests."""

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.runtime.remote_agent import (  # noqa: E402
    LambdaAgentHandler,
    RemoteAgentError,
    RemoteAgentInputError,
    build_analysis_executor,
)

FUNCTION = "ris-dev2-dev-analysis"
WORK = {"workId": "w1", "type": "agent_analysis_agent",
        "capability": "analysis.run", "agentId": "analysis-agent"}


class FakeLambda:
    def __init__(self, body=None, status=200, function_error=None,
                 exc=None, raw=None):
        self.body = body
        self.status = status
        self.function_error = function_error
        self.exc = exc
        self.raw = raw
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        if self.raw is not None:
            payload = self.raw
        else:
            payload = json.dumps(self.body or {
                "success": True, "data": {"results": {}}}).encode()
        response = {"StatusCode": self.status,
                    "Payload": io.BytesIO(payload)}
        if self.function_error:
            response["FunctionError"] = self.function_error
        return response


class RemoteAgentHandlerTest(unittest.TestCase):
    def test_execution_only_event_and_result(self):
        client = FakeLambda(body={"success": True, "data": {"x": 1}})
        handler = LambdaAgentHandler(FUNCTION, client=client)
        result = handler.process_work(WORK)
        self.assertEqual({"success": True, "data": {"x": 1}}, result)
        sent = json.loads(client.calls[0]["Payload"].decode())
        self.assertEqual("agent", sent["executionMode"])
        self.assertEqual(WORK, sent["workItem"])
        self.assertEqual(FUNCTION, client.calls[0]["FunctionName"])

    def test_function_error_and_non_200_are_retryable(self):
        for client in (FakeLambda(function_error="Unhandled"),
                       FakeLambda(status=202)):
            with self.assertRaises(RemoteAgentError):
                LambdaAgentHandler(FUNCTION, client=client).process_work(WORK)

    def test_error_body_is_raised_with_code(self):
        client = FakeLambda(body={"error": {"code": "invalid_input",
                                           "message": "bad"}})
        with self.assertRaises(RemoteAgentError) as ctx:
            LambdaAgentHandler(FUNCTION, client=client).process_work(WORK)
        self.assertEqual("invalid_input", ctx.exception.code)

    def test_invalid_json_and_payload_limit(self):
        with self.assertRaises(RemoteAgentError):
            LambdaAgentHandler(FUNCTION, client=FakeLambda(raw=b"nope")
                               ).process_work(WORK)
        with self.assertRaises(RemoteAgentInputError):
            LambdaAgentHandler(FUNCTION, client=FakeLambda(),
                               max_payload_bytes=10).process_work(WORK)

    def test_client_exception_is_retryable(self):
        with self.assertRaises(RemoteAgentError):
            LambdaAgentHandler(
                FUNCTION, client=FakeLambda(exc=RuntimeError("throttled"))
            ).process_work(WORK)

    def test_missing_function_fails_closed(self):
        with self.assertRaises(ValueError):
            LambdaAgentHandler("")

    def test_build_from_environment(self):
        self.assertIsNone(build_analysis_executor({}))
        handler = build_analysis_executor({
            "ANALYSIS_FUNCTION_NAME": FUNCTION,
            "ANALYSIS_REMOTE_TIMEOUT_SECONDS": "45"})
        self.assertIsInstance(handler, LambdaAgentHandler)
        self.assertEqual(FUNCTION, handler.function_name)
        self.assertEqual(45, handler._timeout)


if __name__ == "__main__":
    unittest.main()
