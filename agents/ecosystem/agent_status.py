"""
Central agent status normalization (fail-closed).

Contract: P6-R6 / Gate RIS-AGENT-STATUS-NORMALIZATION-07.

Executable: ONLY AgentStatus.ACTIVE. Every other known status is
blocked. Unknown / None / empty / malformed values are blocked
(returned as None) — never defaulted to ACTIVE.

This module is the single status-decision boundary. All execution
paths (catalog adapter, eligibility, handler gates, discovery
consumers) must use it instead of local string comparisons.

BLOCKED is a decision result (None), NOT a persisted agent status.
No new persisted status class is introduced here.
"""

from typing import Any, Optional

from agents.ecosystem.registry import AgentStatus


def normalize_agent_status(raw: Any) -> Optional[AgentStatus]:
    """Map a raw status value to its canonical AgentStatus.

    Normalization: strings are stripped and uppercased before lookup.
    Returns None (= BLOCKED) for unknown, empty, None, or non-string
    values. Never defaults to ACTIVE.
    """
    if isinstance(raw, AgentStatus):
        return raw
    if not isinstance(raw, str):
        return None
    key = raw.strip().upper()
    if not key:
        return None
    try:
        return AgentStatus[key]
    except KeyError:
        return None


def is_executable_status(raw: Any) -> bool:
    """True only when the normalized status is ACTIVE.

    Accepts raw catalog values (any case/whitespace) as well as
    AgentStatus members. Everything else — including unknown,
    empty, and None values — is NOT executable (fail-closed).
    """
    if isinstance(raw, AgentStatus):
        return raw == AgentStatus.ACTIVE
    return normalize_agent_status(raw) == AgentStatus.ACTIVE
