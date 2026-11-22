"""Parser runtime modes: CLI vs internal Lambda.

The dedicated Node runtime is reached through an internal Lambda invocation with
the exact same envelope as the CLI. No public HTTP endpoint, no shared IAM or
transport policy. These tests use a fake Lambda client and never touch AWS.
"""

import io
import json
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.analysis.orchestrator import NodeParser  # noqa: E402
from agents.parsers.lambda_adapter import parse_via_lambda  # noqa: E402
from agents.parsers.node_adapter import (  # noqa: E402
    MAX_PAYLOAD_CHARS,
    ParserInputError,
    ParserUnavailable,
)

FUNCTION = "ris-dev2-dev-analysis-parser"


def envelope(capability="parse.job", data=None):
    return {
        "schemaVersion": "1.0",
        "capability": capability,
        "parserVersion": "1.0.0",
        "data": data if data is not None else {"stableId": "a" * 64},
        "confidence": {"overall": "confirmed"},
    }


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
        if self.exc is not None:
            raise self.exc
        if self.raw is not None:
            payload = self.raw
        else:
            body = self.body
            if body is None:
                sent = json.loads(kwargs["Payload"].decode("utf-8"))
                body = envelope(capability=sent.get("capability", "parse.job"))
            payload = json.dumps(body).encode("utf-8")
        response = {"StatusCode": self.status, "Payload": io.BytesIO(payload)}
        if self.function_error:
            response["FunctionError"] = self.function_error
        return response


class LambdaAdapterTest(unittest.TestCase):
    def test_success_uses_internal_invoke_contract(self):
        client = FakeLambda()
        result = parse_via_lambda("parse.job", {"job": {"title": "x"}},
                                  function_name=FUNCTION, client=client)
        self.assertEqual("parse.job", result.capability)
        self.assertEqual("1.0.0", result.parser_version)
        call = client.calls[0]
        self.assertEqual(FUNCTION, call["FunctionName"])
        self.assertEqual("RequestResponse", call["InvocationType"])
        # No public HTTP integration: only the synchronous internal payload.
        self.assertEqual({"FunctionName", "InvocationType", "Payload"}, set(call))
        self.assertNotIn(b"http", call["Payload"].lower())
        sent = json.loads(call["Payload"].decode("utf-8"))
        self.assertEqual({"capability": "parse.job",
                          "input": {"job": {"title": "x"}}}, sent)

    def test_function_name_from_environment(self):
        client = FakeLambda()
        with patch.dict(os.environ, {"RIS_PARSER_FUNCTION": FUNCTION}, clear=False):
            parse_via_lambda("parse.job", {"job": {}}, client=client)
        self.assertEqual(FUNCTION, client.calls[0]["FunctionName"])

    def test_missing_function_fails_closed(self):
        with patch.dict(os.environ, {"RIS_PARSER_FUNCTION": ""}, clear=False):
            with self.assertRaises(ParserUnavailable) as ctx:
                parse_via_lambda("parse.job", {"job": {}}, client=FakeLambda())
        self.assertIn("RIS_PARSER_FUNCTION", str(ctx.exception))

    def test_invalid_input_payload_is_not_a_retryable_failure(self):
        client = FakeLambda(body={
            "schemaVersion": "1.0",
            "error": {"code": "invalid_input", "message": "missing title"},
        })
        with self.assertRaises(ParserInputError):
            parse_via_lambda("parse.job", {"job": {}},
                             function_name=FUNCTION, client=client)

    def test_internal_error_payload_is_retryable(self):
        client = FakeLambda(body={
            "schemaVersion": "1.0",
            "error": {"code": "internal_error", "message": "boom"},
        })
        with self.assertRaises(ParserUnavailable):
            parse_via_lambda("parse.job", {"job": {}},
                             function_name=FUNCTION, client=client)

    def test_function_error_is_unavailable(self):
        client = FakeLambda(function_error="Unhandled")
        with self.assertRaises(ParserUnavailable):
            parse_via_lambda("parse.job", {"job": {}},
                             function_name=FUNCTION, client=client)

    def test_client_exception_is_unavailable(self):
        client = FakeLambda(exc=RuntimeError("throttled"))
        with self.assertRaises(ParserUnavailable):
            parse_via_lambda("parse.job", {"job": {}},
                             function_name=FUNCTION, client=client)

    def test_non_200_status_is_unavailable(self):
        client = FakeLambda(status=202)
        with self.assertRaises(ParserUnavailable):
            parse_via_lambda("parse.job", {"job": {}},
                             function_name=FUNCTION, client=client)

    def test_invalid_json_is_unavailable(self):
        client = FakeLambda(raw=b"not json")
        with self.assertRaises(ParserUnavailable):
            parse_via_lambda("parse.job", {"job": {}},
                             function_name=FUNCTION, client=client)

    def test_wrong_capability_envelope_is_rejected(self):
        client = FakeLambda(body=envelope(capability="parse.cv"))
        with self.assertRaises(ParserUnavailable):
            parse_via_lambda("parse.job", {"job": {}},
                             function_name=FUNCTION, client=client)

    def test_unsupported_capability_and_oversize_payload(self):
        with self.assertRaises(ParserInputError):
            parse_via_lambda("parse.other", {}, function_name=FUNCTION,
                             client=FakeLambda())
        with self.assertRaises(ParserInputError):
            parse_via_lambda("parse.job", {"job": {"text": "x" * MAX_PAYLOAD_CHARS}},
                             function_name=FUNCTION, client=FakeLambda())


    def test_timeout_is_enforced_on_the_real_client(self):
        client = FakeLambda()
        with patch("boto3.client", return_value=client) as factory:
            parse_via_lambda("parse.job", {"job": {}},
                             function_name=FUNCTION, timeout=7)
        config = factory.call_args.kwargs["config"]
        self.assertEqual(7, config.connect_timeout)
        self.assertEqual(7, config.read_timeout)
        self.assertEqual({"max_attempts": 0}, config.retries)


class NodeParserModeTest(unittest.TestCase):
    def test_default_mode_is_cli(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RIS_PARSER_MODE", None)
            parser = NodeParser(runner=lambda capability, payload: envelope(capability))
        self.assertEqual("cli", parser.mode)
        self.assertEqual({"stableId": "a" * 64}, parser.parse_job({"title": "x"}))

    def test_lambda_mode_never_calls_the_node_cli(self):
        calls = []

        def runner(capability, payload):  # pragma: no cover - must not run
            calls.append(capability)
            raise AssertionError("CLI runner used in lambda mode")

        client = FakeLambda()
        parser = NodeParser(mode="lambda", client=client,
                            function_name=FUNCTION, runner=runner)
        data = parser.parse_job({"title": "x"})
        self.assertEqual("a" * 64, data["stableId"])
        self.assertEqual([], calls)
        self.assertEqual(1, len(client.calls))

    def test_mode_from_environment(self):
        with patch.dict(os.environ, {"RIS_PARSER_MODE": "lambda"}, clear=False):
            parser = NodeParser(client=FakeLambda(), function_name=FUNCTION)
        self.assertEqual("lambda", parser.mode)

    def test_unknown_mode_fails_closed(self):
        with self.assertRaises(ParserInputError):
            NodeParser(mode="http")

    def test_cv_job_and_ats_share_the_lambda_transport(self):
        client = FakeLambda()
        parser = NodeParser(mode="lambda", client=client,
                            function_name=FUNCTION)
        parser.parse_cv("JVBERi0=")
        parser.parse_job({"title": "x"})
        parser.parse_ats({"title": "x"}, {"skills": ["Python"]})
        sent = [json.loads(call["Payload"].decode("utf-8"))["capability"]
                for call in client.calls]
        self.assertEqual(["parse.cv", "parse.job", "parse.ats"], sent)
        self.assertEqual(15, parser._timeout)


if __name__ == "__main__":
    unittest.main()
