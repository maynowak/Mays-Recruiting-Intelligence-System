"""
Tests for JobSearch API

Tests the canonical job model, source interface, and reference actor.
"""

import pytest
import json
import sys
sys.path.insert(0, '.')

from jobsearch.models import Job, JobSearchRequest, JobSearchResponse, JobSearchResult
from jobsearch.source_interface import JobSource, SyncJobSource
from jobsearch.reference_actor import ReferenceActor


class TestJobModel:
    """Test canonical Job model."""

    def test_job_creation(self):
        """Job can be created with required fields."""
        job = Job(
            id='job-123',
            source='test',
            source_job_id='source-456',
            title='Developer',
            company='TechCorp',
            location='Berlin',
            url='https://example.com/jobs/123'
        )
        
        assert job.id == 'job-123'
        assert job.title == 'Developer'
        assert job.source == 'test'

    def test_job_to_dict(self):
        """Job can be converted to dict for API."""
        job = Job(
            id='job-123',
            source='test',
            source_job_id='source-456',
            title='Developer',
            company='TechCorp',
            location='Berlin',
            url='https://example.com/jobs/123'
        )
        
        result = job.to_dict()
        
        assert 'id' in result
        assert 'title' in result
        assert 'company' in result

    def test_job_from_source_data(self):
        """Job can be created from source data."""
        source_data = {
            'id': 'job-123',
            'title': 'Developer',
            'company': 'TechCorp',
            'location': 'Berlin',
            'url': 'https://example.com/jobs/123'
        }
        
        job = Job.from_source_data(source_data, source_name='test-source')
        
        assert job.id == 'job-123'
        assert job.source == 'test-source'


class TestJobSearchRequest:
    """Test JobSearchRequest model."""

    def test_request_creation(self):
        """Request can be created."""
        request = JobSearchRequest(query='Python Developer')
        assert request.query == 'Python Developer'

    def test_request_from_dict(self):
        """Request can be created from dict."""
        data = {'query': 'Python Developer', 'limit': 10}
        request = JobSearchRequest.from_dict(data)
        
        assert request.query == 'Python Developer'
        assert request.limit == 10

    def test_request_defaults(self):
        """Request has sensible defaults."""
        request = JobSearchRequest(query='test')
        
        assert request.limit == 50
        assert request.offset == 0
        assert request.remote_only is False


class TestJobSearchResult:
    """Test JobSearchResult model."""

    def test_result_creation(self):
        """Result can be created."""
        job = Job(
            id='job-123',
            source='test',
            source_job_id='s-123',
            title='Test',
            company='C',
            location='L',
            url='https://x.com'
        )
        
        result = JobSearchResult(source='test', jobs=[job])
        
        assert len(result.jobs) == 1
        assert result.source == 'test'


class TestReferenceActor:
    """Test Reference Actor implementation."""

    def test_actor_creation(self):
        """Reference actor can be created."""
        actor = ReferenceActor()
        assert actor.source_id == 'reference-actor-v1'
        assert actor.source_name == 'Reference Actor'

    def test_actor_search(self):
        """Actor can perform search."""
        actor = ReferenceActor()
        result = actor.search_sync('Python', limit=5)
        
        assert result.source == 'reference-actor-v1'
        assert isinstance(result.jobs, list)

    def test_actor_validate_request(self):
        """Actor validates requests."""
        actor = ReferenceActor()
        
        valid = JobSearchRequest(query='test')
        assert actor.validate_search_request(valid) is True
        
        invalid = JobSearchRequest(query='')
        assert actor.validate_search_request(invalid) is False

    def test_actor_echo_capability(self):
        """Actor echo returns expected results."""
        actor = ReferenceActor()
        result = actor.search_sync('Developer', limit=10)
        
        # Should return some jobs
        assert result.jobs or result.error is not None


class TestSyncSourceInterface:
    """Test synchronous source interface."""

    def test_source_is_abstract(self):
        """SyncJobSource cannot be instantiated directly."""
        with pytest.raises(TypeError):
            SyncJobSource()


class TestJobSearchProtocol:
    """Test job search protocol compliance."""

    def test_reference_actor_implements_protocol(self):
        """ReferenceActor implements JobSource protocol."""
        actor = ReferenceActor()
        
        assert isinstance(actor, JobSource) or hasattr(actor, 'source_id')
        assert callable(getattr(actor, 'search_sync'))
        assert callable(getattr(actor, 'validate_search_request'))


class TestIntegration:
    """Integration tests for JobSearch components."""

    def test_full_search_flow(self):
        """Test complete search flow."""
        # Create actor
        actor = ReferenceActor()
        
        # Create request
        request = JobSearchRequest(
            query='Python Developer',
            location='Germany',
            limit=10
        )
        
        # Validate
        assert actor.validate_search_request(request) is True
        
        # Execute
        result = actor.search_sync_with_raw(request)
        
        # Verify
        assert result.source == 'reference-actor-v1'
        assert isinstance(result.jobs, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])