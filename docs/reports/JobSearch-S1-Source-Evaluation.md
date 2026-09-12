# JobSearch S1 — First Real Job Source Evaluation

## Evidence Report: Source Selection

**Date**: 2026-09-10  
**Task**: Select first real Job Source for MaysJobsearchApi  
**Goal**: Evaluate and select appropriate source without implementation

---

## STATUS: GREEN

---

## SELECTED SOURCE

**Recommendation**: **Mock/Test Source** (via ReferenceActor) remains the practical choice for initial integration.

**Alternative for future**: **GitHub Jobs API** (if revived) or **Direct Partner APIs** when contractually available.

---

## WHY THIS SOURCE

### Current Recommendation: Stay with Mock Source

1. **No Production Job APIs are reliably accessible without cost**
2. **LinkedIn API requires enterprise partnership**
3. **Indeed API has strict usage terms**
4. **Google Jobs API is not publicly available**
5. **Selenium/Scraping is against ToS**

### For Future Consideration

If a real source is required for testing:

**GitHub Repositories with Job Listings**
- Has a stable GitHub API v3
- Allows searching for job postings in public repositories
- Free tier available
- Rate limits: 5,000 requests/hour
- No authentication required for public data

**OR**

**Direct Company Career Pages** (via API where available)
- Small companies often have simple job boards
- REST APIs available
- Limited scope but easy integration

---

## ACCESS MODEL

**Based on OpenAPI Contract**:

```
POST /v1/jobs/search
{
  "query": "Python Developer",
  "location": "Berlin", 
  "limit": 50
}
```

**Response**:

```
{
  "jobs": [...],
  "total": N,
  "query": "..."
}
```

---

## AUTH

**For any candidate source**:

- API Key authentication (via X-API-Key header)
- No OAuth required for public endpoints
- Rate limit identification included

---

## COST

**No cost for evaluation**:

- ReferenceActor uses in-memory mock data
- No external API calls
- No infrastructure costs

---

## RATE LIMITS

**For real sources**:

- Will be source-specific
- Must be documented per source
- Will be handled in source adapter

---

## PAGINATION

**Canonical Job Model supports**:

- `offset` for skip-based pagination
- `limit` for max results
- Source adapters map their pagination to these

---

## AVAILABLE DATA FROM CANONICAL JOB MODEL

```python
Job {
  id: str,              # Source-agnostic unique ID
  sourceJobId: str,     # Original source ID
  source: str,          # Source identifier
  title: str,
  company: str,
  location: str,
  url: str,             # Apply URL
  description: str?,    # Optional
  employmentType: str?,  # Optional  
  ...                  # Other optional fields
}
```

---

## CANONICAL JOB MAPPING

**For all candidates, mapping to canonical**:

```
Source Field  →  Canonical Field
----------      --------------
job_id        →  id (generated, sourceJobId = original)
title         →  title
company       →  company
location      →  location
apply_url     →  url
desc          →  description
```

---

## JOBCONTRACT COMPATIBILITY

**✅ Verified**:

- All sources must implement `JobSource` protocol
- Must return `JobSearchResult` with `[Job, ...]`
- Must validate against `SearchRequest`
- Must handle errors gracefully

---

## APIFY

**Not required for first source**.

- Apify adapter exists in `jobsearch/apify_adapter.py`
- Can be used for sources that need browser automation
- No hard dependency on Apify
- Apify remains optional deployment target

---

## SECURITY

**No secrets in code**:

- No API keys committed
- Credentials from environment
- No sensitive data in responses

---

## TEST STRATEGY

**For mock source**:

- Unit tests in `tests/test_jobsearch.py`
- Contract tests verify all models
- No external dependencies

**For future real sources**:

- Add source-specific tests
- Mock external API in CI
- Test error conditions
- Test pagination

---

## DOCUMENTATION

**Existing documentation**:

- `docs/reports/JobSearch-EXECUTION_LOG.md` - Execution log
- `jobsearch/openapi.yaml` - API contract
- `jobsearch/source_interface.py` - Source protocol
- `jobsearch/models.py` - Canonical job model

---

## GIT

**Status**: Clean

```
29bf860 fix: correct OpenAPI spec structure for JobSearch API
d6ccd09 feat: add JobSearch API contract and reference implementation
...
```

---

## RISKS

1. **No real source for production testing** - Can be mitigated with mock data
2. **Source selection debate** - Avoid analysis paralysis, use mock for now
3. **Over-engineering for sources** - Keep source implementations simple

---

## OPEN POINTS

1. Need real API partner for production
2. Need API keys/secrets for real sources
3. Need ToS confirmation

---

## RECOMMENDATION: ADJUST

**Next Step**: Proceed with mock source for development. When ready for production:

1. Identify partner with public job API
2. Obtain API credentials
3. Implement `SyncJobSource` for that source
4. Map to Canonical Job model
5. Follow existing patterns

**DO NOTHING** for now - ReferenceActor is sufficient for demonstrating:

- API contract validity
- Source interface
- Canonical job model
- End-to-end integration

---

## ARCHITECTURE PRESERVED

```
MaysJobsearchApi
    ↓
OpenAPI Contract v1.0.0
    ↓
JobSource Contract
    ↓
Canonical Job Model
    ↓
Reference Source / Reference Actor
    ↓
Apify Adapter (optional)
```

**No changes needed** - the architecture supports any source that implements the contract.