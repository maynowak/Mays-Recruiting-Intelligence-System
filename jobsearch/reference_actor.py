"""
Reference Actor for JobSearch

A minimal technical actor that demonstrates the JobSearch Source Interface.
This actor provides mock job data for testing and demonstration purposes.

NOT a production actor - does NOT connect to real job sources.

This actor is designed to:
1. Demonstrate the Source Interface contract
2. Validate the OpenAPI API contract
3. Test end-to-end integration
4. Serve as documentation/example
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

import sys
sys.path.insert(0, '.')

from jobsearch.models import Job, JobSearchRequest, JobSearchResult
from jobsearch.source_interface import SyncJobSource

logger = logging.getLogger(__name__)


class ReferenceActor(SyncJobSource):
    """
    Reference actor for testing and demonstration.
    
    Provides mock job data that demonstrates the Source Interface contract.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._name = "reference_actor"
        self._id = "reference-actor-v1"
        self._version = "1.0.0"
        
        # Mock job data for demonstration
        self._mock_jobs = self._generate_mock_jobs()
    
    @property
    def source_id(self) -> str:
        return self._id
    
    @property
    def source_name(self) -> str:
        return "Reference Actor"
    
    def _generate_mock_jobs(self) -> List[Dict[str, Any]]:
        """Generate mock job data for testing."""
        base_date = datetime.utcnow() - timedelta(days=3)
        
        return [
            {
                'id': str(uuid.uuid4()),
                'source_job_id': f'ref-{i:03d}',
                'title': ['Python Developer', 'Senior Python Engineer', 'Python Backend Developer'][i % 3],
                'company': ['TechCorp', 'DataSolutions', 'CloudFirst'][i % 3],
                'location': ['Berlin, Germany', 'Remote', 'London, UK'][i % 3],
                'url': f'https://example.com/jobs/ref-{i:03d}',
                'employment_type': 'full_time',
                'description': f'This is a {["Python", "Machine Learning", "Data"][i % 3]} position at {["TechCorp", "DataSolutions", "CloudFirst"][i % 3]}.',
                'published_at': base_date + timedelta(days=i)
            }
            for i in range(20)
        ]
    
    def validate_search_request(self, request: JobSearchRequest) -> bool:
        """Validate the search request."""
        if not request.query:
            return False
        
        if request.limit < 1 or request.limit > 100:
            return False
        
        return True
    
    def search_sync(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 50
    ) -> JobSearchResult:
        """
        Perform a mock search.
        
        Args:
            query: Search query
            location: Optional location filter
            limit: Maximum results
            
        Returns:
            JobSearchResult with mock jobs
        """
        logger.info(f"ReferenceActor.search: query='{query}', location='{location}', limit={limit}")
        
        # Simulate search by filtering mock jobs
        matching_jobs = []
        query_lower = query.lower()
        
        for job_data in self._mock_jobs:
            # Simple keyword matching in title and company
            if query_lower in job_data['title'].lower() or \
               query_lower in job_data['company'].lower() or \
               query_lower in job_data['location'].lower():
                matching_jobs.append(job_data)
        
        # Apply location filter if provided
        if location:
            location_lower = location.lower()
            matching_jobs = [
                j for j in matching_jobs 
                if location_lower in j['location'].lower() or 'remote' in j['location'].lower() and 'remote' in location_lower
            ]
        
        # Apply limit
        limited_jobs = matching_jobs[:min(limit, 100)]
        
        # Convert to Job objects
        jobs = [
            Job(**{
                'id': j['id'],
                'source_job_id': j['source_job_id'],
                'source': self.source_id,
                'title': j['title'],
                'company': j['company'],
                'location': j['location'],
                'url': j['url'],
                'description': j.get('description'),
                'employment_type': j.get('employment_type'),
                'published_at': j.get('published_at')
            })
            for j in limited_jobs
        ]
        
        return JobSearchResult(
            source=self.source_id,
            jobs=jobs,
            error=None
        )
    
    def search_sync_with_raw(
        self,
        request: JobSearchRequest
    ) -> JobSearchResult:
        """
        Search using JobSearchRequest object.
        
        Args:
            request: Search request object
            
        Returns:
            JobSearchResult
        """
        if not self.validate_search_request(request):
            return JobSearchResult(
                source=self.source_id,
                jobs=[],
                error="Invalid search request"
            )
        
        return self.search_sync(
            query=request.query,
            location=request.location,
            limit=request.limit
        )


# Actor handler for Apify/Lambda execution
def main():
    """Main entry point for actor execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Reference Actor for JobSearch')
    parser.add_argument('--input', type=str, default='{}',
                        help='JSON input for the actor')
    args = parser.parse_args()
    
    # Parse input
    try:
        input_data = json.loads(args.input) if isinstance(args.input, str) else args.input
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON input: {e}")
        print(json.dumps({'error': 'Invalid input JSON'}))
        return
    
    # Create actor
    actor = ReferenceActor(input_data.get('config', {}))
    
    # Create request from input
    request = JobSearchRequest.from_dict(input_data.get('search', input_data))
    
    # Validate request
    if not actor.validate_search_request(request):
        print(json.dumps({
            'error': 'Invalid request',
            'request': request.__dict__ if hasattr(request, '__dict__') else str(request)
        }))
        return
    
    # Execute search
    result = actor.search_sync_with_raw(request)
    
    # Output result
    output = {
        'source': result.source,
        'jobs': [job.to_dict() for job in result.jobs],
        'count': len(result.jobs),
        'error': result.error
    }
    
    print(json.dumps(output, indent=2, default=str))


# Lambda handler for AWS Lambda deployment
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Reference Actor.
    
    Args:
        event: API Gateway event with search parameters
        context: Lambda context
        
    Returns:
        Response with search results
    """
    logger.info(f"Reference Actor Lambda: Processing request")
    
    try:
        # Parse event body if present
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        # Create request
        request = JobSearchRequest.from_dict(body)
        
        # Create actor and execute
        actor = ReferenceActor(body.get('config'))
        
        if not actor.validate_search_request(request):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid request'})
            }
        
        result = actor.search_sync_with_raw(request)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result.to_dict() if hasattr(result, 'to_dict') else {
                'source': result.source,
                'jobs': [job.to_dict() for job in result.jobs],
                'count': len(result.jobs)
            })
        }
        
    except Exception as e:
        logger.error(f"Error in Lambda handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


# Apify-compatible dataset output
def get_dataset_schema() -> Dict[str, Any]:
    """Return the expected dataset schema for this actor."""
    return {
        'type': 'object',
        'properties': {
            'jobs': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string'},
                        'sourceJobId': {'type': 'string'},
                        'source': {'type': 'string'},
                        'title': {'type': 'string'},
                        'company': {'type': 'string'},
                        'location': {'type': 'string'},
                        'url': {'type': 'string'},
                        'description': {'type': 'string'}
                    },
                    'required': ['id', 'title', 'company', 'location', 'url', 'source', 'sourceJobId']
                }
            }
        }
    }


if __name__ == '__main__':
    main()