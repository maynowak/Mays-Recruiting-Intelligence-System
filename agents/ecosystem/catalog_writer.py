"""
Agent Catalog Writer

Persists a runtime AgentDescriptor into the existing persistent DynamoDB
agent_catalog table.

Architecture boundary (Gate 04, unchanged):
    runtime AgentRegistry  ──explicit call──>  CatalogWriter  ──>  DynamoDB agent_catalog

This module is the *only* write side for the persistent catalog. It is
never invoked implicitly: nothing in the runtime path persists the
registry. `CatalogAdapter` (read side) and this writer are separate on
purpose, and the writer holds no reference to an `AgentRegistry`.

Schema (existing, NOT invented here):
    terraform/modules/dynamodb/main.tf:87-114 declares exactly
    agentId (hash, S) + status (GSI gsi-status, S) + TTL on
    `expiresAt`. Attribute names below are the ones the EXISTING read
    path already consumes:
      lambda/handler.py:42-88  (_init_catalog, live coldstart)
      agents/ecosystem/catalog_adapter.py:165  (_convert_to_descriptor)
    Both read: agentId, status, name, version, capabilities,
    supported_bodies, supported_runtimes, risk_level, description,
    metadata.

Status convention (existing, reused — never a second decision):
    agents/ecosystem/agent_status.py — unknown/empty/None normalises to
    None = blocked. The writer rejects such a value instead of writing a
    row no reader would accept.

No secrets, tokens, credentials or personal data are accepted here: the
field allowlist below is closed, so an unexpected key is a hard error
rather than a silent write.
"""

from typing import Any, Dict, Iterable, List, Optional

from agents.ecosystem.agent_status import normalize_agent_status
from agents.ecosystem.registry import AgentDescriptor


class CatalogWriteError(RuntimeError):
    """Raised when a catalog entry cannot be persisted.

    The writer never swallows a store failure: a caller must not be able
    to mistake "not written" for "written".
    """


class CatalogEntryInvalid(CatalogWriteError):
    """Raised when the entry violates the existing catalog contract."""


#: Closed allowlist of persistable attributes. Every name is read by the
#: existing read path or declared in the Terraform table definition.
#: `expiresAt` is deliberately absent: the table TTL is enabled on it, so
#: writing it would silently expire a provisioned entry. Retention is a
#: separate gate (Discovery-07 finding) — this module does not invent a
#: retention policy.
WRITABLE_FIELDS = (
    "agentId",
    "status",
    "name",
    "version",
    "description",
    "capabilities",
    "supported_bodies",
    "supported_runtimes",
    "risk_level",
    "metadata",
)

_REQUIRED_FIELDS = ("agentId", "status")


def catalog_item_from_descriptor(descriptor: AgentDescriptor) -> Dict[str, Any]:
    """Project a runtime AgentDescriptor onto the existing catalog shape.

    The projection is explicit (no generic ``asdict``): it guarantees the
    written item is exactly the data form the read path consumes, and
    that nothing unexpected (secrets, tokens) can ride along.
    """
    if not isinstance(descriptor, AgentDescriptor):
        raise CatalogEntryInvalid(
            f"expected AgentDescriptor, got {type(descriptor).__name__}")

    status = normalize_agent_status(descriptor.status)
    if status is None:
        raise CatalogEntryInvalid(
            f"agent {descriptor.agent_id!r}: unsupported status "
            f"{descriptor.status!r} (fail-closed, existing convention)")

    return {
        "agentId": descriptor.agent_id,
        "status": status.value,
        "name": descriptor.name or descriptor.agent_id,
        "version": descriptor.version or "1.0.0",
        "description": descriptor.description or "",
        "capabilities": list(descriptor.capabilities or []),
        "supported_bodies": list(descriptor.supported_bodies or ["1.0.0"]),
        "supported_runtimes": list(descriptor.supported_runtimes or ["python3.14"]),
        "risk_level": descriptor.risk_level or "low",
        "metadata": dict(descriptor.metadata or {}),
    }


def validate_catalog_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a raw catalog item against the existing contract.

    Returns a normalised copy (status via the existing fail-closed
    normaliser) or raises. Rejects unknown keys so a future refactor
    cannot quietly widen what lands in the table.
    """
    if not isinstance(item, dict):
        raise CatalogEntryInvalid(f"expected dict, got {type(item).__name__}")

    unknown = sorted(set(item) - set(WRITABLE_FIELDS))
    if unknown:
        raise CatalogEntryInvalid(f"unknown catalog attribute(s): {unknown}")

    missing = [f for f in _REQUIRED_FIELDS if not item.get(f)]
    if missing:
        raise CatalogEntryInvalid(f"missing required field(s): {missing}")

    status = normalize_agent_status(item["status"])
    if status is None:
        raise CatalogEntryInvalid(
            f"agent {item['agentId']!r}: unsupported status "
            f"{item['status']!r} (fail-closed, existing convention)")

    for field in ("capabilities", "supported_bodies", "supported_runtimes"):
        value = item.get(field, [])
        if not isinstance(value, (list, tuple)):
            raise CatalogEntryInvalid(
                f"agent {item['agentId']!r}: {field} must be a list")
        if any(not isinstance(entry, str) for entry in value):
            raise CatalogEntryInvalid(
                f"agent {item['agentId']!r}: {field} must contain strings only")

    metadata = item.get("metadata", {})
    if not isinstance(metadata, dict):
        raise CatalogEntryInvalid(
            f"agent {item['agentId']!r}: metadata must be a map")

    normalised = dict(item)
    normalised["status"] = status.value
    for field in ("capabilities", "supported_bodies", "supported_runtimes"):
        normalised[field] = list(normalised.get(field, []))
    normalised["metadata"] = dict(metadata)
    return normalised


class CatalogWriter:
    """Explicit writer for the persistent agent_catalog table.

    Idempotency: `agentId` is the table hash key, so writing the same
    agent twice replaces the row in place — no duplicate accumulates.
    Nothing here touches the runtime `AgentRegistry`.
    """

    def __init__(self, table_name: Optional[str] = None, dynamodb=None):
        self.table_name = table_name or _table_name_from_env()
        self._dynamodb = dynamodb
        self._table = None

    @property
    def table(self):
        if self._table is None:
            if not self.table_name:
                raise CatalogWriteError(
                    "agent catalog table not configured "
                    "(pass table_name or set AGENT_CATALOG_TABLE)")
            if self._dynamodb is None:
                import boto3
                self._dynamodb = boto3.resource("dynamodb")
            self._table = self._dynamodb.Table(self.table_name)
        return self._table

    def put_agent(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Persist one validated catalog entry. Returns the written item.

        Idempotent by schema (hash key `agentId`). Raises on any store
        failure — never returns a success-looking result for a failed
        write.
        """
        validated = validate_catalog_item(item)
        try:
            self.table.put_item(Item=validated)
        except CatalogWriteError:
            raise
        except Exception as exc:
            raise CatalogWriteError(
                f"failed to persist catalog entry "
                f"{validated['agentId']!r}: {type(exc).__name__}: {exc}"
            ) from exc
        return validated

    def put_descriptor(self, descriptor: AgentDescriptor) -> Dict[str, Any]:
        """Persist a runtime descriptor via the explicit projection."""
        return self.put_agent(catalog_item_from_descriptor(descriptor))

    def put_descriptors(self, descriptors: Iterable[AgentDescriptor]
                        ) -> List[Dict[str, Any]]:
        return [self.put_descriptor(d) for d in descriptors]


def _table_name_from_env() -> Optional[str]:
    import os
    return os.environ.get("AGENT_CATALOG_TABLE")


__all__ = [
    "CatalogWriteError",
    "CatalogEntryInvalid",
    "CatalogWriter",
    "catalog_item_from_descriptor",
    "validate_catalog_item",
    "WRITABLE_FIELDS",
]
