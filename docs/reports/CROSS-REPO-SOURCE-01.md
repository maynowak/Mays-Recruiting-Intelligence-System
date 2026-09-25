# CROSS-REPO-SOURCE-01 — Cross-Repository Source-of-Truth

## Executive Summary

This document establishes the canonical source for understanding cross-repository data flow and commitments between Mays-RIS and Mays-Orders-AWS.

**Repository**: Mays-Recruiting-Intelligent-System

**Remote**: git@github.com:maynowak/Mays-Recruiting-Intelligent-System.git

**Branch**: main

**Current Commit**: See git log for latest

---

## Cross-Repository Architecture

### Repository Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                    Mays-Recruiting-Intelligent-System       │
│                       (RIS Repository)                       │
│                                                               │
│  GROUND ZERO (Platform Core)                                 │
│  ├── Agent Infrastructure                                    │
│  ├── Agent Runtime (AgentBody)                               │
│  ├── Agent Ecosystem (Registry, Discovery)                   │
│  ├── OrdersPort Interface                                    │
│  └── Installer (Local Development Support)                   │
│                      │                                      │
│                      │ OrdersPort Interface                 │
│                      ▼                                      │
│          ┌───────────────────┐                             │
│          │   OrdersAdapter   │                             │
│          └────────┬──────────┘                             │
│                   │                                          │
└───────────────────┼──────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                   Mays-Orders-AWS                           │
│                    (External Repository)                    │
│                                                             │
│  Terraform managed AWS resources                            │
│  API endpoints for order processing                           │
│  CI/CD pipeline for deployments                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Source-of-Truth Commit

This repository's current state is defined by:

```
Repository: git@github.com:maynowak/Mays-Recruiting-Intelligent-System.git
Branch: main
HEAD: <current-commit-sha>
```

Use this command to verify:

```bash
git rev-parse HEAD
git remote get-url origin
git rev-parse origin/main
```

### Source Path Verification

Before any cross-repo integration, verify:

1. **Repository URL**: Must match `git@github.com:maynowak/Mays-Recruiting-Intelligent-System.git`
2. **Branch**: Must be `main`
3. **HEAD Commit**: Use SHA, not branch name, for reproducibility
4. **Clean State**: No uncommitted changes that affect integration

---

## Cross-Repo Integration Contracts

### 1. OrdersPort Interface

The OrdersPort is the canonical integration boundary:

```python
# orders_port interface (in orders_port.py)
class OrdersPort:
    def get_order(order_id: str) -> Order: ...
    def create_order(data: dict) -> Order: ...
    def update_order(order_id: str, data: dict) -> Order: ...
    def list_orders(filters: dict) -> List[Order]: ...
```

### 2. DevelopmentOrdersAdapter

Implemented in RIS for local testing:

- Implements OrdersPort interface
- Simulates external system behavior
- Used in dry-run mode for testing

### 3. Cross-Repo Validation

When integrating with Mays-Orders-AWS:

1. Verify repository identity (remote URL + commit SHA)
2. Verify branch is correct (`main`)
3. Verify working tree is clean
4. Use adapter pattern for loose coupling

---

## Validator: Repository Identity Check

Before using repository commits in production:

```python
def validate_repository_state(repo_path: Path) -> Dict[str, str]:
    """
    Validate repository is at expected state.

    Returns:
        {
            "remote": "git@github.com:...",
            "branch": "main",
            "commit": "abc123...",
            "is_clean": true
        }
    """
```

---

## Current Implementation Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| INSTALLER-LOCAL-INTEGRATION-01 | ✅ Complete | Local installer framework |
| SOURCE-CONNECTIVITY-01 | ✅ Complete | Source connectivity checks |
| ENVIRONMENT-COMPATIBILITY-01 | ✅ Complete | Environment validation |
| CROSS-REPO-SOURCE-01 | ✅ Complete | This document |

---

## Test Verification

All cross-repo tests pass:

```bash
python3 -m pytest tests/unit/agents/test_source_connectivity.py -v
python3 -m pytest tests/unit/agents/test_environment_compat.py -v
```

---

## References

- INSTALLER-LOCAL-INTEGRATION-01.md
- SOURCE-CONNECTIVITY-GATE-01.md
- SOURCE-CONNECTIVITY-GATE-02-INTEGRATION-GUIDE.md
- ENVIRONMENT-COMPATIBILITY-01.md
