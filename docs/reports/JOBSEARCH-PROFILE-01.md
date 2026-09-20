# JOBSEARCH-PROFILE-01 — Persisted JobSearch User Object

**STATUS**: GREEN

## Overview

This milestone establishes the persisted `JobSearch` domain model for user-owned saved job searches in the Mays-Recruiting-Intelligence-System.

## What Was Implemented

### Domain Models (`jobsearch/domain_models.py`)

**Core Classes**:

1. **`JobSearch`** - Main persisted object
   - `job_search_id` - Unique identifier
   - `user_id` - Owner's ID (tenant isolation)
   - `tenant_id` - Tenant context (isolation)
   - `name` - Human-readable identity/name
   - `search_configuration` - Search parameters
   - `ats_search_profile` - ATS-specific search profile
   - `status` - ACTIVE/ARCHIVED/DELETED
   - Timestamps: created_at, updated_at, last_used_at
   - `metadata` - Additional flexible data

2. **`ATSSearchProfile`** - ATS-oriented search preparation
   - target_roles, ats_keywords, skills, requirements
   - preferred_criteria, exclusions
   - location, radius, work_mode

3. **`SearchConfiguration`** - Search parameters
   - query, location, location_radius
   - employment_types, salary_min, remote_only
   - sources

4. **Enums**: JobSearchStatus, WorkMode, EmploymentType

### Repository Layer (`jobsearch/repository.py`)

**`JobSearchRepository`** class provides:
- `save()` - Persist JobSearch
- `get()` - Retrieve with ownership verification
- `list_by_user()` - List user's JobSearches
- `delete()` - Delete with verification

**Tenant/User Isolation**: Enforced in repository layer
- All queries verify userId and tenantId
- Returns None on mismatch (no data leak)

## Key Design Decisions

1. **User-owned identity**: Each JobSearch has its own `name` field
2. **Independent ATS profiles**: Each JobSearch can have different skills/keywords
3. **Tenant isolation**: `tenant_id` enforced in all repository operations
4. **No duplicate logic**: Builds on existing patterns without reinventing

## Test Coverage

**28 tests, all passing**:

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_job_search.py` | 18 | Model validation, serialization, rounds |
| `test_repository.py` | 10 | Repository operations, isolation |

## Architectural Fit

```
User
├── Profile (existing: user-profile table)
├── JobSearch[] (NEW: jobsearch-job_searches table)
│   ├── JobSearch 1 (own ID, name, config, ATS profile)
│   ├── JobSearch 2 ...
│   └── JobSearch N ...
└── Browser ATS (UNAFFECTED: available without registration)
```

## Future Integration Points

1. **API Endpoints**: CRUD for JobSearch (future: JOBSEARCH-API-01)
2. **Terraform**: DynamoDB table creation (not applied in this milestone)
3. **Frontend**: "Meine Jobsuchen" UI integration
4. **Agent Flow**: JobSearch → Agent → ATS (documented only)

## Git Status

```
Current Commit: 818d774 (ATS-REG-01 already committed)
New Files: 4
  - jobsearch/domain_models.py
  - jobsearch/repository.py
  - tests/unit/jobsearch/test_job_search.py
  - tests/unit/jobsearch/test_repository.py
```

## AWS/Terraform Status

- **NO CHANGES** - No AWS infrastructure modified
- **NO APPLY** - No Terraform executed
- Table definition available via `create_jobsearch_table_definitions()` for future deployment

## Verification Checklist

- [x] Repository structure inspected first
- [x] No competing JobSearch model introduced
- [x] Registered user can own multiple JobSearch objects
- [x] Every JobSearch has stable identity and name
- [x] Every JobSearch can have its own ATS Search Profile
- [x] JobSearch data isolated by user/tenant
- [x] Existing browser ATS remains untouched
- [x] Existing server-side ATS remains authoritative
- [x] ATS Agent unchanged
- [x] 28 tests pass
- [x] Documentation updated (this file)
- [x] No AWS apply occurred
- [x] No unrelated changes introduced