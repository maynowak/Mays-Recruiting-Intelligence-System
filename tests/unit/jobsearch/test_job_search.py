"""
Tests for JobSearch Domain Model

Tests for the persisted JobSearch user-owned object.
"""

import pytest
from datetime import datetime
from dataclasses import dataclass

import sys
sys.path.insert(0, '.')

from jobsearch.domain_models import (
    JobSearch, JobSearchStatus, ATSSearchProfile, 
    SearchConfiguration, create_job_search
)


class TestATSSearchProfile:
    """Tests for ATS Search Profile model."""
    
    def test_default_creation(self):
        """ATSSearchProfile can be created with defaults."""
        profile = ATSSearchProfile()
        assert profile.target_roles == []
        assert profile.ats_keywords == []
        assert profile.skills == []
    
    def test_custom_values(self):
        """ATSSearchProfile can be created with values."""
        profile = ATSSearchProfile(
            target_roles=['Software Engineer', 'Senior Dev'],
            ats_keywords=['python', 'django'],
            skills=['python', 'aws', 'docker']
        )
        assert len(profile.target_roles) == 2
        assert 'python' in profile.ats_keywords
        assert 'python' in profile.skills
    
    def test_to_dict(self):
        """ATSSearchProfile serializes to dict."""
        profile = ATSSearchProfile(
            target_roles=['Engineer'],
            location='Berlin',
            radius='30km'
        )
        d = profile.to_dict()
        assert d['targetRoles'] == ['Engineer']
        assert d['location'] == 'Berlin'
        assert d['radius'] == '30km'
    
    def test_from_dict(self):
        """ATSSearchProfile can be created from dict."""
        data = {
            'targetRoles': ['Lead'],
            'atsKeywords': ['python'],
            'location': 'Munich'
        }
        profile = ATSSearchProfile.from_dict(data)
        assert profile.target_roles == ['Lead']
        assert profile.ats_keywords == ['python']
        assert profile.location == 'Munich'


class TestSearchConfiguration:
    """Tests for Search Configuration model."""
    
    def test_default_creation(self):
        """SearchConfiguration can be created with defaults."""
        config = SearchConfiguration()
        assert config.query == ""
        assert config.remote_only is False
    
    def test_with_query(self):
        """SearchConfiguration with query."""
        config = SearchConfiguration(query="Python Developer")
        assert config.query == "Python Developer"
    
    def test_to_dict(self):
        """SearchConfiguration serializes to dict."""
        config = SearchConfiguration(
            query="Python",
            location="Berlin",
            remote_only=True
        )
        d = config.to_dict()
        assert d['query'] == "Python"
        assert d['location'] == "Berlin"
        assert d['remoteOnly'] is True
    
    def test_from_dict(self):
        """SearchConfiguration can be created from dict."""
        data = {'query': 'Java', 'location': 'Frankfurt'}
        config = SearchConfiguration.from_dict(data)
        assert config.query == 'Java'
        assert config.location == 'Frankfurt'


class TestJobSearch:
    """Tests for JobSearch model."""
    
    def test_creation(self):
        """JobSearch can be created with required fields."""
        search = JobSearch(
            job_search_id='js-001',
            user_id='user-123',
            tenant_id='tenant-abc',
            name='Python Jobs'
        )
        assert search.job_search_id == 'js-001'
        assert search.user_id == 'user-123'
        assert search.tenant_id == 'tenant-abc'
        assert search.name == 'Python Jobs'
        assert search.status == JobSearchStatus.ACTIVE
    
    def test_with_configurations(self):
        """JobSearch with full configuration."""
        search = JobSearch(
            job_search_id='js-001',
            user_id='user-123',
            tenant_id='tenant-abc',
            name='Full Config Test',
            search_configuration=SearchConfiguration(query='Python'),
            ats_search_profile=ATSSearchProfile(target_roles=['Engineer'])
        )
        assert search.search_configuration.query == 'Python'
        assert 'Engineer' in search.ats_search_profile.target_roles
    
    def test_to_dict(self):
        """JobSearch serializes to dict."""
        search = JobSearch(
            job_search_id='js-001',
            user_id='user-123',
            tenant_id='tenant-abc',
            name='Test',
        )
        d = search.to_dict()
        assert d['jobSearchId'] == 'js-001'
        assert d['userId'] == 'user-123'
        assert d['tenantId'] == 'tenant-abc'
        assert d['name'] == 'Test'
        assert d['status'] == 'active'
    
    def test_from_dict(self):
        """JobSearch can be created from dict."""
        data = {
            'jobSearchId': 'js-002',
            'userId': 'user-456',
            'tenantId': 'tenant-xyz',
            'name': 'From Dict Test',
            'searchConfiguration': {'query': 'Java Developer'},
            'atsSearchProfile': {'targetRoles': ['Backend']},
            'status': 'active'
        }
        search = JobSearch.from_dict(data)
        assert search.job_search_id == 'js-002'
        assert search.user_id == 'user-456'
        assert search.name == 'From Dict Test'
        assert search.search_configuration.query == 'Java Developer'
        assert 'Backend' in search.ats_search_profile.target_roles


class TestCreateJobSearch:
    """Tests for create_job_search factory function."""
    
    def test_factory_creation(self):
        """Factory creates JobSearch with defaults."""
        search = create_job_search(
            job_search_id='js-001',
            user_id='user-123',
            tenant_id='tenant-abc',
            name='Factory Test'
        )
        assert search.job_search_id == 'js-001'
        assert isinstance(search.search_configuration, SearchConfiguration)
        assert isinstance(search.ats_search_profile, ATSSearchProfile)
    
    def test_factory_with_custom_config(self):
        """Factory accepts custom configurations."""
        config = SearchConfiguration(query='Custom Query')
        profile = ATSSearchProfile(skills=['custom'])
        
        search = create_job_search(
            job_search_id='js-001',
            user_id='user-123',
            tenant_id='tenant-abc',
            name='Custom',
            search_configuration=config,
            ats_search_profile=profile
        )
        assert search.search_configuration.query == 'Custom Query'
        assert 'custom' in search.ats_search_profile.skills


class TestJobSearchStatus:
    """Tests for JobSearchStatus enum."""
    
    def test_status_values(self):
        """Status enum has correct values."""
        assert JobSearchStatus.ACTIVE.value == 'active'
        assert JobSearchStatus.ARCHIVED.value == 'archived'
        assert JobSearchStatus.DELETED.value == 'deleted'


class TestMultipleJobSearches:
    """Tests for multiple JobSearches per user."""
    
    def test_independent_profiles(self):
        """Each JobSearch has independent ATS profile."""
        job1 = create_job_search(
            job_search_id='js-1',
            user_id='user-1',
            tenant_id='tenant-1',
            name='Java Backend',
            ats_search_profile=ATSSearchProfile(
                target_roles=['Java Engineer'],
                skills=['java', 'spring']
            )
        )
        
        job2 = create_job_search(
            job_search_id='js-2',
            user_id='user-1',
            tenant_id='tenant-1',
            name='Python Frontend',
            ats_search_profile=ATSSearchProfile(
                target_roles=['Python Developer'],
                skills=['python', 'react']
            )
        )
        
        # Verify independence
        assert 'java' in job1.ats_search_profile.skills
        assert 'python' not in job1.ats_search_profile.skills
        assert 'python' in job2.ats_search_profile.skills
        assert 'java' not in job2.ats_search_profile.skills
    
    def test_same_user_different_searches(self):
        """Same user can have multiple JobSearches."""
        search1 = create_job_search(
            job_search_id='js-1',
            user_id='user-1',
            tenant_id='tenant-1',
            name='Backend'
        )
        search2 = create_job_search(
            job_search_id='js-2',
            user_id='user-1',
            tenant_id='tenant-1',
            name='Frontend'
        )
        search3 = create_job_search(
            job_search_id='js-3',
            user_id='user-1',
            tenant_id='tenant-1',
            name='Full Stack'
        )
        
        assert search1.name == 'Backend'
        assert search2.name == 'Frontend'
        assert search3.name == 'Full Stack'


class TestSerializationRoundTrip:
    """Tests for serialization/deserialization round trips."""
    
    def test_full_roundtrip(self):
        """JobSearch survives a full serialization round-trip."""
        original = JobSearch(
            job_search_id='js-roundtrip',
            user_id='user-test',
            tenant_id='tenant-test',
            name='Round Trip Test',
            search_configuration=SearchConfiguration(
                query='Test Query',
                location='Berlin',
                remote_only=True
            ),
            ats_search_profile=ATSSearchProfile(
                target_roles=['Test Role'],
                skills=['test', 'python']
            ),
            metadata={'custom': 'data'}
        )
        
        # Serialize
        data = original.to_dict()
        
        # Deserialize
        restored = JobSearch.from_dict(data)
        
        # Verify
        assert restored.job_search_id == original.job_search_id
        assert restored.name == original.name
        assert restored.search_configuration.query == 'Test Query'
        assert 'test' in restored.ats_search_profile.skills