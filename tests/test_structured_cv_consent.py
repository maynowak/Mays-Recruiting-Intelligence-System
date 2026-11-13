"""Synthetic consent-gate tests for structured CV profile storage.

The notice remains DRAFT; these tests only verify technical fail-closed
behaviour in a local moto table. They are not evidence of legal approval.
"""

import os
import unittest
from unittest.mock import patch

try:
    import boto3
    from moto import mock_aws
    from jobsearch.consent_contract import ConsentContext
    from jobsearch.consent_repository import ConsentRepository
except ImportError:  # pragma: no cover
    boto3 = None
    mock_aws = None

CTX = ConsentContext("user-synthetic-1", "tenant-synthetic-1",
                     "partner-synthetic-1", "issuer-synthetic-1")
PURPOSE = "cv-builder-profile-storage"
DRAFT = "structured-cv-profile-storage-2026-11-12-draft-1"


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class StructuredCvConsentTest(unittest.TestCase):
    def _repo(self):
        db = boto3.resource("dynamodb", region_name="eu-central-1")
        db.create_table(
            TableName="consents-structured",
            KeySchema=[{"AttributeName": "scopeKey", "KeyType": "HASH"},
                       {"AttributeName": "entityKey", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "scopeKey", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        return ConsentRepository("consents-structured", db)

    @mock_aws
    def test_draft_grant_requires_explicit_test_mode(self):
        repo = self._repo()
        with self.assertRaises(Exception):
            repo.grant(CTX, PURPOSE, DRAFT)
        with patch.dict(os.environ, {"STRUCTURED_CV_PROFILE_TEST_MODE": "true"}):
            repo.grant(CTX, PURPOSE, DRAFT)
        self.assertTrue(repo.has_consent(CTX, PURPOSE))
        repo.withdraw(CTX, PURPOSE)
        self.assertFalse(repo.has_consent(CTX, PURPOSE))

    @mock_aws
    def test_notice_enforcement_blocks_draft_even_in_test_mode(self):
        repo = self._repo()
        with patch.dict(os.environ, {
                "STRUCTURED_CV_PROFILE_TEST_MODE": "true",
                "CONSENT_NOTICE_STATE_ENFORCED": "true"}):
            with self.assertRaises(Exception):
                repo.grant(CTX, PURPOSE, DRAFT)

    @mock_aws
    def test_consent_is_bound_to_tenant_and_user(self):
        repo = self._repo()
        with patch.dict(os.environ, {"STRUCTURED_CV_PROFILE_TEST_MODE": "true"}):
            repo.grant(CTX, PURPOSE, DRAFT)
        other_tenant = ConsentContext(CTX.user_id, "other-tenant",
                                      CTX.partner_application_id, CTX.issuer)
        other_user = ConsentContext("other-user", CTX.tenant_id,
                                    CTX.partner_application_id, CTX.issuer)
        self.assertFalse(repo.has_consent(other_tenant, PURPOSE))
        self.assertFalse(repo.has_consent(other_user, PURPOSE))


if __name__ == "__main__":
    unittest.main()
