# JOBSEARCH-API-01 — JobSearch CRUD API

**STATUS**: GREEN

## TASK

Implement CRUD API endpoints for the JobSearch domain model using the existing Platform API patterns.

## CONTEXT

Building on JOBSEARCH-PROFILE-01 (GREEN), this milestone implements the API layer for the persisted JobSearch user object.

## ARCHITECTURE

```
JobSearch Frontend
    │
    ▼ HTTPS/JWT
    │
Platform API (Ground Zero Lambda)
    │
    ├── GET /me/jobsearches ────────► JobSearchRepository.list_by_user()
    ├── POST /me/jobsearches ─────► JobSearchRepository.save()
    ├── GET /me/jobsearches/{id} ──► JobSearchRepository.get()
    ├── PUT /me/jobsearches/{id} ──► JobSearchRepository.save()
    └── DELETE /me/jobsearches/{id} ─► JobSearchRepository.delete()
```

## IMPLEMENTATION

### Files Modified/Created

1. **`lambda/handler.py`** - Added JobSearch API handlers:
   - `_handle_jobsearch_list` - GET /me/jobsearches
   - `_handle_jobsearch_create` - POST /me/jobsearches
   - `_handle_jobsearch_get` - GET /me/jobsearches/{jobSearchId}
   - `_handle_jobsearch_update` - PUT /me/jobsearches/{jobSearchId}
   - `_handle_jobsearch_delete` - DELETE /me/jobsearches/{jobSearchId}

2. **`jobsearch/repository.py`** - Persistence layer (from JOBSEARCH-PROFILE-01)

3. **`jobsearch/domain_models.py`** - Domain models (from JOBSEARCH-PROFILE-01)

4. **`tests/unit/jobsearch/`** - Test suite (from JOBSEARCH-PROFILE-01)

### API Endpoints

| Endpoint | Method | Handler | Description |
|----------|--------|---------|-------------|
| `/me/jobsearches` | GET | `_handle_jobsearch_list` | List user's JobSearches |
| `/me/jobsearches` | POST | `_handle_jobsearch_create` | Create new JobSearch |
| `/me/jobsearches/{jobSearchId}` | GET | `_handle_jobsearch_get` | Get single JobSearch |
| `/me/jobsearches/{jobSearchId}` | PUT | `_handle_jobsearch_update` | Update JobSearch |
| `/me/jobsearches/{jobSearchId}` | DELETE | `_handle_jobsearch_delete` | Delete JobSearch |

### Contract

#### GET /me/jobsearches

```json
{
  "jobsearches": [
    {
      "jobSearchId": "uuid",
      "userId": "user-uuid",
      "tenantId": "tenant-uuid",
      "name": "Java Backend Frankfurt",
      "searchConfiguration": {
        "query": "Java Developer",
        "location": "Frankfurt",
        "locationRadius": "30km"
      },
      "atsSearchProfile": {
        "targetRoles": ["Backend Engineer"],
        "skills": ["Java", "Spring"]
      },
      "status": "active",
      "createdAt": "2026-09-20T10:00:00Z"
    }
  ]
}
```

#### POST /me/jobsearches

```json
// Request
{
  "name": "Python Cloud Jobs",
  "searchConfiguration": {
    "query": "Python Cloud Engineer",
    "location": "Berlin"
  },
  "atsSearchProfile": {
    "skills": ["Python", "AWS", "Docker"]
  }
}

// Response (201)
{
  "jobSearch": {
    "jobSearchId": "generated-uuid",
    "userId": "user-uuid",
    "tenantId": "tenant-uuid",
    "name": "Python Cloud Jobs",
    ...
  }
}
```

## AUTH

Uses existing Platform API authentication:
- JWT validation via Cognito
- Token extracted from `Authorization: Bearer <token>` header
- Claims extracted via `_extract_user_context(event)`
- User identity: `sub` claim → `userId`
- Tenant isolation: `custom:tenant_id` claim → `tenantId`

## TENANT ISOLATION

Enforced server-side in repository layer:

1. **All queries filtered by tenantId**
2. **Path parameter extraction for jobSearchId**
3. **Ownership verification** - User can only access their own JobSearches
4. **No client-controlled identity** - Frontend never sets userId or tenantId

```python
# Example: Get JobSearch with isolation
def _handle_jobsearch_get(event, context, job_search_id):
    user_context = _extract_user_context(event)
    
    # Verify ownership/tenant before query
    search = repo.get(
        job_search_id=job_search_id,
        user_id=user_context['userId'],
        tenant_id=user_context['tenantId']
    )
```

## DATA MODEL

### JobSearch

```python
@dataclass
class JobSearch:
    job_search_id: str       # UUID, primary key in DynamoDB
    user_id: str             # Owner, from Cognito JWT
    tenant_id: str           # Tenant, from JWT
    name: str                # Human-readable name
    search_configuration: SearchConfiguration
    ats_search_profile: ATSSearchProfile
    status: JobSearchStatus  # ACTIVE, ARCHIVED, DELETED
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime]
    metadata: Dict[str, Any]
```

## API Convention

Follows existing Platform API patterns:
- JSON responses
- HTTP status codes (200, 201, 400, 401, 403, 404, 500)
- Error format: `{"error": "message"}`
- No separate error codes (uses HTTP status)

## GIT STATUS

```
Branch: main
Commit: After JOBSEARCH-PROFILE-01
Changes:
  Modified: lambda/handler.py (JobSearch handlers added)
```

## AWS/Terraform STATUS

- **NO CHANGES** - No infrastructure modifications
- Repository layer uses existing DynamoDB patterns
- Table would be created with existing naming convention

## TESTS

All tests pass:

```
tests/unit/jobsearch/test_job_search.py: 18 passed
tests/unit/jobsearch/test_repository.py: 10 passed
tests/unit/ats_agent/: 20 passed (existing)
-----------------------------
Total: 48 tests passed
```

## RISKS

1. **Low Risk**: Uses existing patterns, no breaking changes
2. **Low Risk**: Tenant isolation enforced in repository
3. **Medium Risk**: Requires DynamoDB table for Host (not created)

## OPEN POINTS

1. API documentation in OpenAPI format
2. Integration tests with live DynamoDB
3. Frontend integration

## NEXT STEP

**JOBSEARCH-UI-01** - Frontend integration for "Meine Jobsuchen"

---

## TEST COVERAGE

### Unit Tests Implemented

1. `test_creation` - JobSearch can be created with all fields
2. `test_with_configurations` - Full configurations work
3. `test_to_dict` - Serialization works
4. `test_from_dict` - Deserialization works
5. `test_factory_creation` - Factory function works
6. `test_factory_with_custom_config` - Custom configurations work
7. `test_status_values` - Enum values correct
8. `test_independent_profiles` - Multiple jobs have separate profiles
9. `test_same_user_different_searches` - User can have multiple searches
10. `test_full_roundtrip` - Serialization round-trip survives

Repository tests cover:
- Save operations
- Get with tenant isolation
- Get with user isolation  
- Delete operations
- List by user

## SECURITY VERIFICATION

- [x] User context extracted from JWT
- [x] Tenant isolation enforced
- [x] Ownership verification in repository
- [x] No client-controlled identity
- [x] Errors do not leak sensitive data