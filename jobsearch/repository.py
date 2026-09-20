"""
JobSearch Repository Adapter

Provides persistence layer for JobSearch domain objects using DynamoDB.

This adapter handles:
- Saving JobSearch objects to DynamoDB
- Loading JobSearch objects from DynamoDB
- Listing JobSearches for a user
- Tenant isolation enforcement

Follows the existing pattern in lambda/handler.py for DynamoDB operations.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class JobSearchRepository:
    """
    Repository for persisting and retrieving JobSearch objects.
    
    Uses DynamoDB for storage with tenant isolation.
    """
    
    def __init__(self, table_name: Optional[str] = None, dynamodb=None):
        """
        Initialize the repository.
        
        Args:
            table_name: DynamoDB table name (from env if not provided)
            dynamodb: DynamoDB resource (created if not provided)
        """
        self.table_name = table_name or os.environ.get('JOBSEARCH_TABLE')
        self._dynamodb = dynamodb
        self._table = None
    
    @property
    def table(self):
        """Lazily get the DynamoDB table."""
        if self._table is None:
            if not self._dynamodb:
                import boto3
                self._dynamodb = boto3.resource('dynamodb')
            self._table = self._dynamodb.Table(self.table_name) if self.table_name else None
        return self._table
    
    def save(self, job_search) -> bool:
        """
        Save a JobSearch to DynamoDB.
        
        Args:
            job_search: JobSearch instance to save
            
        Returns:
            True if successful, False otherwise
        """
        if not self.table:
            logger.warning("DynamoDB table not configured")
            return False
        
        try:
            item = job_search.to_dict()
            self.table.put_item(Item=item)
            logger.info(f"Saved JobSearch: {job_search.job_search_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving JobSearch {job_search.job_search_id}: {e}")
            return False
    
    def get(self, job_search_id: str, user_id: str, tenant_id: str):
        """
        Get a JobSearch by ID, verifying ownership and tenant isolation.
        
        Args:
            job_search_id: JobSearch identifier
            user_id: Expected owner's user ID
            tenant_id: Expected tenant ID
            
        Returns:
            JobSearch instance or None if not found/authorized
        """
        from jobsearch.domain_models import JobSearch
        
        if not self.table:
            logger.warning("DynamoDB table not configured")
            return None
        
        try:
            response = self.table.get_item(
                Key={'jobSearchId': job_search_id}
            )
            
            item = response.get('Item')
            if not item:
                return None
            
            # Enforce tenant/user isolation
            if item.get('userId') != user_id:
                logger.warning(f"User {user_id} attempted to access JobSearch owned by {item.get('userId')}")
                return None
            
            if item.get('tenantId') != tenant_id:
                logger.warning(f"Tenant {tenant_id} attempted to access JobSearch for tenant {item.get('tenantId')}")
                return None
            
            return JobSearch.from_dict(item)
            
        except Exception as e:
            logger.error(f"Error getting JobSearch {job_search_id}: {e}")
            return None
    
    def list_by_user(self, user_id: str, tenant_id: str, status: Optional[str] = None):
        """
        List all JobSearches for a user and tenant.
        
        Args:
            user_id: User ID filter
            tenant_id: Tenant ID filter
            status: Optional status filter (ACTIVE, ARCHIVED, DELETED)
            
        Returns:
            List of JobSearch instances
        """
        from jobsearch.domain_models import JobSearch
        
        if not self.table:
            logger.warning("DynamoDB table not configured")
            return []
        
        try:
            # Use GSI if available, or scan for simpler implementation
            response = self.table.scan()
            
            results = []
            for item in response.get('Items', []):
                # Enforce tenant/user isolation
                if item.get('userId') != user_id:
                    continue
                if item.get('tenantId') != tenant_id:
                    continue
                if status and item.get('status') != status:
                    continue
                
                try:
                    results.append(JobSearch.from_dict(item))
                except Exception as e:
                    logger.warning(f"Skipping invalid JobSearch item: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error listing JobSearches for user {user_id}: {e}")
            return []
    
    def delete(self, job_search_id: str, user_id: str, tenant_id: str) -> bool:
        """
        Delete a JobSearch, verifying ownership.
        
        Args:
            job_search_id: JobSearch to delete
            user_id: Expected owner's user ID
            tenant_id: Expected tenant ID
            
        Returns:
            True if deleted, False otherwise
        """
        if not self.table:
            logger.warning("DynamoDB table not configured")
            return False
        
        try:
            existing = self.get(job_search_id, user_id, tenant_id)
            if not existing:
                return False
            
            self.table.delete_item(
                Key={'jobSearchId': job_search_id}
            )
            logger.info(f"Deleted JobSearch: {job_search_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting JobSearch {job_search_id}: {e}")
            return False


def create_jobsearch_table_definitions() -> Dict[str, Any]:
    """
    Returns DynamoDB table definition for JobSearch.
    
    This is for Terraform documentation and schema definition.
    The actual table should be created via Terraform.
    """
    return {
        'tableName': 'jobsearch-job_searches',
        'billingMode': 'PAY_PER_REQUEST',
        'hashKey': 'jobSearchId',
        'attributes': [
            {'name': 'jobSearchId', 'type': 'S'},
            {'name': 'userId', 'type': 'S'},
            {'name': 'tenantId', 'type': 'S'},
            {'name': 'status', 'type': 'S'},
        ],
        'gsis': [
            {
                'name': 'gsi-user',
                'hashKey': 'userId',
                'projectionType': 'ALL',
            },
            {
                'name': 'gsi-status',
                'hashKey': 'tenantId',
                'rangeKey': 'status',
                'projectionType': 'ALL',
            },
        ],
        'ttl': {
            'attributeName': 'expiresAt',
            'enabled': True,
        },
    }
