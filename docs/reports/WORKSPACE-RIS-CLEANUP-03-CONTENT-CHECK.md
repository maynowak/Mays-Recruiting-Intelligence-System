# WORKSPACE-RIS-CLEANUP-03 — Content Safety Check

**Status:** COMPLETE - Read-only Analysis Only

## Overview

Analysis of four RIS-related directories to determine which contain unique content for potential cleanup.

---

## Directories Analyzed

| Directory | Git Status | Files | Status |
|-----------|------------|-------|--------|
| `Mays-Recruiting-Intelligent-System` | NO .git | 2 | PARTIAL |
| `Mays-Recruiting-Intelligencystem` | NO .git | 2 | PARTIAL |
| `Mays-Recruiting-Intelligent-System` | ✅ YES - .git | ~200+ | **ACTIVE** |
| `Mays-Recruiting-Intelligent-System-oldnew` | NO .git | 1 | ARCHIVE |

---

## ACTIVE Repository: `Mays-Recruiting-Intelligent-System`

**Status:** AUTHORITATIVE GIT REPOSITORY

- ✅ Has `.git` directory
- Remote: `git@github.com:maynowak/Mays-Recruiting-Intelligent-System.git`
- Branch: `main`
- HEAD: `2a440a9 feat: add dependency and contract change checker`
- Untracked: 9 files (new implementations)

This is the **only true Git repository** among the four directory variants.

---

## INACTIVE 1: `Mays-Recruiting-Intelligence-System` (lowercase 't')

**Classification:** DUPLICATE (ORPHANED/PARTIAL)

**Files:**
```
docs/RUNTIME_REGISTRY_INTEGRATION.md
```

**Analysis:**
- Only 1 file
- No `.git` directory
- File appears to be a partial copy or remnant from old work

**Comparison with ACTIVE:**
- Same document may exist at `docs/reports/RUNTIME_REGISTRY_INTEGRATION.md`
- **NOT UNIQUE** - already in active repo

**SAFE_TO_REMOVE:** ✅ YES

---

## INACTIVE 2: `Mays-Recruiting-Intelligencystem` (typo)

**Classification:** PARTIAL / UNIQUE_WORK UNCERTAIN

**Files:**
```
jobsearch/repository.py (7433 bytes, md5: e265b0a77c1b68d4674e6172efc9f4f5)
jobsearch/domain_models.py (8511 bytes, md5: 0b4164a255ac621c147ab5d58f30dc7e)
```

**Analysis:**
- Contains 2 JobSearch module files
- Files have **DIFFERENT** MD5 hashes from ACTIVE repository
- Different file sizes and timestamps
- **POSSIBLY UNIQUE WORK** - needs manual review

**Comparison with ACTIVE:**
```
ACTIVE:   repository.py = 7220 bytes, md5: 13f7fb7f5394230823d21f29c2f17b1e
INACTIVE: repository.py = 7433 bytes, md5: e265b0a77c1b68d4674e6172efc9f4f5

ACTIVE:   domain_models.py = 8562 bytes, md5: 89ebfd020384471764fca54db0115942
INACTIVE: domain_models.py = 8511 bytes, md5: 0b4164a255ac621c147ab5d58f30dc7e
```

**SAFE_TO_REMOVE:** ❌ NO - Content differs, may contain unique work

**RECOMMENDATION:** Compare file diffs manually before removal

---

## INACTIVE 3: `Mays-Recruiting-Intelligent-System-oldnew`

**Classification:** ARCHIVE/SNAPSHOT

**Files:**
```
docs/reports/S2-16-IAM-DEPLOYMENT-GOVERNANCE.md
```

**Analysis:**
- Contains dated documentation
- File also exists in ACTIVE repository at same path
- Same size (8282 bytes) but different driving

**Comparison with ACTIVE:**
```
ACTIVE:   docs/reports/S2-16-IAM-DEPLOYMENT-GOVERNANCE.md
INACTIVE: docs/reports/S2-16-IAM-DEPLOYMENT-GOVERNANCE.md
```

**Content Status:** Unclear if identical - needs diff review

**SAFE_TO_REMOVE:** ⚠️ UNCERTAIN - Need to check if content matches

---

## Summary Table

| Directory | Git | Unique Content | Safe to Remove |
|-----------|-----|----------------|----------------|
| `M-Intelligence-System` (lowercase t) | NO | Single file in active repo | ✅ YES |
| `M-Intelligencystem` (typo) | NO | Different code files | ⚠️ REVIEW |
| `M-Intelligent-System` (ACTIVE) | ✅ | N/A | N/A |
| `M-Intelligent-System-oldnew` | NO | May duplicate active | ⚠️ REVIEW |

---

## Files Requiring Manual Review

### 1. `jobsearch/repository.py` (INACTIVE 2)
- Different from active version
- May contain experimental work
- Check git history or diff for changes

### 2. `jobsearch/domain_models.py` (INACTIVE 2)
- Different from active version
- May contain work-in-progress
- Check git history or diff for changes

### 3. `docs/reports/S2-16-IAM-DEPLOYMENT-GOVERNANCE.md` (INACTIVE 3)
- Verify content matches active version
- If identical, safe to remove

---

## Recommendation

**PHASE 1 - REMOVE:**
- `Mays-Recruiting-Intelligence-System` (lowercase 't') - Orphaned, no unique content

**PHASE 2 - REVIEW:**
- `Mays-Recruiting-Intelligencystem` - Review jobsearch files for unique work
- `Mays-Recruiting-Intelligent-System-oldnew` - Review doc for duplication

**PHASE 3 - KEEP:**
- `Mays-Recruiting-Intelligent-System` - Active repository

---

## Hard Stop

**NO FILES WERE MODIFIED**
- No deletions
- No moves
- No renames
- No git operations
- No commits

---

**Next Step:** Manual review of flagged files before cleanup decisions.