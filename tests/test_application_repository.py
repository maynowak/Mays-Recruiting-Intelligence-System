import os
import unittest
from decimal import Decimal

try:
    import boto3
    from moto import mock_aws
    from jobsearch.application_contract import ApplicationContext, ApplicationContractError
    from jobsearch.application_repository import ApplicationRepository, ApplicationConflict
except ImportError:  # pragma: no cover
    boto3 = None
    mock_aws = lambda fn: fn


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class ApplicationRepositoryTests(unittest.TestCase):
    def test_document_and_legacy_reference_ownership_is_fail_closed(self):
        class Resource:
            resource_type = "CVDocument"
            cv_id = "cv-owned"
            document_id = "doc-owned"

        class Profiles:
            def get(self, resource_id, user_id, tenant_id, partner_app_id, issuer):
                if resource_id == "cv-owned" and user_id == "user-a" and tenant_id == "tenant-a":
                    return Resource()
                return None

        repo = object.__new__(ApplicationRepository)
        repo.profile_repository = Profiles()
        ctx = ApplicationContext("user-a", "tenant-a", "partner-a", "issuer-a")
        repo._verify_cv_reference({"cvId": "cv-owned", "documentId": "doc-owned"}, ctx)
        repo._verify_legacy_reference({"id": "cv-owned", "version": 1}, "cvRef", ctx)
        with self.assertRaisesRegex(ApplicationContractError, "not owned"):
            repo._verify_cv_reference({"cvId": "cv-owned"}, ApplicationContext("user-b", "tenant-a", "partner-a", "issuer-a"))
        with self.assertRaisesRegex(ApplicationContractError, "not owned"):
            repo._verify_cv_reference({"cvId": "cv-owned", "documentId": "doc-other"}, ctx)
        repo.profile_repository = None
        with self.assertRaisesRegex(ApplicationContractError, "cannot be verified"):
            repo._verify_cv_reference({"cvId": "cv-owned"}, ctx)

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
        token = repo.issue_cursor(key, user_id="u1", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2, stage_filter="draft")
        second_key = repo.resolve_cursor(token, user_id="u1", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2, stage_filter="draft")
        self.assertEqual(key, second_key)
        with self.assertRaises(ValueError):
            repo.resolve_cursor(token[:-1] + "0", user_id="u1", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2)
        with self.assertRaises(ValueError):
            repo.resolve_cursor(token, user_id="u2", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2)
        with self.assertRaises(ValueError):
            repo.resolve_cursor(token, user_id="u1", tenant_id="t1", partner_app_id="p1", issuer="https://issuer", scope="applications", resource_type="ApplicationV1", limit=2, stage_filter="submitted")
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

    @mock_aws
    def test_fractional_salary_persists_as_decimal_and_stale_patch_is_409(self):
        os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
        os.environ["RIS_CURSOR_SECRET"] = "test-only-cursor-secret"
        db = boto3.resource("dynamodb", region_name="eu-central-1")
        db.create_table(TableName="applications", KeySchema=[{"AttributeName": "applicationId", "KeyType": "HASH"}, {"AttributeName": "entityKey", "KeyType": "RANGE"}], AttributeDefinitions=[{"AttributeName": "applicationId", "AttributeType": "S"}, {"AttributeName": "entityKey", "AttributeType": "S"}, {"AttributeName": "ownerKey", "AttributeType": "S"}, {"AttributeName": "updatedAt", "AttributeType": "S"}], GlobalSecondaryIndexes=[{"IndexName": "gsi-owner", "KeySchema": [{"AttributeName": "ownerKey", "KeyType": "HASH"}, {"AttributeName": "updatedAt", "KeyType": "RANGE"}], "Projection": {"ProjectionType": "ALL"}, "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1}}], BillingMode="PAY_PER_REQUEST")
        repo = ApplicationRepository("applications", db)
        ctx = ApplicationContext("u1", "t1", "p1", "https://issuer")

        created = repo.create({
            "job": {"jobId": "job-1"},
            "salary": {"expectation": {"amount": 50000.5,
                                       "currency": "EUR", "period": "year"}},
        }, ctx)
        self.assertEqual(Decimal("50000.5"),
                         created["salary"]["expectation"]["amount"])
        raw = repo.table.get_item(Key={
            "applicationId": created["applicationId"],
            "entityKey": "META"}).get("Item")
        self.assertIsInstance(raw["salary"]["expectation"]["amount"], Decimal)

        patched = repo.patch(created["applicationId"], {
            "expectedVersion": 1,
            "salary": {"expectation": {"amount": 60000.75,
                                       "currency": "EUR", "period": "year"}},
        }, ctx)
        self.assertEqual(2, patched["version"])
        self.assertEqual(Decimal("60000.75"),
                         patched["salary"]["expectation"]["amount"])

        with self.assertRaises(ApplicationConflict):
            repo.patch(created["applicationId"],
                       {"expectedVersion": 1, "notes": "stale"}, ctx)


if __name__ == "__main__":
    unittest.main()
