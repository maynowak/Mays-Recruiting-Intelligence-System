# MATCHING-AUDIT-01 — Matching Implementation Audit

**Status**: AUDIT COMPLETE

## Executive Summary

This audit documents the current state of matching/anxiety integration in the Mays-Recruiting-Intelligence-System.

## Key Finding

**MATCHING IS EXTERNAL** - The actual job matching implementation is in `mays-jobsearch` (external repository), NOT in this repository.

## 1. Matching Entry Points

### Current Repository (Mays-Recruiting-Intelligence-System)

There is **NO dedicated matching implementation** in this repository. The matching logic is:

1. **ATS Agent** (`agents/ats_agent/agent.py`) - HTTP client that forwards to external ATS API
2. **Reference Actor** (`jobsearch/reference_actor.py`) - Simple keyword matching for testing only

### External Repository (mays-jobsearch)

The actual matching is performed by the external `mays-jobsearch` repository which exposes:

```
POST /api/ats-analysis
```

## 2. Matching Core Implementation

### Location: mays-jobsearch (external)

Based on `docs/reports/ARCH-ATS-BOUNDARY-01.md`:

**Exported Functions:**
```javascript
export function analyzeJobForAts(job, profile)
export function matchRequirement(req, cvSkills, cvData)
```

**Data Contract:**
```typescript
// Input
{
  job: CanonicalJob,
  profile: Profile,
  ai?: { enabled: boolean, consent: boolean }
}

// Output
{
  analysis: AtsAnalysisResult,
  recommendations: Recommendation[],
  ai: AiInstructions
}
```

## 3. Input Fields Used

### CV/Profile Fields (from test fixtures and code)

**Used in current repository:**
- `skills` - String of skills (used in ATS agent)
- `job` - Job object with title (used in ATS agent)
- Basic work item fields (workId, type, tenantId, capability)

**NOT present in current repository (from external Mantle job search docs):**
- Target Role
- Work Modes
- Employment Types
- Experience
- Certifications
- Salary expectations

### Job Fields

**Used in current repository:**
- `title` - Job title
- `company` - Company name
- `location` - Job location

**NOT present in current repository:**
- Skills requirements
- Detailed descriptions
- Requirements list
- Work mode
- Employment type

## 4. Matching Methodology

### Code Analysis

From `agents/ecosystem/router.py`:
```
Simple deterministic selection for now (no AI ranking)
```

### Actual Matching

**External mays-jobsearch ATS API** - Implementation details not available in this repository.

**Reference Actor (testing only):**
- Simple keyword matching in title and company
- Case-insensitive substring matching
- No scoring, ranking, or weighting

```python
# From reference_actor.py:109
if query_lower in job_data['title'].lower() or \
   query_lower in job_data['company'].lower() or \
   query_lower in job_data['location'].lower():
    matching_jobs.append(job_data)
```

### NOT IMPLEMENTED in this repository:
- Semantic matching
- Embeddings
- LLM-based matching
- Skill deduplication
- Synonym recognition
- Weighted scoring
- Threshold filtering

## 5. Search vs Matching

### Search
- Entry point: `jobsearch/reference_actor.py:search_sync()`
- Method: Keyword search in job title/company/location
- Purpose: Find jobs that contain search terms

### Matching
- Entry point: `agents/ats_agent/agent.py` → External ATS API
- Method: External `analyzeJobForAts()` function
- Purpose: Score how well a CV matches a job

## 6. CV Flow

```
CV Upload
    ↓
Consent
    ↓
Profile (skills, etc.)
    ↓
ATS Agent (analyze.job capability)
    ↓
ATSHttpClient
    ↓
POST /api/ats-analysis (external)
    ↓
Match Result (score, recommendations)
```

**Key Observation:** The CV information flow exists but the actual matching computation happens externally.

## 7. ATS Separation

**ATS** (`agents/ats_agent/`) - This repository's boundary:
- HTTP client to external API
- Capability: `analyze.job`
- Registry: `agents.ats_agent.registry`

**Matching** (mays-jobsearch - external):
- `analyzeJobForAts()` function
- `matchRequirement()` function
- Full matching implementation

**SEPARATION CONFIRMED** - ATS agent in this repository is just an HTTP client wrapper.

## 8. Multi-Skill Search Analysis

### User Input Parsing

**InfoPanel/Brain/JobSearch state** handles:
- Parsing comma/space separated skills
- No complex parsing (e.g., "AWS JAVA Teetrinkerin")

### Current Implementation

From reference actor - simple string matching:
```python
if query_lower in job_data['title'].lower():
    matching_jobs.append(job_data)
```

**No special handling** for multi-element inputs like:
```
AWS, Java, Terraform
AWS; Java; Terraform
AWS Java Terraform
```

These would be treated as literal search strings.

## 9. Existing API & Endpoints

### Agent Execution API
- `POST /api/agents/{agentId}/execute`
- Routes via capability matching
- Uses `agents/agent_body/router.py`

### Job Search API (Internal)
- Based on request content, forwarded to external service
- No dedicated matching endpoint in this repository

### CAPABILITY: `match.evaluate`
- Referenced in `agents/ecosystem/chain.py:238`
- **No implementation exists** - Just a placeholder in the processing chain

## 10. Tests Coverage

### For Matching:
- NONE - No tests specifically for matching logic

### For ATS Agent:
- `tests/unit/ats_agent/test_ats_agent.py` - 10 tests
- Tests HTTP client behavior only
- Mocks external API responses

### For Job Search:
- `tests/unit/jobsearch/test_job_search.py` - Basic request tests

## Findings Summary

| Area | Current State | Location |
|------|---------------|----------|
| Match Entry Point | External API only | `agents/ats_agent/` |
| Match Logic | External (mays-jobsearch) | NOT IN REPO |
| Capabilities | `analyze.job` registered | `agents/ats_agent/registry.py` |
| CAPABILITY match.evaluate | Placeholder only | `agents/ecosystem/chain.py` |
| CV Processing | Passes through to external | `agents/ats_agent/agent.py` |
| Job Search | Reference actor keyword matches | `jobsearch/reference_actor.py` |
| Scoring | Only in external API | mays-jobsearch |
| Ranking | External only | mays-jobsearch |
| Multi-skill | Treated as string | N/A |

## Open Questions

1. **Integration Gaps** - What matching fields does mays-jobsearch expect that aren't in our Job model?
2. **API Consistency** - Should we add a dedicated matching endpoint?
3. **Fallback Strategy** - What happens when ATS API is unavailable?

## Limitations

1. **Cannot verify external implementation** - mays-jobsearch is not accessible
2. **No direct matching tests** - Only HTTP proxy tests exist
3. **Documentation gaps** - Match criteria not fully documented

## Recommended Next Steps

1. **BOUNDARY-CONTRACT-01** - Define explicit API contract with mays-jobsearch for matching
2. **MATCH-TEST-01** - Add tests for matching integration (even if just proxy tests)
3. **MATCH-FALLBACK-01** - Define behavior for ATS API unavailability
4. **CAPABILITY match.evaluate** - Either implement or document as external-only

---

## Git State

- Repository: Mays-Recruiting-Intelligence-System
- Branch: main
- HEAD: Current
- Note: This is an audit, NO code changes

## Conclusion

**MATCHING IS NOT IMPLEMENTED** in this repository. It is entirely delegated to the external `mays-jobsearch` repository via HTTP API.

The `match.evaluate` capability in the processing chain is a **placeholder** with no actual implementation.

For any matching functionality enhancements, work would need to happen in the `mays-jobsearch` repository or through defining a proper contract between the two.