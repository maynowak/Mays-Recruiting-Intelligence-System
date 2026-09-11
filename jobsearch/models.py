"""
Canonical Job Model for JobSearch API

This module defines the standard job representation used across all sources.
Provider-agnostic, normalized representation of job listings.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EmploymentType(Enum):
    """Standard employment types."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    VOLUNTEER = "volunteer"
    OTHER = "other"


@dataclass
class Job:
    """
    Canonical job representation.
    
    This model is provider-agnostic and represents a normalized job listing
    that can come from any source (Apify, direct API, local scraper, etc.)
    """
    
    # Core identifiers
    id: str                           # Unique job identifier (source-agnostic)
    source_job_id: str                # Original ID from source
    source: str                       # Source identifier (e.g., 'indeed', 'linkedin', 'apify')
    
    # Core job details
    title: str
    company: str
    location: str
    
    # URLs
    url: str                          # Apply/link URL
    
    # Optional details
    description: Optional[str] = None
    employment_type: Optional[str] = None
    salary: Optional[str] = None
    salary_currency: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    remote: Optional[bool] = None
    required_experience: Optional[str] = None
    
    # Metadata
    published_at: Optional[datetime] = None
    source_raw: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    @classmethod
    def from_source_data(cls, data: Dict[str, Any], source_name: str) -> 'Job':
        """
        Create a Job from source-specific data.
        
        Args:
            data: Raw data from source
            source_name: Identifier for the source
            
        Returns:
            Normalized Job instance
        """
        return cls(
            id=data.get('id', ''),
            source_job_id=data.get('source_job_id', ''),
            source=source_name,
            title=data.get('title', ''),
            company=data.get('company', ''),
            location=data.get('location', ''),
            url=data.get('url', ''),
            description=data.get('description'),
            employment_type=data.get('employment_type'),
            salary=data.get('salary'),
            salary_currency=data.get('salary_currency'),
            salary_min=data.get('salary_min'),
            salary_max=data.get('salary_max'),
            remote=data.get('remote'),
            required_experience=data.get('required_experience'),
            published_at=data.get('published_at'),
            source_raw=data.get('source_raw')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            'id': self.id,
            'sourceJobId': self.source_job_id,
            'source': self.source,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'url': self.url,
        }
        
        if self.description:
            result['description'] = self.description
        if self.employment_type:
            result['employmentType'] = self.employment_type
        if self.salary:
            result['salary'] = self.salary
        if self.salary_currency:
            result['salaryCurrency'] = self.salary_currency
        if self.salary_min is not None:
            result['salaryMin'] = self.salary_min
        if self.salary_max is not None:
            result['salaryMax'] = self.salary_max
        if self.remote is not None:
            result['remote'] = self.remote
        if self.required_experience:
            result['requiredExperience'] = self.required_experience
        if self.published_at:
            result['publishedAt'] = self.published_at.isoformat()
        
        return result


@dataclass
class JobSearchRequest:
    """
    Standard request for job search.
    """
    query: str
    location: Optional[str] = None
    location_radius: Optional[str] = None  # e.g., "10mi", "50km"
    employment_type: Optional[List[str]] = None
    salary_min: Optional[int] = None
    remote_only: Optional[bool] = False
    limit: int = 50
    offset: int = 0
    sources: Optional[List[str]] = None  # Specific sources to search
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobSearchRequest':
        """Create request from dictionary."""
        return cls(
            query=data.get('query', ''),
            location=data.get('location'),
            location_radius=data.get('locationRadius'),
            employment_type=data.get('employmentType'),
            salary_min=data.get('salaryMin'),
            remote_only=data.get('remoteOnly', False),
            limit=min(data.get('limit', 50), 100),  # Cap at 100
            offset=data.get('offset', 0),
            sources=data.get('sources')
        )


@dataclass
class JobSearchResponse:
    """
    Standard response for job search.
    """
    jobs: List[Job]
    total: int
    query: str
    sources_queried: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'jobs': [job.to_dict() for job in self.jobs],
            'total': self.total,
            'query': self.query,
        }


@dataclass
class JobSearchResult:
    """Full result from a single source."""
    source: str
    jobs: List[Job]
    error: Optional[str] = None