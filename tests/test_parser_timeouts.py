"""RIS-ANALYSIS-AGENT-RUNTIME-11 STEP C — timeout and error boundaries."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.parsers.lambda_adapter import parse_via_lambda  # noqa: E402
from agents.parsers.node_adapter import (  # noqa: E402
    ParserUnavailable,
    parse_via_node,
)

NODE = os.environ.get("RIS_PARSER_NODE") or shutil.which("node")


class NodeCliTimeoutTest(unittest.TestCase):
    @unittest.skipUnless(NODE, "node runtime not available")
    def test_cli_timeout_is_a_controlled_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli = Path(tmp) / "sleeper.mjs"
            cli.write_text(
                "import { setTimeout as sleep } from 'node:timers/promises';\n"
                "await sleep(5000);\n"
                "process.stdout.write('{}');\n", encoding="utf-8")
            with self.assertRaises(ParserUnavailable) as ctx:
                parse_via_node("parse.job", {"job": {"title": "x"}},
                               cli=str(cli), node=NODE, timeout=1)
        self.assertIn("timed out", str(ctx.exception))


class LambdaTimeoutMappingTest(unittest.TestCase):
    class Client:
        def invoke(self, **kwargs):
            from botocore.exceptions import ReadTimeoutError

            raise ReadTimeoutError(endpoint_url="https://lambda.invalid")

    def test_sdk_read_timeout_is_unavailable(self):
        with self.assertRaises(ParserUnavailable) as ctx:
            parse_via_lambda("parse.job", {"job": {"title": "x"}},
                             function_name="canary",
                             client=self.Client(), timeout=1)
        self.assertIn("ReadTimeoutError", str(ctx.exception))

    def test_client_timeout_configuration(self):
        class Ok:
            def invoke(self, **kwargs):
                return {"StatusCode": 200, "Payload": io.BytesIO(
                    json.dumps({"schemaVersion": "1.0",
                                "capability": "parse.job",
                                "parserVersion": "1.0.0",
                                "data": {}, "confidence": {}}).encode())}

        with patch("boto3.client", return_value=Ok()) as factory:
            parse_via_lambda("parse.job", {"job": {"title": "x"}},
                             function_name="canary", timeout=15)
        config = factory.call_args.kwargs["config"]
        self.assertEqual(15, config.connect_timeout)
        self.assertEqual(15, config.read_timeout)
        self.assertEqual({"max_attempts": 0}, config.retries)


class TimeoutBudgetTest(unittest.TestCase):
    def test_parser_budget_fits_the_analysis_lambda(self):
        from agents.parsers import lambda_adapter

        module = (ROOT / "terraform" / "modules" / "analysis_runtime"
                  / "variables.tf").read_text(encoding="utf-8")
        self.assertIn("default     = 60", module)
        self.assertIn("var.analysis_timeout_seconds >= 15", module)
        self.assertLessEqual(lambda_adapter.DEFAULT_TIMEOUT_SECONDS, 15)

    def test_payload_limits_stay_below_the_contract(self):
        from agents.analysis.contracts import MAX_INLINE_JOB_CHARS
        from agents.parsers import node_adapter

        # The parser transport is wider than the inline job contract.
        self.assertGreater(node_adapter.MAX_PAYLOAD_CHARS, MAX_INLINE_JOB_CHARS)
        self.assertEqual(100_000, node_adapter.MAX_PAYLOAD_CHARS)


if __name__ == "__main__":
    unittest.main()
