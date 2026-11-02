import os
import unittest

try:
    import boto3
    from moto import mock_aws
    from jobsearch.application_contract import ApplicationContext
    from jobsearch.application_repository import ApplicationRepository, ApplicationConflict
except ImportError:  # pragma: no cover
    boto3 = None
    mock_aws = lambda fn: fn


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class ApplicationRepositoryTests(unittest.TestCase):
    @mock_aws
    def test_scoped_idempotent_create_and_versioned_status(self):
        os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
        os.environ["RIS_CURSOR_SECRET"] = "test-only-cursor-secret"
        db = boto3.resource("dynamodb", region_name="eu-central-1")
        db.create_table(TableName="applications", KeySchema=[{"AttributeName": "applicationId", "KeyType": "HASH"}, {"AttributeName": "entityKey", "KeyType": "RANGE"}], AttributeDefinitions=[{"AttributeName": "applicationId", "AttributeType": "S"}, {"AttributeName": "entityKey", "AttributeType": "S"}, {"AttributeName": "ownerKey", "AttributeType": "S"}, {"AttributeName": "updatedAt", "AttributeType": "S"}], GlobalSecondaryIndexes=[{"IndexName": "gsi-owner", "KeySchema": [{"AttributeName": "ownerKey", "KeyType": "HASH"}, {"AttributeName": "updatedAt", "KeyType": "RANGE"}], "Projection": {"ProjectionType": "ALL"}, "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1}}], BillingMode="PAY_PER_REQUEST")
        repo = ApplicationRepository("applications", db)
        ctx = ApplicationContext("u1", "t1", "p1", "https://issuer")
        body = {"job": {"jobId": "job-1"}, "idempotencyKey": "same-request"}
        first = repo.create(body, ctx)
        second = repo.create(body, ctx)
        self.assertEqual(first["applicationId"], second["applicationId"])
        updated = repo.status(first["applicationId"], "READY", 1, False, ctx)
        self.assertEqual(updated["version"], 2)
        with self.assertRaises(ApplicationConflict):
            repo.status(first["applicationId"], "SUBMITTED", 1, True, ctx)
        other = ApplicationContext("u2", "t1", "p1", "https://issuer")
        with self.assertRaises(LookupError):
            repo.get(first["applicationId"], other)

        with self.assertRaises(ApplicationConflict):
            repo.create({"job": {"jobId": "different"}, "idempotencyKey": "same-request"}, ctx)

    @mock_aws
    def test_pagination_cursor_and_all_identity_dimensions(self):
        os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
        os.environ["RIS_CURSOR_SECRET"] = "test-only-cursor-secret"
        db = boto3.resource("dynamodb", region_name="eu-central-1")
        db.create_table(TableName="applications", KeySchema=[{"AttributeName": "applicationId", "KeyType": "HASH"}, {"AttributeName": "entityKey", "KeyType": "RANGE"}], AttributeDefinitions=[{"AttributeName": "applicationId", "AttributeType": "S"}, {"AttributeName": "entityKey", "AttributeType": "S"}, {"AttributeName": "ownerKey", "AttributeType": "S"}, {"AttributeName": "updatedAt", "AttributeType": "S"}], GlobalSecondaryIndexes=[{"IndexName": "gsi-owner", "KeySchema": [{"AttributeName": "ownerKey", "KeyType": "HASH"}, {"AttributeName": "updatedAt", "KeyType": "RANGE"}], "Projection": {"ProjectionType": "ALL"}, "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1}}], BillingMode="PAY_PER_REQUEST")
        repo = ApplicationRepository("applications", db)
        ctx = ApplicationContext("u1", "t1", "p1", "https://issuer")
        ids = [repo.create({"job": {"jobId": f"job-{n}"}}, ctx)["applicationId"] for n in range(3)]
        page, key = repo.list(ctx, limit=2)
        self.assertEqual(2, len(page))
        token = repo.issue_cursor(key, user_id="u1", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2)
        second_key = repo.resolve_cursor(token, user_id="u1", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2)
        self.assertEqual(key, second_key)
        with self.assertRaises(ValueError):
            repo.resolve_cursor(token[:-1] + "0", user_id="u1", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2)
        with self.assertRaises(ValueError):
            repo.resolve_cursor(token, user_id="u2", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2)
        page2, _ = repo.list(ctx, limit=2, cursor=second_key)
        self.assertEqual(1, len(page2))
        for foreign in (
            ApplicationContext("u2", "t1", "p1", "https://issuer"),
            ApplicationContext("u1", "t2", "p1", "https://issuer"),
            ApplicationContext("u1", "t1", "p2", "https://issuer"),
            ApplicationContext("u1", "t1", "p1", "https://other-issuer"),
        ):
            with self.assertRaises(LookupError):
                repo.get(ids[0], foreign)


if __name__ == "__main__":
    unittest.main()
