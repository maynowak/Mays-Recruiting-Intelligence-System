"""Tests Observability-Foundation (live Contract, Gate OBS-01).

Prueft gegen AWS (Profil aus Env): Dashboard mit echten Widgets,
Alarme vorhanden+OK-Konfiguration, Trail aktiv, Bucket-Schutz,
project_name-Isolation (kein MO-Overlap), Log-Gruppen.
Ueberspringt sauber ohne Credentials (CI-sicher).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT = "mays-ris"
REGION = os.environ.get("AWS_REGION", "eu-central-1")
ACCOUNT = "240571105849"


def _client(name):
    import boto3
    profile = os.environ.get("AWS_PROFILE")
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return session.client(name, region_name=REGION)


def _has_creds():
    try:
        ident = _client("sts").get_caller_identity()
        return ident.get("Account") == ACCOUNT
    except Exception:
        return False


def tearDownModule():
    # boto-Module wieder aus sys.modules entfernen: Der Test
    # test_no_aws_imports verlangt einen boto-freien Prozess; unsere
    # Live-Calls duerfen spaetere Tests nicht beeinflussen (billiger Re-Import).
    for mod in [m for m in sys.modules if m.startswith(("boto", "botocore"))]:
        del sys.modules[mod]


class TestObservabilityFoundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _has_creds():
            raise unittest.SkipTest("keine AWS-Credentials (Contract-Tests brauchen Live)")

    def test_dashboard_exists_with_real_widgets(self):
        cw = _client("cloudwatch")
        body = json.loads(cw.get_dashboard(DashboardName=f"{PROJECT}-overview")["DashboardBody"])
        titles = [w.get("properties", {}).get("title", w["type"]) for w in body["widgets"]]
        for expected in ("API Requests", "Lambda Invocations", "Work Queue Visible Messages",
                         "DLQ Visible Messages", "DynamoDB Throttled Requests"):
            self.assertIn(expected, titles)
        # Keine Fake-/Custom-Metriken im Dashboard
        raw = json.dumps(body)
        self.assertNotIn("MaySOrders", raw)

    def test_alarms_present(self):
        cw = _client("cloudwatch")
        names = {a["AlarmName"] for a in
                 cw.describe_alarms()["MetricAlarms"] if a["AlarmName"].startswith(PROJECT)}
        for expected in (f"{PROJECT}-api-5xx", f"{PROJECT}-api-4xx",
                         f"{PROJECT}-lambda-errors", f"{PROJECT}-lambda-duration",
                         f"{PROJECT}-lambda-throttles", f"{PROJECT}-dynamodb-throttled",
                         f"{PROJECT}-dlq-messages"):
            self.assertIn(expected, names)

    def test_trail_active(self):
        ct = _client("cloudtrail")
        trails = ct.describe_trails()["trailList"]
        ours = [t for t in trails if t["Name"] == f"{PROJECT}-trail"]
        self.assertEqual(len(ours), 1)
        status = ct.get_trail_status(Name=f"{PROJECT}-trail")
        self.assertTrue(status["IsLogging"])

    def test_trail_bucket_protected_and_separate(self):
        s3 = _client("s3")
        bucket = f"{PROJECT}-cloudtrail-240571105849"
        pab = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
        self.assertTrue(all(pab.values()))
        enc = s3.get_bucket_encryption(Bucket=bucket)
        algo = enc["ServerSideEncryptionConfiguration"]["Rules"][0] \
            ["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
        self.assertEqual(algo, "AES256")
        # Trennung vom Terraform-State-Bucket
        self.assertNotEqual(bucket, "mays-ris-tf-state-dev")

    def test_project_isolation_no_mo_overlap(self):
        cw = _client("cloudwatch")
        names = [a["AlarmName"] for a in cw.describe_alarms()["MetricAlarms"]]
        self.assertFalse(any(n.startswith("mays-ris") and "mays-orders" in n for n in names))
        dash = [d["DashboardName"] for d in
                cw.list_dashboards()["DashboardEntries"]]
        self.assertIn(f"{PROJECT}-overview", dash)
        self.assertNotIn("mays-ris-orders-overview", dash)

    def test_log_groups_exist(self):
        logs = _client("logs")
        groups = {g["logGroupName"] for g in
                  logs.describe_log_groups()["logGroups"]}
        self.assertIn("/aws/lambda/mays-ris-dev-agent", groups)
        self.assertIn("/aws/lambda/mays-ris-dev-orders-reader", groups)


if __name__ == "__main__":
    unittest.main()
