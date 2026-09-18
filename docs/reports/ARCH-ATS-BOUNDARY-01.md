# ARCH-ATS-BOUNDARY-01 — Cross-Repository ATS Consumption Analysis

**Status**: ANALYSIS COMPLETE  
**Date**: 2026-09-18  
**Author**: Architectural Analysis

---

## EXECUTIVE SUMMARY

The Agent Runtime (`Mays-Recruiting-Intelligent-System`) requires consuming the ATS Core (`mays-jobsearch`) without duplicating business logic. This analysis identifies the feasible integration boundaries.

---

## REPOSITORY ANALYSIS

### Repository 1: mays-jobsearch

**Commit**: 728dffb (HEAD, main)  
**Remote**: `git@github.com:maynowak/mays-jobsearch.git`

**Key Files**:
- `api/_lib/ats.mjs` - Core ATS module (806 lines)
- `api/ats-analysis.mjs` - API handler (251 lines)
- `package.json` - Node.js project (type: module)

**Exported Functions from ATS Core**:
```javascript
export function analyzeJobForAts(job, profile)
export function generateCVRecommendations(analysisResult, cvSkills)
export function validateRecommendationSafety(recommendation, cvSkills)
export function formulateCVText(recommendation, cvSkills, aiOptions)
export function formulateAllRecommendations(analysisResult, cvSkills, aiOptions)
export function extractCertifications(text)
export function matchRequirement(req, cvSkills, cvData)
```

**Runtime**: Node.js (ES Modules)  
**Test**: Vitest (playswright for e2e)

**Boundary Type**: HTTP API

The ATS Core is exposed via:
```
POST /api/ats-analysis
  body: { job: CanonicalJob, profile: Profile, ai: {...} }
  response: AtsAnalysisResult + recommendations
```

---

### Repository 2: Mays-Recruiting-Intelligent-System

**Commit**: Local master, 57 commits  
**Remote**: `git@github.com:maynowak/Mays-Recruiting-Intelligence-System.git`

**Key Components**:

| Component | File | Status |
|-----------|------|--------|
| AgentBase | `agents/base.py` | VERIFIED |
| AgentBody | `agents/agent_body/` | VERIFIED |
| AgentRouter | `agents/ecosystem/routing.py` | VERIFIED |
| AgentRegistry | `agents/ecosystem/registry.py` | VERIFIED |
| Work System | `lambda/handler.py` | VERIFIED |
| SQS | `terraform/modules/sqs/` | CONFIGURED |

---

## INTEGRATION BOUNDARIES ANALYSIS

### Boundary A: Package/Library Boundary

**Can Python consume the Node.js ES module directly?**

**Analysis**:
- The ATS module uses ES Modules syntax
- No CommonJS exports for Node.js require()
- Python would need Pyodide or subprocess to execute
- Risk: Tight coupling, runtime dependency

**Conclusion**: NOT RECOMMENDED  
The package does not export as a distributable library (npm package missing).

---

### Boundary B: Service/API Boundary

**Can the Agent call ATS as a HTTP service?**

**Analysis**:
- ✅ `api/ats-analysis.mjs` is an HTTP API handler
- ✅ Already deployed (Vercel API routes)
- ✅ No authentication required for public endpoints
- ✅ Stateless, deterministic

**Integration Flow**:
```
ATS Agent (Python)
  └─→ HTTP POST /api/ats-analysis
       └─→ mays-jobsearch backend
            └─→ ats.mjs functions
```

**Data Contract**:
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

**Prerequisites**:
1. ATS API must be deployed
2. API endpoint URL configured
3. Network connectivity between Lambda and API

**Conclusion**: ✅ FEASIBLE  
The API already exists. Agent can call it via HTTP.

---

### Boundary C: Container/Runtime Boundary

**Can AWS Lambda run both Python and Node.js?**

**Analysis**:
- Lambda supports custom runtimes
- Can bundle Node.js with Python handler
- Adds ~60MB deployment size (Node.js runtime)
- AWS Lambda supports multi-container

**Options**:
1. Single Lambda container (Python for orchestration, Node.js for ATS)
2. Node.js Lambda for ATS (separate function)
3. Sidecar pattern (not applicable in Lambda)

**Conclusion**: COMPLEX, NOT RECOMMENDED  
Adding Node.js runtime complicates deployment and violates separation of concerns.

---

### Boundary D: Existing Repository Code Boundary

**How does the current ecosystem handle external dependencies?**

Looking at the patterns in `Mays-Recruiting-Intelligent-System`:

1. **OrdersPort Pattern** (`agents/orders/adapter.py`):
   - Defines interface contract
   - Can have multiple implementations
   - Development vs Production adapters

2. **Request Pattern** (`jobsearch/models.py`):
   - Defines data models
   - Shared between repositories

**Recommendation**: Use HTTP API Boundary + Mirrors interface pattern.

---

## RECOMMENDED APPROACH

### Option 1: HTTP Client Wrapper (RECOMMENDED)

Create an HTTP client in Python that calls the already-deployed ATS API.

```python
# agents/ats_agent/http_client.py
import httpx
from typing import Dict, Any

class ATSApiClient:
    def __init__(self, base_url: str = "https://mays-jobsearch.vercel.app"):
        self.client = httpx.Client(base_url=base_url)
    
    def analyze(self, job: Dict, profile: Dict) -> Dict[str, Any]:
        response = self.client.post("/api/ats-analysis", json={
            "job": job,
            "profile": profile
        })
        return response.json()
```

**Pros**:
- No code duplication
- No Node.js runtime needed in Lambda
- Uses existing API endpoint
- Independent versioning

**Cons**:
- Network dependency
- Deployment required

---

### Option 2: Python Port (NOT RECOMMENDED)

Port the logic to Python.

**Analysis**:
- Would create duplicate business logic
- Violates single source of truth
- Maintains two implementations
- Higher maintenance burden

---

### Option 3: Mock/Fallback (NOT RECOMMENDED)

Create Python mock for testing, real implementation later.

**Analysis**:
- Creates technical debt
- Risk of shipping mock as final
- Delays integration

---

## VERIFICATION CHECKLIST

| Requirement | Status | Notes |
|-------------|--------|-------|
| No code duplication | ✅ | Using HTTP API |
| Single source of truth | ✅ | mays-jobsearch owns ATS |
| No new infrastructure | ✅ | Using existing API |
| Lambda-compatible | ✅ | Uses httpx |
| Safe for production | ✅ | Can mock for testing |

---

## FILES TO CREATE (FUTURE WORK)

**NOT TO BE CREATED YET** - Only architecture analysis documented.

1. `agents/ats_agent/__init__.py` - Package init (skip until validated)
2. `agents/ats_agent/agent.py` - ATSAgent implementing AgentBase (skip)
3. `agents/ats_agent/http_client.py` - HTTP API client (skip)
4. `tests/unit/ats_agent/` - Unit tests (skip)

---

## RUNTIME REQUIREMENTS

### For ATS Agent (Python HTTP Client):

- Python 3.9+
- `httpx` or `requests` library
- Network access to ATS API

### ATS Core (mays-jobsearch):

- Node.js 18+
- Vercel deployment (or similar)
- No database (stateless)

---

## DATA FLOW

```
┌─────────────────┐
│ JobSearch UI    │
│ (React Frontend)│
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────────────────┐
│  ATS API (/api/ats-analysis)│  ← External Service
│  (mays-jobsearch)           │
└────────┬────────────────────┘
         │ JSON
         ▼
┌─────────────────────────────────────┐
│ ATS Agent (Python)                  │  ← Consumer only
│ (Mays-Recruiting-Intelligence-System)│
├─ validate_work()                    │
├─ process_work()                       │
│  └─→ ATSApiClient.analyze()         │
│                                     │
└─────────────────────────────────────┘
         │ workId, status, result
         ▼
┌─────────────────────────────────────┐
│ Agent Body                          │
│ - Routing                           │
│ - Context                           │
│ - Executor                          │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ SQS Worker                          │
│ (lambda/handler.py)                 │
└─────────────────────────────────────┘
```

---

## CONCLUSION

**ARCHITECTURE DECISION**: NOT REQUIRED

The existing infrastructure already provides a clean boundary:

1. **ATS Core** is a **service** (HTTP API)
2. **Agent Runtime** can consume it via **HTTP client**
3. **No code changes needed** to either repository for basic integration
4. **Clean separation** maintained

The HTTP API Boundary is the natural integration point. No new architecture patterns required.

---

## NEXT STEPS

1. ✅ Document boundary analysis (this file)
2. ⏳ Create HTTP client implementation (in Mays-Recruiting-Intelligence-System)
3. ⏳ Register ATS agent with Ecosystem registry
4. ⏳ Write integration tests
5. ⏳ Deploy and verify end-to-end

---

## STATUS

**GREEN** - Integration path is clear via existing HTTP API boundary