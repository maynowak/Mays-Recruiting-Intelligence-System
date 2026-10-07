"""
Tests for DELETE /me/profile (privacy deletion).

Written during RIS Truth Recovery against the REAL authorization and
persistence model, verified in T6:

- identity comes exclusively from the JWT `sub` claim
  (_extract_user_context); the request body is never consulted
- the DynamoDB partition key is `userId` alone (verified read-only via
  describe-table on mays-ris-dev-user-profile), therefore the delete is
  inherently scoped to the authenticated subject
- conditional `attribute_exists(userId)` yields 404 when absent
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lambda'))

from handler import _handle_me_profile_delete


def _event(method='DELETE', sub='user-123', tenant='tenant-abc', body=None):
    event = {
        'httpMethod': method,
        'path': '/me/profile',
        'body': body,
        'requestContext': {
            'authorizer': {
                'jwt': {
                    'claims': {
                        'sub': sub,
                        'email': 'test@example.com',
                        'custom:tenant_id': tenant,
                    }
                }
            }
        },
    }
    return event


def _table(conditional_fails=False, raises=None):
    table = MagicMock()
    if conditional_fails:
        err = Exception('conditional failed')
        err.response = {'Error': {'Code': 'ConditionalCheckFailedException'}}
        table.delete_item.side_effect = err
    elif raises is not None:
        table.delete_item.side_effect = raises
    return table


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('USER_PROFILE_TABLE', 'mays-ris-dev-user-profile')
    return monkeypatch


class TestProfileDeletionAuthorization:
    def test_unauthenticated_returns_401(self, env):
        event = {'httpMethod': 'DELETE', 'path': '/me/profile',
                 'requestContext': {}}
        with patch('handler._get_dynamodb') as ddb:
            res = _handle_me_profile_delete(event, None)
        assert res['statusCode'] == 401
        ddb.assert_not_called()

    def test_uses_jwt_subject_not_body(self, env):
        """Caller identity is the JWT sub; body cannot redirect deletion."""
        table = _table()
        ddb = MagicMock()
        ddb.Table.return_value = table
        event = _event(body=json.dumps({'userId': 'victim', 'tenantId': 'other-tenant'}))
        with patch('handler._get_dynamodb', return_value=ddb):
            res = _handle_me_profile_delete(event, None)
        assert res['statusCode'] == 204
        # delete targeted the authenticated subject only
        assert table.delete_item.call_args.kwargs['Key'] == {'userId': 'user-123'}

    def test_cross_tenant_claim_cannot_reach_other_profile(self, env):
        """Different tenant claim still only addresses own userId key."""
        table = _table()
        ddb = MagicMock()
        ddb.Table.return_value = table
        event = _event(sub='user-123', tenant='tenant-other')
        with patch('handler._get_dynamodb', return_value=ddb):
            _handle_me_profile_delete(event, None)
        key = table.delete_item.call_args.kwargs['Key']
        assert key == {'userId': 'user-123'}
        assert 'tenantId' not in key


class TestProfileDeletionSemantics:
    def test_successful_delete_returns_204_empty_body(self, env):
        table = _table()
        ddb = MagicMock()
        ddb.Table.return_value = table
        with patch('handler._get_dynamodb', return_value=ddb):
            res = _handle_me_profile_delete(_event(), None)
        assert res['statusCode'] == 204
        assert res['body'] == ''

    def test_missing_profile_returns_404(self, env):
        ddb = MagicMock()
        ddb.Table.return_value = _table(conditional_fails=True)
        with patch('handler._get_dynamodb', return_value=ddb):
            res = _handle_me_profile_delete(_event(), None)
        assert res['statusCode'] == 404
        assert json.loads(res['body'])['error'] == 'Profile not found'

    def test_delete_is_conditional_on_existence(self, env):
        """404 semantics come from the guard, not a prior read."""
        table = _table(conditional_fails=True)
        ddb = MagicMock()
        ddb.Table.return_value = table
        with patch('handler._get_dynamodb', return_value=ddb):
            _handle_me_profile_delete(_event(), None)
        kwargs = table.delete_item.call_args.kwargs
        assert kwargs['ConditionExpression'] == 'attribute_exists(userId)'
        table.get_item.assert_not_called()

    def test_unconfigured_store_returns_500(self, monkeypatch):
        monkeypatch.delenv('USER_PROFILE_TABLE', raising=False)
        res = _handle_me_profile_delete(_event(), None)
        assert res['statusCode'] == 500
        assert json.loads(res['body'])['error'] == 'Profile store not configured'

    def test_storage_failure_returns_500(self, env):
        ddb = MagicMock()
        ddb.Table.return_value = _table(raises=RuntimeError('boom'))
        with patch('handler._get_dynamodb', return_value=ddb):
            res = _handle_me_profile_delete(_event(), None)
        assert res['statusCode'] == 500
        assert json.loads(res['body'])['error'] == 'Failed to delete profile'