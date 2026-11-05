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


class CursorSecretConfigurationTests(unittest.TestCase):
    """Cursor signing must fail closed without leaking the key."""

    def setUp(self):
        import jobsearch.application_repository as module
        module._SECRET_CACHE.clear()
        self._saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def test_missing_secret_fails_closed(self):
        from jobsearch.application_repository import _cursor_secret
        os.environ.pop("RIS_CURSOR_SECRET", None)
        os.environ.pop("RIS_CURSOR_SECRET_ARN", None)
        with self.assertRaises(RuntimeError):
            _cursor_secret()

    def test_secret_arn_is_resolved_and_cached(self):
        from unittest.mock import patch
        from jobsearch.application_repository import _cursor_secret

        calls = []

        class FakeClient:
            def get_secret_value(self, **kwargs):
                calls.append(kwargs["SecretId"])
                return {"SecretString": "from-secret-store"}

        arn = "arn:aws:secretsmanager:eu-central-1:1:secret:cursor"
        os.environ.pop("RIS_CURSOR_SECRET", None)
        os.environ["RIS_CURSOR_SECRET_ARN"] = arn
        with patch("jobsearch.application_repository.boto3.client", return_value=FakeClient()):
            self.assertEqual(b"from-secret-store", _cursor_secret())
            self.assertEqual(b"from-secret-store", _cursor_secret())
        self.assertEqual([arn], calls)

    def test_unreadable_secret_fails_closed(self):
        from unittest.mock import patch
        from jobsearch.application_repository import _cursor_secret

        class Boom:
            def get_secret_value(self, **kwargs):
                raise RuntimeError("denied")

        os.environ.pop("RIS_CURSOR_SECRET", None)
        os.environ["RIS_CURSOR_SECRET_ARN"] = "arn:aws:secretsmanager:eu-central-1:1:secret:x"
        with patch("jobsearch.application_repository.boto3.client", return_value=Boom()):
            with self.assertRaises(RuntimeError):
                _cursor_secret()

    def test_plain_env_secret_is_not_preferred_over_arn(self):
        from jobsearch.application_repository import _cursor_secret
        os.environ["RIS_CURSOR_SECRET"] = "local-test-key"
        os.environ["RIS_CURSOR_SECRET_ARN"] = "arn:aws:secretsmanager:eu-central-1:1:secret:x"
        self.assertEqual(b"local-test-key", _cursor_secret())


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class ApplicationUserScopeTests(unittest.TestCase):
    def _table(self):
        db = boto3.resource("dynamodb", region_name="eu-central-1")
        db.create_table(
            TableName="applications",
            KeySchema=[{"AttributeName": "applicationId", "KeyType": "HASH"},
                       {"AttributeName": "entityKey", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "applicationId", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"},
                {"AttributeName": "ownerKey", "AttributeType": "S"},
                {"AttributeName": "userKey", "AttributeType": "S"},
                {"AttributeName": "updatedAt", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {"IndexName": "gsi-owner",
                 "KeySchema": [{"AttributeName": "ownerKey", "KeyType": "HASH"},
                               {"AttributeName": "updatedAt", "KeyType": "RANGE"}],
                 "Projection": {"ProjectionType": "ALL"}},
                {"IndexName": "gsi-user",
                 "KeySchema": [{"AttributeName": "userKey", "KeyType": "HASH"},
                               {"AttributeName": "updatedAt", "KeyType": "RANGE"}],
                 "Projection": {"ProjectionType": "ALL"}},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        return ApplicationRepository("applications", db)

    @mock_aws
    def test_user_scope_spans_partners_but_stays_inside_one_tenant(self):
        os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
        os.environ["RIS_CURSOR_SECRET"] = "test-only-cursor-secret"
        repo = self._table()
        same_user_a = ApplicationContext("u1", "t1", "p1", "https://a")
        same_user_b = ApplicationContext("u1", "t1", "p2", "https://b")
        other_tenant = ApplicationContext("u1", "t2", "p1", "https://a")
        other_user = ApplicationContext("u2", "t1", "p1", "https://a")
        for ctx, job in ((same_user_a, "a"), (same_user_b, "b"),
                         (other_tenant, "c"), (other_user, "d")):
            repo.create({"job": {"jobId": job}}, ctx)

        items, _ = repo.list_by_user("t1", "u1")
        self.assertEqual({"a", "b"}, {x["job"]["jobId"] for x in items})

        deleted = 0
        for _ in range(5):
            count, pending = repo.delete_all_for_user("t1", "u1", limit=1)
            deleted += count
            if not pending:
                break
        self.assertEqual(2, deleted)

        for ctx in (same_user_a, same_user_b):
            with self.assertRaises(LookupError):
                repo.get(items[0]["applicationId"], ctx)
        # Other tenant and other user are untouched.
        self.assertEqual("c", repo.get(repo.list(other_tenant)[0][0]["applicationId"], other_tenant)["job"]["jobId"])
        self.assertEqual("d", repo.get(repo.list(other_user)[0][0]["applicationId"], other_user)["job"]["jobId"])
        # Idempotent re-run.
        self.assertEqual((0, False), repo.delete_all_for_user("t1", "u1"))

    @mock_aws
    def test_deleted_application_removes_history_and_cover_letters(self):
        os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
        os.environ["RIS_CURSOR_SECRET"] = "test-only-cursor-secret"
        repo = self._table()
        ctx = ApplicationContext("u1", "t1", "p1", "https://a")
        app = repo.create({"job": {"jobId": "a"}}, ctx)
        repo.add_history(app["applicationId"], {"type": "note"}, 1, ctx)
        # add_history now increments the application version.
        repo.add_cover_letter(app["applicationId"], "hello", 2, ctx)
        count, pending = repo.delete_all_for_user("t1", "u1")
        self.assertEqual((1, False), (count, pending))
        row = repo.table.query(KeyConditionExpression=boto3.dynamodb.conditions.Key("applicationId").eq(app["applicationId"]))
        self.assertEqual([], row["Items"])
