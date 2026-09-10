"""
Unit tests for Platform API handlers.

These tests verify the correct behavior of the Ground Zero Platform API routes.
"""

import json
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handler import (
    handler,
    _extract_user_context,
    _handle_platform,
    _handle_me,
    _handle_me_profile,
    _handle_agents,
    _is_entitlement_valid,
    _get_user_profile,
    _get_agent_catalog,
    _get_entitlements,
    _get_entitlement_for_agent,
    _get_work_item,
    _extract_path_param
)


@pytest.fixture
def mock_event():
    """Create a mock API Gateway event."""
    return {
        'httpMethod': 'GET',
        'path': '/platform',
        'requestContext': {
            'authorizer': {
                'jwt': {
                    'claims': {
                        'sub': 'user-123',
                        'email': 'test@example.com',
                        'custom:tenant_id': 'tenant-abc',
                        'cognito:groups': ['recruiters', 'candidates']
                    }
                }
            }
        }
    }


@pytest.fixture
def auth_event():
    """Create a mock authenticated API Gateway event."""
    return {
        'httpMethod': 'GET',
        'path': '/me',
        'requestContext': {
            'authorizer': {
                'jwt': {
                    'claims': {
                        'sub': 'user-123',
                        'email': 'test@example.com',
                        'custom:tenant_id': 'tenant-abc'
                    }
                }
            }
        }
    }


class TestPlatformHandler:
    """Test cases for GET /platform endpoint."""

    def test_platform_returns_basic_info(self):
        """Platform endpoint should return platform name, version, environment."""
        event = {'httpMethod': 'GET', 'path': '/platform'}
        result = handler(event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        assert 'platform' in body
        assert 'name' in body['platform']
        assert 'version' in body['platform']
        assert 'environment' in body['platform']

    def test_platform_with_custom_env(self):
        """Platform endpoint respects PLATFORM_NAME environment variable."""
        with patch.dict(os.environ, {'PLATFORM_NAME': 'CustomPlatform'}):
            event = {'httpMethod': 'GET', 'path': '/platform'}
            result = handler(event, None)
            
            body = json.loads(result['body'])
            assert body['platform']['name'] == 'CustomPlatform'


class TestMeHandler:
    """Test cases for GET /me endpoint."""

    def test_me_returns_user_context(self, auth_event):
        """Me endpoint returns user identity from JWT."""
        result = handler(auth_event, None)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        assert body['userId'] == 'user-123'
        assert body['email'] == 'test@example.com'
        assert body['tenantId'] == 'tenant-abc'

    def test_me_unauthenticated_returns_401(self):
        """Me endpoint returns 401 for unauthenticated request."""
        event = {'httpMethod': 'GET', 'path': '/me'}
        result = handler(event, None)
        
        assert result['statusCode'] == 401
        body = json.loads(result['body'])
        assert 'error' in body

    def test_me_extracts_groups(self, auth_event):
        """Me endpoint extracts Cognito groups."""
        result = handler(auth_event, None)
        
        body = json.loads(result['body'])
        assert 'groups' in body
        assert 'recruiters' in body['groups']


class TestMeProfileHandler:
    """Test cases for GET /me/profile endpoint."""

    def test_profile_returns_found(self, auth_event):
        """Me profile endpoint returns profile when found."""
        auth_event['path'] = '/me/profile'
        
        with patch('handler._get_user_profile') as mock_profile:
            mock_profile.return_value = {
                'userId': 'user-123',
                'tenantId': 'tenant-abc',
                'displayName': 'Test User'
            }
            
            result = handler(auth_event, None)
            
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['userId'] == 'user-123'

    def test_profile_not_found_returns_404(self, auth_event):
        """Me profile endpoint returns 404 when profile not found."""
        auth_event['path'] = '/me/profile'
        
        with patch('handler._get_user_profile') as mock_profile:
            mock_profile.return_value = None
            
            result = handler(auth_event, None)
            
            assert result['statusCode'] == 404
            body = json.loads(result['body'])
            assert 'error' in body

    def test_profile_unauthenticated_returns_401(self):
        """Me profile endpoint returns 401 for unauthenticated request."""
        event = {'httpMethod': 'GET', 'path': '/me/profile'}
        result = handler(event, None)
        
        assert result['statusCode'] == 401


class TestAgentsHandler:
    """Test cases for GET /agents endpoint."""

    def test_agents_returns_allowed_only(self, auth_event):
        """Agents endpoint returns only allowed agents based on entitlements."""
        auth_event['path'] = '/agents'
        
        with patch('handler._get_entitlements') as mock_ent, \
             patch('handler._get_agent_catalog') as mock_catalog:
            mock_ent.return_value = [
                {'agentId': 'agent-1', 'validUntil': '2099-01-01'}
            ]
            mock_catalog.return_value = {
                'agent-1': {'agentId': 'agent-1', 'status': 'active', 'name': 'Test Agent'}
            }
            
            result = handler(auth_event, None)
            
            body = json.loads(result['body'])
            assert 'agents' in body

    def test_agents_filters_inactive(self, auth_event):
        """Agents endpoint excludes inactive agents."""
        auth_event['path'] = '/agents'
        
        with patch('handler._get_entitlements') as mock_ent, \
             patch('handler._get_agent_catalog') as mock_catalog:
            mock_ent.return_value = [
                {'agentId': 'agent-1'}
            ]
            mock_catalog.return_value = {
                'agent-1': {'agentId': 'agent-1', 'status': 'inactive'}
            }
            
            result = handler(auth_event, None)
            
            body = json.loads(result['body'])
            agent_ids = [a['agentId'] for a in body['agents']]
            assert 'agent-1' not in agent_ids

    def test_agents_unauthenticated_returns_401(self):
        """Agents endpoint returns 401 for unauthenticated request."""
        event = {'httpMethod': 'GET', 'path': '/agents'}
        result = handler(event, None)
        
        assert result['statusCode'] == 401


class TestEntitlementValidation:
    """Test cases for entitlement temporal validation."""

    def test_valid_entitlement_no_dates(self):
        """Entitlement without date constraints is valid."""
        entitlement = {'agentId': 'test-agent'}
        assert _is_entitlement_valid(entitlement) is True

    def test_valid_entitlement_future_valid_from(self):
        """Entitlement with future validFrom is valid."""
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        entitlement = {'agentId': 'test-agent', 'validFrom': future}
        assert _is_entitlement_valid(entitlement) is True

    def test_invalid_entitlement_past_valid_from(self):
        """Entitlement with past validFrom is invalid."""
        past = (datetime.utcnow() - timedelta(days=30)).isoformat()
        entitlement = {'agentId': 'test-agent', 'validFrom': past}
        assert _is_entitlement_valid(entitlement) is False

    def test_valid_entitlement_future_valid_until(self):
        """Entitlement with future validUntil is valid."""
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        entitlement = {'agentId': 'test-agent', 'validUntil': future}
        assert _is_entitlement_valid(entitlement) is True

    def test_invalid_entitlement_past_valid_until(self):
        """Entitlement with past validUntil is invalid."""
        past = (datetime.utcnow() - timedelta(days=30)).isoformat()
        entitlement = {'agentId': 'test-agent', 'validUntil': past}
        assert _is_entitlement_valid(entitlement) is False


class TestUserContextExtraction:
    """Test cases for user context extraction from JWT claims."""

    def test_extracts_basic_claims(self):
        """Extracts user ID, email, and tenant from JWT claims."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-456',
                            'email': 'test@test.com',
                            'custom:tenant_id': 'tenant-xyz'
                        }
                    }
                }
            }
        }
        
        ctx = _extract_user_context(event)
        
        assert ctx['userId'] == 'user-456'
        assert ctx['email'] == 'test@test.com'
        assert ctx['tenantId'] == 'tenant-xyz'

    def test_extracts_groups_from_string(self):
        """Extracts groups from Cognito groups claim (string format)."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-123',
                            'cognito:groups': 'admin,recruiter'
                        }
                    }
                }
            }
        }
        
        ctx = _extract_user_context(event)
        
        assert ctx['groups'] == ['admin', 'recruiter']

    def test_extracts_groups_from_list(self):
        """Extracts groups from Cognito groups claim (list format)."""
        event = {
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-123',
                            'cognito:groups': ['admin', 'recruiter']
                        }
                    }
                }
            }
        }
        
        ctx = _extract_user_context(event)
        
        assert ctx['groups'] == ['admin', 'recruiter']

    def test_handles_missing_claims(self):
        """Handles missing JWT claims gracefully."""
        event = {'requestContext': {'authorizer': {}}}
        ctx = _extract_user_context(event)
        
        assert ctx['userId'] is None
        assert ctx['tenantId'] is None


class TestNotFoundRoute:
    """Test cases for 404 responses."""

    def test_unknown_route_returns_404(self):
        """Unknown routes return 404."""
        event = {'httpMethod': 'GET', 'path': '/unknown'}
        result = handler(event, None)
        
        assert result['statusCode'] == 404


class TestSQSHandling:
    """Test cases for SQS event handling."""

    def test_sqs_event_returns_200(self):
        """SQS events return 200 status."""
        event = {
            'Records': [{
                'body': json.dumps({'workId': 'test-123', 'type': 'test'})
            }]
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 200


class TestAgentAPI:
    """Test cases for Agent API routes."""

    def test_list_agents(self):
        """GET /api/agents returns agent list."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/agents',
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-123',
                            'tenant_id': 'tenant-abc'
                        }
                    }
                }
            }
        }
        
        with patch('handler._get_agent_catalog') as mock_catalog:
            mock_catalog.return_value = {
                'agent-1': {'agentId': 'agent-1', 'status': 'active'}
            }
            
            result = handler(event, None)
            
            assert result['statusCode'] == 200

    def test_get_agent_by_id(self):
        """GET /api/agents/{agentId} returns agent."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/agents/agent-1',
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-123',
                            'tenant_id': 'tenant-abc'
                        }
                    }
                }
            }
        }
        
        with patch('handler._get_entitlement_for_agent') as mock_ent, \
             patch('handler._get_agent_catalog') as mock_catalog:
            mock_ent.return_value = {
                'agentId': 'agent-1',
                'validUntil': '2099-01-01'
            }
            mock_catalog.return_value = {
                'agent-1': {'agentId': 'agent-1', 'status': 'active'}
            }
            
            result = handler(event, None)
            
            assert result['statusCode'] == 200

    def test_get_agent_unauthenticated(self):
        """GET /api/agents requires authentication."""
        event = {
            'httpMethod': 'GET',
            'path': '/api/agents/agent-1'
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 401

    def test_execute_agent(self):
        """POST /api/agents/{agentId}/execute creates work."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/agents/agent-1/execute',
            'body': json.dumps({
                'capability': 'analyze_cv',
                'payload': {'cv': 'data'}
            }),
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-123',
                            'tenant_id': 'tenant-abc'
                        }
                    }
                }
            }
        }
        
        with patch('handler._get_entitlement_for_agent') as mock_ent, \
             patch('handler._get_agent_catalog') as mock_catalog, \
             patch('handler._get_dynamodb') as mock_db, \
             patch('handler._get_sqs') as mock_sqs:
            mock_ent.return_value = {
                'agentId': 'agent-1',
                'validUntil': '2099-01-01'
            }
            mock_catalog.return_value = {
                'agent-1': {'agentId': 'agent-1', 'status': 'active', 'version': '1.0.0'}
            }
            mock_db.return_value.Table.return_value.put_item.return_value = {}
            mock_sqs.return_value.send_message.return_value = {}
            
            result = handler(event, None)
            
            assert result['statusCode'] == 202

    def test_execute_agent_unauthorized(self):
        """POST /api/agents/{agentId}/execute denies unauthorized."""
        event = {
            'httpMethod': 'POST',
            'path': '/api/agents/agent-1/execute',
            'body': json.dumps({'capability': 'analyze_cv'}),
            'requestContext': {
                'authorizer': {
                    'jwt': {
                        'claims': {
                            'sub': 'user-123',
                            'tenant_id': 'tenant-abc'
                        }
                    }
                }
            }
        }
        
        with patch('handler._get_entitlement_for_agent') as mock_ent:
            mock_ent.return_value = None
            
            result = handler(event, None)
            
            assert result['statusCode'] == 403


class TestPathExtraction:
    """Test cases for path parameter extraction."""

    def test_extract_agent_id(self):
        """Extracts agent ID from path."""
        path = '/api/agents/agent-123'
        result = _extract_path_param(path, 'agentId')
        assert result == 'agent-123'

    def test_extract_work_id(self):
        """Extracts work ID from path."""
        path = '/api/agents/agent-456/work/work-789'
        result = _extract_path_param(path, 'workId')
        assert result == 'work-789'

    def test_extract_invalid_path(self):
        """Returns None for invalid path."""
        result = _extract_path_param('/invalid/path', 'agentId')
        assert result is None