"""
Apify Job Source Adapter

Adapts the JobSearch Source Interface for Apify actors.

This adapter allows the Reference Actor (and future agents) to run
on Apify while maintaining compatibility with the abstract Source Interface.
"""

import json
import logging
from typing import Dict, Any, Optional

import sys
sys.path.insert(0, '.')

from jobsearch.models import Job, JobSearchRequest, JobSearchResult
from jobsearch.source_interface import SyncJobSource, JobSearchProtocol

logger = logging.getLogger(__name__)


class ApifyJobSource(SyncJobSource):
    """
    Apify adapter for job sources.
    
    Allows running sources as Apify actors while maintaining
    the standard Source Interface.
    """
    
    def __init__(
        self,
        source_id: str,
        source_name: str,
        actor_id: Optional[str] = None,
        api_token: Optional[str] = None,
        default_options: Optional[Dict[str, Any]] = None
    ):
        self._id = source_id
        self._name = source_name
        self._actor_id = actor_id
        self._api_token = api_token
        self._options = default_options or {}
        self._apify_client = None
    
    @property
    def source_id(self) -> str:
        return self._id
    
    @property
    def source_name(self) -> str:
        return self._name
    
    def _get_apify_client(self):
        """Get or create Apify client."""
        if not hasattr(self, '_client') or self._client is None:
            try:
                from apify_sdk import Actor
                self._client = Actor
            except ImportError:
                logger.warning("Apify SDK not installed, using mock client")
                self._client = None
        return self._client
    
    def validate_search_request(self, request: JobSearchRequest) -> bool:
        """Validate search request."""
        return bool(request.query and request.limit > 0)
    
    def search_sync(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 50
    ) -> JobSearchResult:
        """
        Execute search via Apify actor.
        
        Args:
            query: Search query
            location: Location filter
            limit: Max results
            
        Returns:
            JobSearchResult from Apify actor
        """
        logger.info(f"ApifyJobSource.search: {query} in {location}")
        
        # Check if Apify is available
        client = self._get_apify_client()
        
        if client is None:
            logger.warning("Apify client not available, returning empty result")
            return JobSearchResult(
                source=self.source_id,
                jobs=[],
                error="Apify client not available"
            )
        
        try:
            # In actual Apify environment, you would:
            # 1. Start the actor
            # 2. Wait for completion
            # 3. Process results from datasets
            
            # For now, return error indicating actor needs implementation
            return JobSearchResult(
                source=self.source_id,
                jobs=[],
                error="Actor execution not implemented - placeholder"
            )
            
        except Exception as e:
            logger.error(f"Apify actor execution failed: {e}")
            return JobSearchResult(
                source=self.source_id,
                jobs=[],
                error=str(e)
            )
    
    def get_default_options(self) -> Dict[str, Any]:
        """Get default actor execution options."""
        return {
            'memory_mb': 512,
            'timeout': 300,
            'storage': True,
            'use_status_file': False
        }


class ApifyActor:
    """
    Apify actor wrapper that demonstrates source interface compatibility.
    
    This can be deployed as an Apify actor that uses the JobSearch source interface.
    """
    
    def __init__(self, source: SyncJobSource):
        self.source = source
        self._input_schema = {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'title': 'Search Query'},
                'location': {'type': 'string', 'title': 'Location'},
                'limit': {'type': 'integer', 'default': 50, 'minimum': 1, 'maximum': 100},
                'employmentTypes': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'title': 'Employment Types'
                }
            },
            'required': ['query']
        }
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the actor with input."""
        try:
            request = JobSearchRequest.from_dict(input_data)
            
            if not self.source.validate_search_request(request):
                return {
                    'error': 'Invalid request',
                    'input': input_data
                }
            
            result = self.source.search_sync_with_raw(request)
            
            return {
                'source': result.source,
                'jobs': [job.to_dict() for job in result.jobs],
                'count': len(result.jobs),
                'total': result.total if hasattr(result, 'total') else len(result.jobs),
                'error': result.error
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'input': input_data
            }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return the input schema for Apify registry."""
        return self._input_schema


# Example Apify actor registration
def create_apify_actor(source_class, default_source_id: str = "default"):
    """
    Factory function to create an Apify-compatible actor.
    
    Args:
        source_class: JobSource class to wrap
        default_source_id: Default source ID
        
    Returns:
        Async function that can be used as Apify actor entry point
    """
    async def actor_entry_point():
        from apify_sdk import Actor
        
        async with Actor() as actor:
            actor.set_value('ACTOR_NAME', source_class.__name__)
            
            input_data = await actor.get_input() or {}
            
            source_instance = source_class(**input_data.get('config', {}))
            
            request = JobSearchRequest.from_dict(input_data)
            
            if not source_instance.validate_search_request(request):
                await actor.attach_data('result', {'error': 'Invalid request'})
                return
            
            result = await source_instance.search(request.query, request.location, request.limit)
            
            await actor.attach_data('result', {
                'source': result.source,
                'jobs': [job.to_dict() for job in result.jobs],
                'count': len(result.jobs)
            })
    
    return actor_entry_point


# Example usage
if __name__ == '__main__':
    # Demonstrate creating an Apify-compatible source
    source = ApifyJobSource(
        source_id="test-source",
        source_name="Test Source",
        actor_id="test/actor"
    )
    
    # Create actor wrapper
    apify_actor = ApifyActor(source)
    
    # Test with sample input
    test_input = {
        'query': 'Python Developer',
        'location': 'Berlin',
        'limit': 10
    }
    
    result = apify_actor.run(test_input)
    print(json.dumps(result, indent=2, default=str))