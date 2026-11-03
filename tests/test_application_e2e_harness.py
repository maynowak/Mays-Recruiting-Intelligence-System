import json
import os
import unittest

try:
    import boto3
    from moto import mock_aws
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    boto3 = None
    mock_aws = None
    ClientError = Exception

from agents.ecosystem.privacy_application_erasure import ApplicationErasureExecutor
from jobsearch.application_contract import ApplicationContractError, ApplicationContext
from jobsearch.application_repository import ApplicationConflict, ApplicationNotFound
from tests.application_e2e_harness import (
    ApplicationE2EHarness,
    Dev2MutationBlocked,
    HarnessMode,
    PRIMARY,
    SECONDARY_ISSUER,
    SECONDARY_PARTNER,
    SECONDARY_TENANT,
    SECONDARY_USER,
)


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class ApplicationE2EHarnessTests(unittest.TestCase):
    TABLE = "synthetic-local-applications"

    def setUp(self):
        self.env = self._environment()
        self.env.__enter__()
        self.aws = mock_aws()
        self.aws.start()
        self.db = boto3.resource("dynamodb", region_name="eu-central-1")
        self.db.create_table(
            TableName=self.TABLE,
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
                "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        self.harness = ApplicationE2EHarness(self.db, self.TABLE)

    @staticmethod
    def _environment():
        class Environment:
            def __enter__(self):
                self.old = {k: os.environ.get(k) for k in (
                    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                    "AWS_DEFAULT_REGION", "AWS_EC2_METADATA_DISABLED", "RIS_CURSOR_SECRET",
                )}
                os.environ.update({
                    "AWS_ACCESS_KEY_ID": "testing",
                    "AWS_SECRET_ACCESS_KEY": "testing",
                    "AWS_SESSION_TOKEN": "testing",
                    "AWS_DEFAULT_REGION": "eu-central-1",
                    "AWS_EC2_METADATA_DISABLED": "true",
                    "RIS_CURSOR_SECRET": "local-only-application-v1-cursor-secret",
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

    def test_local_mode_is_only_executable_mode(self):
        with self.assertRaises(Dev2MutationBlocked):
            ApplicationE2EHarness(self.db, self.TABLE, mode=HarnessMode.DEV2)
        self.assertEqual(HarnessMode.LOCAL, self.harness.mode)

    def test_full_crud_status_history_cover_export_and_cleanup(self):
        ctx = self.harness.context()
        created = self.harness.create(1, idempotency_key="synthetic-idem-1")
        app_id = created["applicationId"]
        self.assertEqual("DRAFT", created["status"])
        self.assertEqual("draft", created["stage"])
        self.assertEqual(1, created["version"])
        self.assertEqual(created, self.harness.repository.get(app_id, ctx))

        patched = self.harness.repository.patch(
            app_id, {"job": {"jobId": "synthetic-job-updated-1"}, "expectedVersion": 1}, ctx
        )
        self.assertEqual(2, patched["version"])
        ready = self.harness.repository.status(app_id, "READY", 2, False, ctx)
        self.assertEqual(3, ready["version"])
        history = self.harness.repository.add_history(
            app_id, {"type": "synthetic-note", "text": "synthetic-history"}, 3, ctx
        )
        self.assertEqual("synthetic-note", history["event"]["type"])
        letter = self.harness.repository.add_cover_letter(
            app_id, "Synthetic cover letter only.", 4, ctx
        )
        exported = self.harness.repository.export(app_id, ctx)
        self.assertEqual(app_id, exported["application"]["applicationId"])
        # READY transition and the explicit history event are both retained.
        self.assertEqual(2, len(exported["history"]))
        self.assertEqual(letter["versionId"], exported["coverLetterVersions"][0]["versionId"])
        raw = json.dumps(exported, sort_keys=True, default=str)
        for forbidden in ("ownerKey", "credential", "Authorization", "Bearer", "secret"):
            self.assertNotIn(forbidden, raw)

        self.harness.repository.delete(app_id, 5, ctx)
        with self.assertRaises(ApplicationNotFound):
            self.harness.repository.get(app_id, ctx)
        items, _ = self.harness.repository.list(ctx)
        self.assertEqual([], items)

    def test_status_confirmation_and_stale_version_are_rejected(self):
        ctx = self.harness.context()
        app_id = self.harness.create(2)["applicationId"]
        self.harness.repository.status(app_id, "READY", 1, False, ctx)
        with self.assertRaisesRegex(ApplicationContractError, "confirmation"):
            self.harness.repository.status(app_id, "SUBMITTED", 2, False, ctx)
        self.harness.repository.patch(
            app_id, {"job": {"jobId": "synthetic-job-2a"}, "expectedVersion": 2}, ctx
        )
        with self.assertRaisesRegex(ApplicationConflict, "VERSION_CONFLICT"):
            self.harness.repository.patch(
                app_id, {"job": {"jobId": "synthetic-job-2b"}, "expectedVersion": 2}, ctx
            )

    def test_jobsearch_stage_roundtrip_preserves_legacy_lifecycle_and_history(self):
        ctx = self.harness.context()
        app_id = self.harness.create(4)["applicationId"]
        submitted = self.harness.repository.status(app_id, "submitted", 1, True, ctx, "confirmed send")
        self.assertEqual("SUBMITTED", submitted["status"])
        self.assertEqual("submitted", submitted["stage"])
        feedback = self.harness.repository.status(app_id, "feedback", 2, False, ctx)
        self.assertEqual("SUBMITTED", feedback["status"])
        self.assertEqual("feedback", feedback["stage"])
        exported = self.harness.repository.export(app_id, ctx)
        transitions = exported["history"]
        self.assertEqual("draft", transitions[-2]["fromStage"])
        self.assertEqual("submitted", transitions[-2]["toStage"])
        self.assertEqual("submitted", transitions[-1]["fromStage"])
        self.assertEqual("feedback", transitions[-1]["toStage"])

    def test_idempotency_and_payload_conflict(self):
        first = self.harness.create(3, idempotency_key="synthetic-idem-3")
        second = self.harness.create(3, idempotency_key="synthetic-idem-3")
        self.assertEqual(first["applicationId"], second["applicationId"])
        with self.assertRaisesRegex(ApplicationConflict, "IDEMPOTENCY_PAYLOAD_CONFLICT"):
            self.harness.repository.create(
                {"job": {"jobId": "synthetic-different"}, "idempotencyKey": "synthetic-idem-3"},
                self.harness.context(),
            )

    def test_pagination_cursor_tampering_and_identity_binding(self):
        ctx = self.harness.context()
        for sequence in range(10, 14):
            self.harness.create(sequence)
        first, key = self.harness.repository.list(ctx, limit=2)
        self.assertEqual(2, len(first))
        token = self.harness.repository.issue_cursor(
            key, user_id=PRIMARY.user_id, tenant_id=PRIMARY.tenant_id,
            partner_app_id=PRIMARY.partner_application_id, issuer=PRIMARY.issuer,
            scope="applications", resource_type="ApplicationV1", limit=2,
        )
        decoded = self.harness.repository.resolve_cursor(
            token, user_id=PRIMARY.user_id, tenant_id=PRIMARY.tenant_id,
            partner_app_id=PRIMARY.partner_application_id, issuer=PRIMARY.issuer,
            scope="applications", resource_type="ApplicationV1", limit=2,
        )
        second, _ = self.harness.repository.list(ctx, limit=2, cursor=decoded)
        self.assertEqual(2, len(second))
        with self.assertRaises(ValueError):
            self.harness.repository.resolve_cursor(
                token[:-1] + ("0" if token[-1] != "0" else "1"),
                user_id=PRIMARY.user_id, tenant_id=PRIMARY.tenant_id,
                partner_app_id=PRIMARY.partner_application_id, issuer=PRIMARY.issuer,
                scope="applications", resource_type="ApplicationV1", limit=2,
            )
        for identity in (SECONDARY_USER, SECONDARY_TENANT, SECONDARY_PARTNER, SECONDARY_ISSUER):
            with self.assertRaises(ValueError):
                self.harness.repository.resolve_cursor(
                    token, user_id=identity.user_id, tenant_id=identity.tenant_id,
                    partner_app_id=identity.partner_application_id, issuer=identity.issuer,
                    scope="applications", resource_type="ApplicationV1", limit=2,
                )

    def test_cross_identity_reads_are_not_visible(self):
        app_id = self.harness.create(20)["applicationId"]
        for identity in (SECONDARY_USER, SECONDARY_TENANT, SECONDARY_PARTNER, SECONDARY_ISSUER):
            with self.assertRaises(ApplicationNotFound):
                self.harness.repository.get(app_id, self.harness.context(identity))
            items, _ = self.harness.repository.list(self.harness.context(identity))
            self.assertEqual([], items)

    def test_client_identity_fields_are_rejected(self):
        from jobsearch.application_contract import validate_create, validate_patch
        for field in ("applicationId", "ownerId", "userId", "tenantId", "partnerApplicationId", "issuer"):
            with self.assertRaises(ApplicationContractError):
                validate_create({field: "attacker", "job": {"jobId": "synthetic"}})
            with self.assertRaises(ApplicationContractError):
                validate_patch({field: "attacker", "expectedVersion": 1})

    def test_resumable_erasure_and_retry_are_identity_scoped(self):
        for sequence in range(30, 34):
            self.harness.create(sequence)
        ctx = self.harness.context()
        executor = ApplicationErasureExecutor(self.harness.repository)
        result = executor.run(ctx, limit=2)
        self.assertEqual(2, result.deleted)
        self.assertTrue(result.pending)
        result = executor.run(ctx, cursor=result.cursor, limit=2)
        self.assertEqual(2, result.deleted)
        self.assertFalse(result.pending)
        result = executor.run(ctx, limit=2)
        self.assertEqual(0, result.deleted)
        self.assertFalse(result.pending)
        other_items, _ = self.harness.repository.list(self.harness.context(SECONDARY_USER))
        self.assertEqual([], other_items)


if __name__ == "__main__":
    unittest.main()
