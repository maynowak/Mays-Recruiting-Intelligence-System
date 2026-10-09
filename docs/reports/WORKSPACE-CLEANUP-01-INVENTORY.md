# WORKSPACE-CLEANUP-01 — Workspace Inventory

**Status:** INVENTORY ONLY (No modifications made)

## Executive Summary

This document provides a comprehensive inventory of the project workspace structure under `~/projects/` for consolidation planning.

---

## Current Directory Structure

```
~/projects/
├── Digital-Book-Experience/       (Git repo - DIRTY, 25 untracked)
├── Digital-Book-Experience220726/ (Backup/zip snapshot)
├── Digital-Book-Experience2.2.7/  (Backup/zip snapshot)
├── Hallo AI einführungspromt mays job matcher.txt
├── index.html
├── May-Order-Branchwork/          (Non-git work area)
├── Mays-Jobsearch/                (Git repo - DIRTY, 1 untracked)
├── Mays-Jobsearch28082026.zip     (Backup archive)
├── Mays-Jobsearch-featurework/    (Non-git work area)
├── Mays-Orders-AWS/               (Git repo - DIRTY, 6 untracked)
├── Mays-Orders-AWS02092026/      (Non-git checkout)
├── Mays-Orders-AWS180826.zip     (Backup archive)
├── Mays-Orders-AWSwithoutsqs.zip (Backup archive)
├── Mays-Providers-AWS02092026.zip (Backup archive)
├── Mays-Orders-AWS.zip           (Backup archive)
├── Mays-Recruiting-Intelligence-System/ (Git repo - DIRTY, 8 untracked)
├── Mays-Recruiting-Intelligencystem/  (Non-git partial content)
├── Mays-Recruiting-Intelligence-System-oldnew/ (Non-git partial content)
├── QA/                           (Non-git work area)
├── qa-labs/                      (Non-git work area)
├── React-Projekt-Marketing-Website/ (Git repo - DIRTY, 26 untracked)
├── teraformlesson/              (Non-git learning area)
└── version1withLoveable.txt
```

---

## Git Repository Inventory

| Repository | Remote | Branch | HEAD | Status | Untracked |
|------------|--------|--------|------|--------|-----------|
| Digital-Book-Experience | git@github.com:maynowak/digital-book-experience.git | main | 20c16df | DIRTY | 25 |
| Mays-Jobsearch | git@github.com:maynowak/mays-jobsearch.git | main | 57d96ce | DIRTY | 1 |
| Mays-Orders-AWS | git@github.com:maynowak/mays-order-aws.git | main | 181c096 | DIRTY | 6 |
| Mays-Recruiting-Intelligence-System | git@github.com:maynowak/Mays-Recruiting-Intelligent-System.git | main | 2a440a9 | DIRTY | 8 |
| React-Projekt-Marketing-Website | git@github.com:maynowak/React-Projekt-Marketing-Website.git | main | 5228a46 | DIRTY | 26 |

---

## Similar Repository Analysis

### Mays-Recruiting-Intelligence-System Variants

| Directory | Git Status | Remote | Notes |
|-----------|------------|--------|-------|
| `Mays-Recruiting-Intelligence-System/` | YES | maynowak/Mays-Recruiting-Intelligent-System | **ACTIVE** - Current repository |
| `Mays-Recruiting-Intelligencystem/` | NO | N/A | **PARTIAL** - Contains only jobsearch/ subdirectory (orphaned) |
| `Mays-Recruiting-Intelligent-System-oldnew/` | NO | N/A | **PARTIAL** - Likely old branch work |

**Analysis:** These appear to be different local copies/checkouts, NOT git worktrees. The dot-missing `Mays-Recruiting-Intelligencystem` is likely an accidental or partial checkout.

### Mays-Orders-AWS Variants

| Directory | Git Status | Remote | Notes |
|-----------|------------|--------|-------|
| `Mays-Orders-AWS/` | YES | maynowak/mays-order-aws.git | **ACTIVE** - Current repository |
| `Mays-Orders-AWS02092026/` | NO | N/A | **ARCHIVE** - Non-git, dated checkout |

**Analysis:** The dated variant may be a historical snapshot from September 2.

---

## Classification

### ACTIVE PROJECT
- `Mays-Recruiting-Intelligence-System/` - Current work repository
- `Mays-Jobsearch/` - External ATS repository
- `Mays-Orders-AWS/` - External orders repository

### ACTIVE WORKTREE
- None identified (no `.git` files found)

### INFRASTRUCTURE
- None

### BRANCH_WORK
- `May-Order-Branchwork/` - Non-git work directory
- `Mays-Jobsearch-featurework/` - Non-git feature work

### QA
- `qa-labs/` - Non-git QA work area
- `QA/` - Non-git QA work area

### ARCHIVE
- `Digital-Book-Experience220726/` - Backup
- `Digital-Book-Experience2.2.7/` - Version snapshot
- `Mays-Jobsearch28082026.zip` - Archive
- `Mays-Orders-AWS02092026/` - Dated snapshot
- `Mays-Orders-AWS180826.zip` - Archive
- `Mays-Orders-AWSwithoutsqs.zip` - Archive
- `Mays-Orders-AWS.zip` - Archive
- `Mays-Recruiting-Intelligence-System-oldnew/` - Old snapshot
- `React-Projekt-Marketing-Website.zip` - Archive

### BACKUP
- All `.zip` files in workspace

### DUPLICATE_OR_OLD_CHECKOUT
- `Mays-Recruiting-Intelligencystem/` - Incomplete/mistyped name
- `Mays-Orders-AWS02092026/` - Historical snapshot
- `Mays-Jobsearch-featurework/` - Feature branch work

### UNKNOWN
- None

---

## Target Consolidation Structure

**Desirable final structure:**

```
~/projects/
└── Mays-Recruiting-Intelligence-System/
    ├── README.md
    ├── agents/
    ├── jobsearch/
    ├── lambda/
    ├── terraform/
    ├── docs/
    ├── installer/
    │   └── source_connectivity.py (reference implementation)
    ├── tests/
    │   └── unit/agents/
    └── reports/
        ├── SHARED-CONTRACT-01.md
        ├── ENVIRONMENT-COMPATIBILITY-01.md
        └── ...
```

---

## Proposed Moves (FOR DISCUSSION ONLY)

### SAFE MOVES

| SOURCE | DESTINATION | CATEGORY | RISK | REASON |
|--------|-------------|----------|------|--------|
| `Mays-Jobsearch/` | `Mays-Recruiting-Intelligence-System/integrations/mays-jobsearch/` | SUBMODULE | LOW | External dependency, could be git submodule |
| `Mays-Orders-AWS/` | `Mays-Recruiting-Intelligence-System/integrations/mays-orders/` | SUBMODULE | LOW | External dependency, could be git submodule |

### PROBLEMATIC MOVES (DO NOT RECOMMEND WITHOUT REVIEW)

| SOURCE | ISSUE |
|--------|-------|
| `May-Order-Branchwork/` | Unknown content, non-git |
| `Mays-Recruiting-Intelligencystem/` | Incomplete, likely mistake |
| `Mays-Recruiting-Intelligent-System-oldnew/` | Unknown purpose |
| `qa-labs/`, `QA/` | Testing/QA areas |
| All `.zip` files | Binary archives, not needed |

---

## Git Security Checklist

- [ ] **Submodules**: None detected
- [ ] **Worktrees**: None detected
- [ ] **Dirty Trees**: 5 repositories have untracked changes
- [ ] **Secrets**: No sensitive files detected in `.gitignore` patterns
- [ ] **Large Files**: Several `.zip` archives present

**Recommendation:** Handle dirty/untracked files per repository's own guidelines before any consolidation.

---

## Important Notes

### For Mays-Recruiting-Intelligence-System (Current)
- This is the **active repository** with uncommitted changes
- Source connectivity framework has been implemented
- See `agents/source_connectivity.py` for the checker

### For Mays-Orders-AWS
- **VALID Git repository** with remote `maynowak/mays-order-aws.git`
- Has uncommitted changes (6 untracked files)
- Contains installer structure ready for integration
- **DO NOT** modify while another process is working on it

---

## Files NOT to Move/Modify

1. **All `.zip` files** - Binary archives, may contain important data
2. **Untracked files in active repos** - May contain work-in-progress
3. **Any `terrraformlesson`** - Learning materials
4. **Q&A directories** - Testing areas

---

## Recommendations

1. **Use git submodules** for Mays-Jobsearch and Mays-Orders-AWS in the main repo
2. **Review untracked files** in each active repo before consolidation
3. **Archive dated snapshots** to separate backup location
4. **Clean up partial checkouts** (`Mays-Recruiting-Intelligencystem`)
5. **Document untracked file purposes** before deletion consideration

---

## Open Questions

1. What is the purpose of `Mays-Recruiting-Intelligencystem/` (no 't')?
2. What work is in `May-Order-Branchwork/`?
3. What is in `Mays-Recruiting-Intelligent-System-oldnew/`?
4. Should `.zip` archives be kept or moved to backup storage?

---

## HARD STOP

**WORKSPACE CLEANUP INVENTORY COMPLETE**

- ✅ Repository structure documented
- ✅ Git status for all repos recorded
- ✅ Similar repos identified
- ✅ Classification completed
- ✅ Target structure proposed
- ✅ Safety checklist performed

**NO FILES WERE MODIFIED**

**NO COMMITS WERE MADE**

**NO AWS OPERATIONS PERFORMED**

---

**Next Step:** Wait for approval before any file movement or cleanup.