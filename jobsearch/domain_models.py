"""
JobSearch Domain Model

A persisted user-owned JobSearch object containing:
- unique identity/name
- search configuration  
- per-JobSearch ATS Search Profile

This module defines the canonical model for stored job searches.
Each user can maintain multiple independent JobSearches.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class JobSearchStatus(Enum):
    """Status of a user's saved job search."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class WorkMode(Enum):
    """Work mode preferences for job search."""
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class EmploymentType(Enum):
    """Employment type preferences."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"


@dataclass
class ATSSearchProfile:
    """
    ATS-oriented search/mapping preparation for a JobSearch.
    
    Each JobSearch can have its own independent ATS Search Profile
    with different skills, keywords, roles, and requirements.
    """
    
    target_roles: List[str] = field(default_factory=list)
    ats_keywords: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    preferred_criteria: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    location: Optional[str] = None
    radius: Optional[str] = None
    work_mode: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {}
        if self.target_roles:
            result['targetRoles'] = self.target_roles
        if self.ats_keywords:
            result['atsKeywords'] = self.ats_keywords
        if self.skills:
            result['skills'] = self.skills
        if self.requirements:
            result['requirements'] = self.requirements
        if self.preferred_criteria:
            result['preferredCriteria'] = self.preferred_criteria
        if self.exclusions:
            result['exclusions'] = self.exclusions
        if self.location:
            result['location'] = self.location
        if self.radius:
            result['radius'] = self.radius
        if self.work_mode:
            result['workMode'] = self.work_mode
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ATSSearchProfile':
        """Create from dictionary."""
        return cls(
            target_roles=data.get('targetRoles', []),
            ats_keywords=data.get('atsKeywords', []),
            skills=data.get('skills', []),
            requirements=data.get('requirements', []),
            preferred_criteria=data.get('preferredCriteria', []),
            exclusions=data.get('exclusions', []),
            location=data.get('location'),
            radius=data.get('radius'),
            work_mode=data.get('workMode'),
        )


@dataclass
class SearchConfiguration:
    """
    Search configuration parameters for a JobSearch.
    
    Represents the parameters needed to perform the user's saved search.
    """
    
    query: str = ""
    location: Optional[str] = None
    location_radius: Optional[str] = None
    employment_types: Optional[List[str]] = None
    salary_min: Optional[int] = None
    remote_only: bool = False
    sources: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {'query': self.query}
        if self.location:
            result['location'] = self.location
        if self.location_radius:
            result['locationRadius'] = self.location_radius
        if self.employment_types:
            result['employmentTypes'] = self.employment_types
        if self.salary_min is not None:
            result['salaryMin'] = self.salary_min
        if self.remote_only:
            result['remoteOnly'] = self.remote_only
        if self.sources:
            result['sources'] = self.sources
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchConfiguration':
        """Create from dictionary."""
        return cls(
            query=data.get('query', ''),
            location=data.get('location'),
            location_radius=data.get('locationRadius'),
            employment_types=data.get('employmentTypes'),
            salary_min=data.get('salaryMin'),
            remote_only=data.get('remoteOnly', False),
            sources=data.get('sources'),
        )


@dataclass
class JobSearch:
    """
    Persisted user-owned JobSearch object.
    
    Each user can maintain multiple independent JobSearches.
    Each JobSearch has:
    - a user-owned identity/name
    - its own search configuration
    - its own ATS Search Profile
    
    IMPORTANT: This is user-owned persisted data, not the immediate JobSearch
    from jobsearch/models.py which is for API requests/responses.
    """
    
    job_search_id: str
    user_id: str
    tenant_id: str
    name: str
    search_configuration: SearchConfiguration = field(default_factory=SearchConfiguration)
    ats_search_profile: ATSSearchProfile = field(default_factory=ATSSearchProfile)
    status: JobSearchStatus = JobSearchStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation for storage/API."""
        return {
            'jobSearchId': self.job_search_id,
            'userId': self.user_id,
            'tenantId': self.tenant_id,
            'name': self.name,
            'searchConfiguration': self.search_configuration.to_dict(),
            'atsSearchProfile': self.ats_search_profile.to_dict(),
            'status': self.status.value,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
            'lastUsedAt': self.last_used_at.isoformat() if self.last_used_at else None,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobSearch':
        """Create from dictionary (e.g., from DynamoDB item)."""
        return cls(
            job_search_id=data['jobSearchId'],
            user_id=data['userId'],
            tenant_id=data['tenantId'],
            name=data['name'],
            search_configuration=SearchConfiguration.from_dict(
                data.get('searchConfiguration', {})
            ),
            ats_search_profile=ATSSearchProfile.from_dict(
                data.get('atsSearchProfile', {})
            ),
            status=JobSearchStatus(data.get('status', 'active')),
            created_at=datetime.fromisoformat(data['createdAt']) if data.get('createdAt') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data['updatedAt']) if data.get('updatedAt') else datetime.utcnow(),
            last_used_at=datetime.fromisoformat(data['lastUsedAt']) if data.get('lastUsedAt') else None,
            metadata=data.get('metadata', {}),
        )


def create_job_search(
    job_search_id: str,
    user_id: str,
    tenant_id: str,
    name: str,
    search_configuration: Optional[SearchConfiguration] = None,
    ats_search_profile: Optional[ATSSearchProfile] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> JobSearch:
    """
    Factory function to create a new JobSearch.
    
    Args:
        job_search_id: Unique identifier for this JobSearch
        user_id: Owner's user ID
        tenant_id: Tenant context for isolation
        name: Human-readable name for this JobSearch
        search_configuration: Optional search parameters
        ats_search_profile: Optional ATS-specific search profile
        metadata: Optional additional metadata
    
    Returns:
        New JobSearch instance
    """
    return JobSearch(
        job_search_id=job_search_id,
        user_id=user_id,
        tenant_id=tenant_id,
        name=name,
        search_configuration=search_configuration or SearchConfiguration(),
        ats_search_profile=ats_search_profile or ATSSearchProfile(),
        metadata=metadata or {},
    )