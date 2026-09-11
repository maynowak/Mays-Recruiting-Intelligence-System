"""
Source Interface for JobSearch

Defines the contract that all job sources must implement.
Sources can be: Apify actors, direct APIs, local scrapers, etc.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import sys
sys.path.insert(0, '.')

from jobsearch.models import Job, JobSearchRequest, JobSearchResult


class JobSource(ABC):
    """
    Protocol for job sources.
    
    Any source that can provide jobs must implement this interface.
    This allows for pluggable sources: Apify actors, direct APIs, local workers, etc.
    """
    
    @property
    @abstractmethod
    def source_id(self) -> str:
        """Return unique identifier for this source."""
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return human-readable name for this source."""
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 50
    ) -> JobSearchResult:
        """
        Search for jobs.
        
        Args:
            query: Search query (job title, keywords, etc.)
            location: Location filter
            limit: Maximum number of results
            
        Returns:
            JobSearchResult with jobs or error
        """
        pass
    
    @abstractmethod
    def validate_search_request(self, request: JobSearchRequest) -> bool:
        """
        Validate a search request.
        
        Args:
            request: Search request to validate
            
        Returns:
            True if request is valid for this source
        """
        pass
    
    def get_supported_capabilities(self) -> List[str]:
        """
        Return list of capabilities this source supports.
        
        Returns:
            List of capability strings
        """
        return ['search']


class JobSearchProtocol:
    """
    Type hint for job search protocol.
    
    Usage:
        def process_source(source: JobSource) -> None:
            pass
    """
    
    def search(self, query: str, location: Optional[str] = None, limit: int = 50) -> JobSearchResult:
        """
        Search for jobs from this source.
        """
        ...


# Synchronous wrapper for async sources
class SyncJobSource(JobSource):
    """
    Synchronous version of JobSource for non-async environments.
    """
    
    @property
    @abstractmethod
    def source_id(self) -> str:
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        pass
    
    @abstractmethod
    def search_sync(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 50
    ) -> JobSearchResult:
        """Synchronous search method."""
        pass
    
    async def search(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 50
    ) -> JobSearchResult:
        """Async wrapper for sync search."""
        return self.search_sync(query, location, limit)
    
    @abstractmethod
    def validate_search_request(self, request: JobSearchRequest) -> bool:
        pass