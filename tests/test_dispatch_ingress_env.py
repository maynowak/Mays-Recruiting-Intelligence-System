"""Dispatch ingress must not run without an entitlement resolver."""

import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lambda"))

_SPEC = importlib.util.spec_from_file_location(
    "dispatch_ingress_env", os.path.join(ROOT, "lambda", "dispatch_ingress.py"))
dispatch_ingress = importlib.util.module_from_spec(_SPEC)
sys.modules["dispatch_ingress_env"] = dispatch_ingress
_SPEC.loader.exec_module(dispatch_ingress)


class TestDispatchIngressAuthorization(unittest.TestCase):
    def test_missing_profile_table_fails_closed(self):
        env = {k: v for k, v in os.environ.items()
               if k != "API_PROFILES_TABLE"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                dispatch_ingress._dependencies()

    def test_missing_entitlements_table_fails_closed(self):
        with patch.dict(os.environ, {"API_PROFILES_TABLE": "profiles"},
                        clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                dispatch_ingress._dependencies()
        self.assertIn("ENTITLEMENTS_TABLE", str(ctx.exception))

    def test_resolver_is_always_configured(self):
        with patch.dict(os.environ, {
                "API_PROFILES_TABLE": "profiles",
                "ENTITLEMENTS_TABLE": "entitlements",
                "WORK_ITEMS_TABLE": "work-items",
                "WORK_QUEUE_URL":
                    "https://sqs.eu-central-1.amazonaws.com/262370457690/"
                    "ris-dev2-dev-work-queue",
        }, clear=True), \
                patch("boto3.resource"), patch("boto3.client"):
            deps = dispatch_ingress._dependencies()
        self.assertIsNotNone(deps.get("profile_store"))
        self.assertIsNotNone(deps.get("table"))
        self.assertEqual(deps.get("work_queue_url"),
                         "https://sqs.eu-central-1.amazonaws.com/262370457690/"
                         "ris-dev2-dev-work-queue")


if __name__ == "__main__":
    unittest.main()
