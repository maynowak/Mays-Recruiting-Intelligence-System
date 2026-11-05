import unittest

try:
    import boto3
    from moto import mock_aws
except ImportError:  # pragma: no cover - optional local test dependency
    boto3 = None
    mock_aws = None

from agents.ecosystem.privacy_deletion_ledger import (
    EXPECTED_ABSENT, LedgerScope,
)
from agents.ecosystem.privacy_durable_deletion_ledger import (
    DurableDeletionLedger, DurableDeletionLedgerConflict,
)


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class DurableDeletionLedgerTests(unittest.TestCase):
    @mock_aws
    def test_idempotent_cas_and_restore_reconciliation(self):
        dynamodb = boto3.resource("dynamodb", region_name="eu-central-1")
        table = dynamodb.create_table(
            TableName="ledger",
            KeySchema=[{"AttributeName": "ledgerId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "ledgerId", "AttributeType": "S"},
                {"AttributeName": "operationId", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "gsi-operation",
                "KeySchema": [
                    {"AttributeName": "operationId", "KeyType": "HASH"},
                    {"AttributeName": "ledgerId", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        scope = LedgerScope("user-a", "tenant-a", "partner-a", "issuer-a")
        ledger = DurableDeletionLedger(table=table, table_name="ledger", enabled=True)

        first = ledger.capture(operation_id="op-1", scope=scope,
                               resource_type="APPLICATION", resource_ref="app-1")
        replay = ledger.capture(operation_id="op-1", scope=scope,
                                resource_type="APPLICATION", resource_ref="app-1")
        self.assertEqual(first, replay)
        erased = ledger.mark_erasure_result(
            operation_id="op-1", scope=scope,
            resource_type="APPLICATION", resource_ref="app-1", complete=True)
        self.assertEqual(erased.state, EXPECTED_ABSENT)
        self.assertEqual(
            ledger.reconcile_restore(
                operation_id="op-1", scope=scope,
                restored_resources=[{
                    "tenant_id": "tenant-a", "user_id": "user-a",
                    "partner_application_id": "partner-a", "issuer": "issuer-a",
                    "resourceType": "APPLICATION", "resourceRef": "app-1",
                }]).error_code,
            "RESTORED_ERASED_RESOURCE",
        )

        with self.assertRaises(DurableDeletionLedgerConflict):
            ledger.capture(operation_id="op-1", scope=scope,
                           resource_type="APPLICATION", resource_ref="other-app")
