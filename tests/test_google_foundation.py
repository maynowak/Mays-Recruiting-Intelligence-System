"""Tests Gate 13A: Google-Foundation Guards (Gate 13A).

Kein Netz/AWS: statische Guards (keine Secrets im Code, kein Auto-Linking,
keine Token-Felder im Profil) + Profil-Boundary (Gate 12 intakt).
"""

import importlib.util
import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "gw_handler_13a", os.path.join(REPO_ROOT, "lambda", "handler.py"))
handler = importlib.util.module_from_spec(_SPEC)
sys.modules["gw_handler_13a"] = handler
_SPEC.loader.exec_module(handler)


def read(rel):
    with open(os.path.join(REPO_ROOT, rel)) as fh:
        return fh.read()


class FakeTable:
    class ConditionalFailed(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "ConditionalCheckFailedException"}}

    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        if ConditionExpression == "attribute_not_exists(userId)" \
                and Item["userId"] in self.items:
            raise FakeTable.ConditionalFailed()
        self.items[Item["userId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["userId"])
        return {"Item": dict(item)} if item else {}


def ctx():
    return {"userId": "user-g13", "tenantId": "tenant-g13",
            "username": "g13", "email": "g13@example.com", "groups": []}


class TestGoogleFoundationGuards(unittest.TestCase):
    def test_no_secret_literals_in_terraform(self):
        """Client-Secret nur als Variable, nie als Wert (kein Dummy-Deploy)."""
        for rel in ("terraform/modules/cognito/main.tf",
                    "terraform/modules/cognito/variables.tf",
                    "terraform/variables.tf", "terraform/main.tf"):
            text = read(rel)
            self.assertNotRegex(text, r'client_secret\s*=\s*"[^"]+"',
                                f"Secret-Literal in {rel}")
            self.assertNotIn("AKIA", text)
        main = read("terraform/modules/cognito/main.tf")
        self.assertIn("var.google_client_secret", main)
        self.assertIn('sensitive   = true', read("terraform/modules/cognito/variables.tf"))

    def test_no_automatic_account_linking_code(self):
        """Nirgendwo Auto-Linking (auch nicht per E-Mail)."""
        hits = []
        for root, _, files in os.walk(REPO_ROOT):
            if any(skip in root for skip in (".git", "__pycache__", "installer/projects",
                                             "node_modules", ".terraform")):
                continue
            for fn in files:
                if not fn.endswith(".py") or fn == "test_google_foundation.py":
                    continue
                text = open(os.path.join(root, fn), errors="ignore").read()
                for pat in ("AdminLinkProviderForUser", "admin_link_provider",
                            "auto_link", "autolink", "merge_provider"):
                    if re.search(pat, text, re.IGNORECASE):
                        hits.append(f"{fn}:{pat}")
        self.assertEqual(hits, [], f"Auto-Linking-Spuren: {hits}")

    def test_no_token_fields_in_profile(self):
        """Profil kennt keine Token-Felder (Gate-12-Modell intakt)."""
        table = FakeTable()
        resp = handler._provision_user_profile(table, ctx(), {"nickname": "G"})
        body = json.loads(resp["body"])
        forbidden = {"access_token", "refresh_token", "id_token", "token",
                     "google_sub", "google_access", "client_secret"}
        self.assertTrue(forbidden.isdisjoint(set(body.keys())),
                        f"Token-Felder im Profil: {forbidden & set(body.keys())}")

    def test_google_user_without_profile_stays_without(self):
        """Identity != Application Profile (Gate-12-Prinzip, kein Auto-Provision)."""
        table = FakeTable()
        got = table.get_item(Key={"userId": "user-g13"})
        self.assertNotIn("Item", got)


if __name__ == "__main__":
    unittest.main()
