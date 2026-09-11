"""
JobSearch API Client

Provides client-side interface for the JobSearch API.
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional

import aiohttp
import asyncio

import sys
sys.path.insert(0, '.')

from jobsearch.models import Job, JobSearchRequest, JobSearchResponse

logger = logging.getLogger(__name__)


class JobSearchClient:
    """
    Client for JobSearch API.
    
    Usage:
        client = JobSearchClient(base_url="https://api.example.com/v1", api_key="...")
        results = client.search("Python Developer", location="Germany")
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {}
            if self.api_key:
                headers['X-API-Key'] = self.api_key
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def search(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        employment_types: Optional[List[str]] = None,
        salary_min: Optional[int] = None,
        remote_only: bool = False,
        sources: Optional[List[str]] = None,
        location_radius: Optional[str] = None
    ) -> JobSearchResponse:
        """
        Search for jobs.
        
        Args:
            query: Search query
            location: Location filter
            limit: Max results
            offset: Pagination offset
            employment_types: Filter by type(s)
            salary_min: Minimum salary
            remote_only: Remote jobs only
            sources: Specific sources to search
            location_radius: Location radius
            
        Returns:
            JobSearchResponse with jobs and metadata
        """
        request = JobSearchRequest(
            query=query,
            location=location,
            location_radius=location_radius,
            limit=limit,
            offset=offset,
            employment_type=employment_types,
            salary_min=salary_min,
            remote_only=remote_only,
            sources=sources
        )
        
        return await self.search_with_request(request)
    
    async def search_with_request(self, request: JobSearchRequest) -> JobSearchResponse:
        """Search with JobSearchRequest object."""
        session = await self._get_session()
        
        url = f"{self.base_url}/jobs/search"
        payload = {
            'query': request.query,
            'location': request.location,
            'limit': request.limit,
            'offset': request.offset,
            'remoteOnly': request.remote_only,
            'salaryMin': request.salary_min,
            'locationRadius': request.location_radius,
            'sources': request.sources,
            'employmentType': request.employment_type
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                error = await response.json()
                raise Exception(f"API Error: {error}")
            
            data = await response.json()
            
            jobs = [Job(**job) for job in data.get('jobs', [])]
            
            return JobSearchResponse(
                jobs=jobs,
                total=data.get('total', 0),
                query=data.get('query', request.query),
                sources_queried=data.get('sourcesQueried')
            )
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a specific job by ID."""
        session = await self._get_session()
        
        url = f"{self.base_url}/jobs/{job_id}"
        
        async with session.get(url) as response:
            if response.status == 404:
                return None
            elif response.status != 200:
                error = await response.json()
                raise Exception(f"API Error: {error}")
            
            data = await response.json()
            return Job(**data)
    
    async def list_sources(self) -> List[Dict[str, Any]]:
        """List available job sources."""
        session = await self._get_session()
        
        url = f"{self.base_url}/sources"
        
        async with session.get(url) as response:
            if response.status != 200:
                error = await response.json()
                raise Exception(f"API Error: {error}")
            
            return await response.json()


# Synchronous client for Lambda usage
class SyncJobSearchClient(JobSearchClient):
    """Synchronous client for environments without async support."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        super().__init__(base_url=base_url, api_key=api_key, timeout=timeout)
        self._session = None
    
    def search_sync(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 50,
        **kwargs
    ) -> JobSearchResponse:
        """Synchronous search (placeholder for sync HTTP client)."""
        import requests
        
        headers = {}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        
        url = f"{self.base_url}/jobs/search"
        payload = {
            'query': query,
            'location': location,
            'limit': limit,
            **kwargs
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        
        if response.status_code != 200:
            raise Exception(f"API Error: {response.text}")
        
        data = response.json()
        
        jobs = [Job(**job) for job in data.get('jobs', [])]
        
        return JobSearchResponse(
            jobs=jobs,
            total=data.get('total', 0),
            query=data.get('query', query)
        )