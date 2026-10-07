"""
Tests for JobSearch Repository Adapter

Tests for persistence layer and DynamoDB integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys

from agents.timeutil import utcnow_naive_iso

sys.path.insert(0, '.')

from jobsearch.domain_models import (
    JobSearch, ATSSearchProfile, SearchConfiguration, JobSearchStatus
)


class TestJobSearchRepository:
    """Tests for JobSearch repository operations."""
    
    def test_repository_init(self):
        """Repository can be initialized."""
        from jobsearch.repository import JobSearchRepository
        
        repo = JobSearchRepository(table_name='test-table')
        assert repo.table_name == 'test-table'
    
    def test_repository_uses_env_table(self):
        """Repository falls back to environment variable."""
        from jobsearch.repository import JobSearchRepository
        
        with patch.dict('os.environ', {'JOBSEARCH_TABLE': 'env-table'}):
            repo = JobSearchRepository()
            assert repo.table_name == 'env-table'
    
    def test_repository_save_success(self):
        """Repository can save JobSearch."""
        from jobsearch.repository import JobSearchRepository
        
        mock_table = Mock()
        mock_table.put_item.return_value = {}
        
        repo = JobSearchRepository(table_name='test-table')
        repo._table = mock_table
        
        search = JobSearch(
            job_search_id='js-001',
            user_id='user-123',
            tenant_id='tenant-abc',
            name='Test'
        )
        
        result = repo.save(search)
        assert result is True
        mock_table.put_item.assert_called_once()
    
    def test_repository_get_success(self):
        """Repository can get JobSearch by ID."""
        from jobsearch.repository import JobSearchRepository
        
        mock_table = Mock()
        mock_table.get_item.return_value = {
            'Item': {
                'jobSearchId': 'js-001',
                'userId': 'user-123',
                'tenantId': 'tenant-abc',
                'name': 'Test Job',
                'searchConfiguration': {'query': 'python'},
                'atsSearchProfile': {'skills': ['python']},
                'status': 'active',
                'createdAt': utcnow_naive_iso(),
                'updatedAt': utcnow_naive_iso()
            }
        }
        
        repo = JobSearchRepository(table_name='test-table')
        repo._table = mock_table
        
        result = repo.get('js-001', 'user-123', 'tenant-abc')
        assert result is not None
        assert result.job_search_id == 'js-001'
        assert result.name == 'Test Job'
    
    def test_repository_get_tenant_isolation(self):
        """Repository enforces tenant isolation."""
        from jobsearch.repository import JobSearchRepository
        
        mock_table = Mock()
        mock_table.get_item.return_value = {
            'Item': {
                'jobSearchId': 'js-001',
                'userId': 'user-123',
                'tenantId': 'tenant-other',  # Different tenant!
                'name': 'Test',
                'searchConfiguration': {},
                'atsSearchProfile': {},
                'createdAt': utcnow_naive_iso(),
                'updatedAt': utcnow_naive_iso()
            }
        }
        
        repo = JobSearchRepository(table_name='test-table')
        repo._table = mock_table
        
        result = repo.get('js-001', 'user-123', 'tenant-abc')
        assert result is None  # Should return None due to tenant isolation
    
    def test_repository_get_user_isolation(self):
        """Repository enforces user isolation."""
        from jobsearch.repository import JobSearchRepository
        
        mock_table = Mock()
        mock_table.get_item.return_value = {
            'Item': {
                'jobSearchId': 'js-001',
                'userId': 'user-other',  # Different user!
                'tenantId': 'tenant-abc',
                'name': 'Test',
                'searchConfiguration': {},
                'atsSearchProfile': {},
                'createdAt': utcnow_naive_iso(),
                'updatedAt': utcnow_naive_iso()
            }
        }
        
        repo = JobSearchRepository(table_name='test-table')
        repo._table = mock_table
        
        result = repo.get('js-001', 'user-123', 'tenant-abc')
        assert result is None  # Should return None due to user isolation
    
    def test_repository_delete_success(self):
        """Repository can delete JobSearch."""
        from jobsearch.repository import JobSearchRepository
        
        mock_table = Mock()
        mock_table.get_item.return_value = {
            'Item': {
                'jobSearchId': 'js-001',
                'userId': 'user-123',
                'tenantId': 'tenant-abc',
                'name': 'Test',
                'searchConfiguration': {},
                'atsSearchProfile': {},
                'createdAt': utcnow_naive_iso(),
                'updatedAt': utcnow_naive_iso()
            }
        }
        
        repo = JobSearchRepository(table_name='test-table')
        repo._table = mock_table
        
        result = repo.delete('js-001', 'user-123', 'tenant-abc')
        assert result is True
        mock_table.delete_item.assert_called_once()
    
    def test_repository_list_by_user(self):
        """Repository can list JobSearches for a user."""
        from jobsearch.repository import JobSearchRepository
        
        mock_table = Mock()
        mock_table.scan.return_value = {
            'Items': [
                {
                    'jobSearchId': 'js-001',
                    'userId': 'user-123',
                    'tenantId': 'tenant-abc',
                    'name': 'Test 1',
                    'searchConfiguration': {},
                    'atsSearchProfile': {},
                    'status': 'active',
                    'createdAt': utcnow_naive_iso(),
                    'updatedAt': utcnow_naive_iso()
                },
                {
                    'jobSearchId': 'js-002',
                    'userId': 'user-123',
                    'tenantId': 'tenant-abc',
                    'name': 'Test 2',
                    'searchConfiguration': {},
                    'atsSearchProfile': {},
                    'status': 'active',
                    'createdAt': utcnow_naive_iso(),
                    'updatedAt': utcnow_naive_iso()
                },
                {
                    'jobSearchId': 'js-003',
                    'userId': 'user-456',  # Different user
                    'tenantId': 'tenant-abc',
                    'name': 'Other User',
                    'searchConfiguration': {},
                    'atsSearchProfile': {},
                    'status': 'active',
                    'createdAt': utcnow_naive_iso(),
                    'updatedAt': utcnow_naive_iso()
                }
            ]
        }
        
        repo = JobSearchRepository(table_name='test-table')
        repo._table = mock_table
        
        results = repo.list_by_user('user-123', 'tenant-abc')
        
        assert len(results) == 2
        assert all(r.user_id == 'user-123' for r in results)


class TestTableDefinitions:
    """Tests for DynamoDB table definitions."""
    
    def test_table_definition_exists(self):
        """Table definition can be generated."""
        from jobsearch.repository import create_jobsearch_table_definitions
        
        table_def = create_jobsearch_table_definitions()
        
        assert table_def['tableName'] == 'jobsearch-job_searches'
        assert table_def['billingMode'] == 'PAY_PER_REQUEST'
        assert table_def['hashKey'] == 'jobSearchId'
        assert len(table_def['attributes']) >= 1
        assert len(table_def['gsis']) >= 1
    
    def test_table_definition_has_gsi_user(self):
        """Table definition includes GSI for user lookups."""
        from jobsearch.repository import create_jobsearch_table_definitions
        
        table_def = create_jobsearch_table_definitions()
        
        gsi_user = next((g for g in table_def['gsis'] if g['name'] == 'gsi-user'), None)
        assert gsi_user is not None