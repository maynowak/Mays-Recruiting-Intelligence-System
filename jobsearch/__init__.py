"""
JobSearch API Package

Provides a standardized, extensible interface for job searching
across multiple sources.

Usage:
    from jobsearch import JobSearchClient
    
    client = JobSearchClient(api_key="...")
    results = client.search("Python Developer", location="Germany")
"""

from jobsearch.models import Job, JobSearchRequest, JobSearchResponse, JobSearchResult
from jobsearch.source_interface import JobSource, SyncJobSource

__all__ = [
    'Job',
    'JobSearchRequest', 
    'JobSearchResponse',
    'JobSearchResult',
    'JobSource',
    'SyncJobSource',
]

version = "1.0.0"