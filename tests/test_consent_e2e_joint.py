"""Synthetic joint consent + ApplicationV1 end-to-end (local only).

Runs the eight-step scenario from JM-RIS-CONSENT-RECONCILIATION-01 §8 against
the real repositories and the real handler consent gate. No AWS account, JWT,
API Gateway or Jobsearch deployment is involved.
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import boto3
    from moto import mock_aws
except ImportError:  # pragma: no cover
    boto3 = None
    mock_aws = None

from tests.application_e2e_harness import synthetic_create
from tests.consent_e2e_harness import (
    FOREIGN_TENANT, NOTICE_VERSION, PRIMARY, SECONDARY_USER,
    ConsentGateDenied, JointConsentE2EHarness,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class JointConsentE2ETests(unittest.TestCase):
    APPS = "synthetic-consent-e2e-applications"
    CONSENTS = "synthetic-consent-e2e-consents"

    def setUp(self):
        self.env = self._environment()
        self.env.__enter__()
        self.aws = mock_aws()
        self.aws.start()
        self.db = boto3.resource("dynamodb", region_name="eu-central-1")
        self.db.create_table(
            TableName=self.APPS,
            KeySchema=[
                {"AttributeName": "applicationId", "KeyType": "HASH"},
                {"AttributeName": "entityKey", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "applicationId", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"},
                {"AttributeName": "ownerKey", "AttributeType": "S"},
                {"AttributeName": "updatedAt", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "gsi-owner",
                "KeySchema": [
                    {"AttributeName": "ownerKey", "KeyType": "HASH"},
                    {"AttributeName": "updatedAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 1,
                                          "WriteCapacityUnits": 1},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        self.db.create_table(
            TableName=self.CONSENTS,
            KeySchema=[
                {"AttributeName": "scopeKey", "KeyType": "HASH"},
                {"AttributeName": "entityKey", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "scopeKey", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        self.harness = JointConsentE2EHarness(
            self.db, self.APPS, self.CONSENTS, enforced=True)

    @staticmethod
    def _environment():
        class Environment:
            def __enter__(self):
                self.old = {k: os.environ.get(k) for k in (
                    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                    "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION",
                    "AWS_EC2_METADATA_DISABLED", "RIS_CURSOR_SECRET",
                    "APPLICATION_CONSENT_ENFORCED",
                    "CONSENT_NOTICE_STATE_ENFORCED",
                )}
                os.environ.update({
                    "AWS_ACCESS_KEY_ID": "testing",
                    "AWS_SECRET_ACCESS_KEY": "testing",
                    "AWS_SESSION_TOKEN": "testing",
                    "AWS_DEFAULT_REGION": "eu-central-1",
                    "AWS_EC2_METADATA_DISABLED": "true",
                    "RIS_CURSOR_SECRET": "local-only-consent-e2e-cursor-secret",
                    # Gate on; notice text is still a draft, so technical
                    # acceptance of 1.0 stays enabled for the synthetic run.
                    "APPLICATION_CONSENT_ENFORCED": "true",
                    "CONSENT_NOTICE_STATE_ENFORCED": "false",
                })
                return self

            def __exit__(self, *_):
                for key, value in self.old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        return Environment()

    def tearDown(self):
        self.aws.stop()
        self.env.__exit__(None, None, None)

    def _handler_gate(self):
        import handler

        with patch.object(handler, "_consent_repo",
                          lambda: self.harness.consent):
            return handler._application_consent_error(PRIMARY.consent_context())

    def test_eight_step_synthetic_scenario(self):
        harness = self.harness

        # 1) No consent -> write denied at the repository seam and the handler.
        self.assertFalse(harness.write_allowed())
        with self.assertRaises(ConsentGateDenied):
            harness.create(synthetic_create(1))
        denied = self._handler_gate()
        self.assertEqual(403, denied["statusCode"])
        self.assertEqual("CONSENT_REQUIRED", json.loads(denied["body"])["code"])
        self.assertEqual("NOT_GRANTED", harness.status()["status"])

        # 2) Grant -> stored.
        granted = harness.grant()
        self.assertEqual("GRANTED", granted["status"])
        self.assertEqual(1, granted["version"])
        self.assertEqual(NOTICE_VERSION, granted["noticeVersion"])
        self.assertEqual("APPROVED", granted["noticeState"])
        self.assertTrue(granted["noticeApproved"])
        self.assertIsNone(self._handler_gate())

        # 3) Create -> allowed.
        created = harness.create(synthetic_create(1))
        app_id = created["applicationId"]
        self.assertEqual(1, created["version"])
        self.assertEqual("DRAFT", created["status"])

        # 4) Withdraw -> stored.
        withdrawn = harness.withdraw()
        self.assertEqual("WITHDRAWN", withdrawn["status"])
        self.assertEqual(2, withdrawn["version"])

        # 5) Patch -> denied again.
        self.assertFalse(harness.write_allowed())
        with self.assertRaises(ConsentGateDenied):
            harness.patch(app_id, {"job": {"jobId": "changed"},
                                   "expectedVersion": 1})
        denied = self._handler_gate()
        self.assertEqual(403, denied["statusCode"])

        # 6) Read / export / delete of the existing record still work.
        current = harness.get(app_id)
        self.assertEqual(app_id, current["applicationId"])
        exported = harness.export(app_id)
        self.assertEqual(app_id, exported["application"]["applicationId"])
        harness.delete(app_id, current["version"])
        with self.assertRaises(Exception):
            harness.get(app_id)

        # 7) Regrant -> stored as REGRANTED.
        regranted = harness.grant()
        self.assertEqual("GRANTED", regranted["status"])
        self.assertEqual(3, regranted["version"])
        self.assertIsNone(self._handler_gate())

        # 8) History -> complete ordered events, newest first.
        events = harness.history()
        self.assertEqual(["REGRANTED", "WITHDRAWN", "GRANTED"],
                         [e["event"] for e in events])
        for event in events:
            self.assertEqual("application-storage", event["purpose"])
            self.assertEqual(NOTICE_VERSION, event["noticeVersion"])

    def test_consent_never_leaks_across_user_or_tenant(self):
        self.harness.grant()
        self.assertTrue(self.harness.write_allowed(PRIMARY))
        self.assertFalse(self.harness.write_allowed(SECONDARY_USER))
        self.assertFalse(self.harness.write_allowed(FOREIGN_TENANT))
        with self.assertRaises(ConsentGateDenied):
            self.harness.create(synthetic_create(2), identity=SECONDARY_USER)


if __name__ == "__main__":
    unittest.main()
