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
