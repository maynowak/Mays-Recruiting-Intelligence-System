"""Internal partner boundary for the RIS analysis agent.

The analysis agent is a dedicated internal partner. The caller partner, the
executing agent and the CV owner are three distinct identities:

- caller: verified from the runtime context (never from the request body),
- executor: fixed internal partner ``ris-internal`` / ``ris-internal-analysis``,
- CV owner: the authenticated user; a CV may only be used by its owner.

No shared agent-transport policy is involved. Cross-partner and cross-tenant
access fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from agents.analysis.contracts import ContractError, Identity

INTERNAL_PARTNER_ID = "ris-internal"
INTERNAL_APPLICATION_ID = "ris-internal-analysis"
INTERNAL_AGENT_ID = "analysis-agent"
INTERNAL_PARTNER_VERSION = "1.0.0"


@dataclass(frozen=True)
class InternalPartner:
    partner_id: str = INTERNAL_PARTNER_ID
    application_id: str = INTERNAL_APPLICATION_ID
    agent_id: str = INTERNAL_AGENT_ID
    version: str = INTERNAL_PARTNER_VERSION


INTERNAL_ANALYSIS = InternalPartner()


def assert_internal_partner(request: Dict[str, Any], identity: Identity) -> None:
    """Reject a caller-claimed partner that is not the internal partner."""
    claimed = request.get("partnerId")
    if claimed is not None and str(claimed) != INTERNAL_PARTNER_ID:
        raise ContractError("partner_mismatch",
                            "the analysis agent is an internal RIS partner only")
    caller = getattr(identity, "caller_partner_id", None)
    if caller is not None and str(caller) != INTERNAL_PARTNER_ID:
        raise ContractError("partner_mismatch",
                            "caller partner is not authorized for analysis")
    if not identity.tenant_id or not identity.user_id:
        raise ContractError("missing_identity",
                            "tenant and user are required for analysis")


def assert_cv_owner(identity: Identity,
                    cv_owner_user_id: Optional[str],
                    cv_tenant_id: Optional[str]) -> None:
    """A CV is owner-only; tenant and user must both match."""
    if not cv_owner_user_id or not cv_tenant_id:
        raise ContractError("cv_owner_unknown",
                            "CV owner and tenant must be resolvable")
    if cv_tenant_id != identity.tenant_id:
        raise ContractError("cv_tenant_mismatch",
                            "CV belongs to another tenant")
    if cv_owner_user_id != identity.user_id:
        raise ContractError("cv_owner_mismatch",
                            "CV belongs to another user")


__all__ = [
    "INTERNAL_ANALYSIS",
    "INTERNAL_AGENT_ID",
    "INTERNAL_APPLICATION_ID",
    "INTERNAL_PARTNER_ID",
    "INTERNAL_PARTNER_VERSION",
    "InternalPartner",
    "assert_cv_owner",
    "assert_internal_partner",
]
