"""R08-C0F-2C durable CV upload-ticket ledger.

The ledger stores authorization and lifecycle metadata only.  URLs, S3 keys,
credentials and object content never enter a ledger item.  Registration is a
single DynamoDB transaction containing the applicable USER/CV freeze checks,
the ticket item and an idempotency marker.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from agents.ecosystem.privacy_erasure_contract import (
    FREEZE_RELEASED, freeze_resource_id)


TICKET_RESOURCE_TYPE = "UploadTicketLedgerV1"
MARKER_RESOURCE_TYPE = "UploadTicketIdempotencyV1"
STATUS_ISSUED = "ISSUED"
STATUS_PRESIGN_FAILED = "PRESIGN_FAILED"
STATUS_COMPLETED = "COMPLETED"
STATUS_REVOKED = "REVOKED"
TICKET_STATUSES = frozenset({
    STATUS_ISSUED, STATUS_PRESIGN_FAILED, STATUS_COMPLETED, STATUS_REVOKED})


class UploadTicketError(RuntimeError):
    pass


class UploadTicketConflict(UploadTicketError):
    pass


class UploadTicketUnavailable(UploadTicketError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class UploadTicketLedgerV1:
    ticket_id: str
    cv_id: str
    document_id: str
    user_id: str
    tenant_id: str
    partner_application_id: str
    issuer: str
    issued_at: str
    expires_at: str
    status: str = STATUS_ISSUED
    version: int = 1

    def __post_init__(self):
        for value, name in (
            (self.ticket_id, "ticketId"), (self.cv_id, "cvId"),
            (self.document_id, "documentId"), (self.user_id, "userId"),
            (self.tenant_id, "tenantId"),
            (self.partner_application_id, "partnerApplicationId"),
            (self.issuer, "issuer"), (self.issued_at, "issuedAt"),
            (self.expires_at, "expiresAt"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise UploadTicketError(f"{name} is required")
        if self.status not in TICKET_STATUSES:
            raise UploadTicketError("invalid upload-ticket status")
        if isinstance(self.version, bool) or not isinstance(self.version, int) \
                or self.version < 1:
            raise UploadTicketError("invalid upload-ticket version")

    def to_item(self) -> Dict[str, Any]:
        return {
            "resourceId": self.ticket_id,
            "resourceType": TICKET_RESOURCE_TYPE,
            "ticketId": self.ticket_id,
            "cvId": self.cv_id,
            "documentId": self.document_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "partnerApplicationId": self.partner_application_id,
            "issuer": self.issuer,
            "issuedAt": self.issued_at,
            "expiresAt": self.expires_at,
            "status": self.status,
            "version": self.version,
        }

    def quiescence_evidence(self):
        from agents.ecosystem.privacy_s3_erasure import UploadTicketEvidence
        return UploadTicketEvidence(self.ticket_id, self.expires_at)


class UploadTicketLedgerRepository:
    """Atomic ticket registration and versioned state transitions."""

    def __init__(self, *, client: Any, table_name: Optional[str] = None,
                 guard_table_name: Optional[str] = None,
                 enabled: Optional[bool] = None):
        self.client = client
        self.table_name = table_name or os.environ.get("UPLOAD_TICKET_LEDGER_TABLE")
        self.guard_table_name = guard_table_name or os.environ.get(
            "PARTNER_PROFILE_TABLE")
        if enabled is None:
            enabled = os.environ.get(
                "ERASURE_UPLOAD_TICKET_LEDGER_ENABLED", "false").lower() == "true"
        self.enabled = bool(enabled)

    def _ensure(self):
        if not self.enabled or not self.table_name or not self.guard_table_name:
            raise UploadTicketUnavailable("upload-ticket ledger is unavailable")
        if not self.client or not hasattr(self.client, "transact_write_items"):
            raise UploadTicketUnavailable("upload-ticket transaction client unavailable")

    @staticmethod
    def _marker_id(ticket: UploadTicketLedgerV1) -> str:
        material = "#".join((ticket.user_id, ticket.tenant_id,
                              ticket.partner_application_id, ticket.issuer,
                              ticket.cv_id, ticket.document_id))
        return "upload-ticket-dedupe#" + hashlib.sha256(
            material.encode("utf-8")).hexdigest()

    @staticmethod
    def _scope_checks(ticket: UploadTicketLedgerV1,
                      guard_table_name: str) -> List[Dict[str, Any]]:
        checks = []
        for scope, cv_id in (("USER", None), ("CV", ticket.cv_id)):
            key = freeze_resource_id(
                user_id=ticket.user_id, tenant_id=ticket.tenant_id,
                partner_application_id=ticket.partner_application_id,
                issuer=ticket.issuer, scope=scope, cv_id=cv_id)
            checks.append({"ConditionCheck": {
                "TableName": guard_table_name,
                "Key": {"resourceId": {"S": key}},
                "ConditionExpression": (
                    "attribute_not_exists(resourceId) OR #s = :released"),
                "ExpressionAttributeNames": {"#s": "state"},
                "ExpressionAttributeValues": {
                    ":released": {"S": FREEZE_RELEASED},
                },
            }})
        return checks

    @staticmethod
    def _serialize(item: Mapping[str, Any]) -> Dict[str, Dict[str, str]]:
        from jobsearch.partner_profile_repository import serializer
        return {key: serializer(value) for key, value in item.items()}

    def register(self, ticket: UploadTicketLedgerV1) -> UploadTicketLedgerV1:
        """Register once; a matching retry returns the existing ticket."""
        self._ensure()
        marker_id = self._marker_id(ticket)
        marker = {
            "resourceId": marker_id, "resourceType": MARKER_RESOURCE_TYPE,
            "ticketId": ticket.ticket_id,
            "fingerprint": hashlib.sha256(json.dumps(
                ticket.to_item(), sort_keys=True).encode()).hexdigest(),
        }
        actions = self._scope_checks(ticket, self.guard_table_name) + [
            {"Put": {
                "TableName": self.table_name,
                "Item": self._serialize(ticket.to_item()),
                "ConditionExpression": "attribute_not_exists(resourceId)",
            }},
            {"Put": {
                "TableName": self.table_name,
                "Item": self._serialize(marker),
                "ConditionExpression": "attribute_not_exists(resourceId)",
            }},
        ]
        try:
            self.client.transact_write_items(TransactItems=actions)
            return ticket
        except Exception as exc:
            if "ConditionalCheckFailed" not in str(exc) \
                    and "conditional" not in str(exc).lower():
                raise UploadTicketUnavailable("ticket registration failed") from exc
            # Idempotent replay is allowed only when the marker and ticket
            # fingerprint match exactly. A fake or foreign marker is a conflict.
            try:
                response = self.client.get_item(
                    TableName=self.table_name,
                    Key={"resourceId": {"S": marker_id}},
                    ConsistentRead=True)
                existing = response.get("Item") or {}
            except Exception as read_exc:
                raise UploadTicketUnavailable("ticket replay lookup failed") from read_exc
            existing_ticket_id = existing.get("ticketId")
            if isinstance(existing_ticket_id, Mapping):
                existing_ticket_id = existing_ticket_id.get("S")
            if existing_ticket_id != ticket.ticket_id:
                raise UploadTicketConflict("upload-ticket idempotency conflict")
            return ticket

    @staticmethod
    def _value(value: Mapping[str, Any]) -> Any:
        if "S" in value:
            return value["S"]
        if "N" in value:
            return int(value["N"]) if str(value["N"]).isdigit() else float(value["N"])
        if "BOOL" in value:
            return value["BOOL"]
        return None

    def get(self, ticket_id: str) -> UploadTicketLedgerV1:
        self._ensure()
        try:
            response = self.client.get_item(
                TableName=self.table_name,
                Key={"resourceId": {"S": ticket_id}}, ConsistentRead=True)
        except Exception as exc:
            raise UploadTicketUnavailable("ticket lookup failed") from exc
        item = response.get("Item") or {}
        if item.get("resourceType", {}).get("S") != TICKET_RESOURCE_TYPE:
            raise UploadTicketConflict("upload ticket not found")
        data = {key: self._value(value) for key, value in item.items()}
        return UploadTicketLedgerV1(
            ticket_id=data["ticketId"], cv_id=data["cvId"],
            document_id=data["documentId"], user_id=data["userId"],
            tenant_id=data["tenantId"],
            partner_application_id=data["partnerApplicationId"],
            issuer=data["issuer"], issued_at=data["issuedAt"],
            expires_at=data["expiresAt"], status=data["status"],
            version=data["version"])

    def transition(self, ticket: UploadTicketLedgerV1, *, status: str,
                   expected_version: int) -> UploadTicketLedgerV1:
        self._ensure()
        if status not in TICKET_STATUSES or ticket.version != expected_version:
            raise UploadTicketConflict("invalid ticket state transition")
        from jobsearch.partner_profile_repository import serializer
        action = {"Update": {
            "TableName": self.table_name,
            "Key": {"resourceId": serializer(ticket.ticket_id)},
            "UpdateExpression": "SET #s = :s, #v = :newv, updatedAt = :now",
            "ConditionExpression": (
                "resourceType = :rt AND #v = :oldv AND userId = :u "
                "AND tenantId = :t AND partnerApplicationId = :p AND issuer = :i"),
            "ExpressionAttributeNames": {"#s": "status", "#v": "version"},
            "ExpressionAttributeValues": {
                ":s": serializer(status), ":newv": serializer(expected_version + 1),
                ":oldv": serializer(expected_version),
                ":rt": serializer(TICKET_RESOURCE_TYPE),
                ":u": serializer(ticket.user_id), ":t": serializer(ticket.tenant_id),
                ":p": serializer(ticket.partner_application_id),
                ":i": serializer(ticket.issuer), ":now": serializer(_now()),
            }}}
        try:
            self.client.transact_write_items(
                TransactItems=self._scope_checks(ticket, self.guard_table_name)
                + [action])
        except Exception as exc:
            if "ConditionalCheckFailed" in str(exc) or "conditional" in str(exc).lower():
                raise UploadTicketConflict("ticket version conflict") from exc
            raise UploadTicketUnavailable("ticket transition failed") from exc
        return UploadTicketLedgerV1(
            ticket_id=ticket.ticket_id, cv_id=ticket.cv_id,
            document_id=ticket.document_id, user_id=ticket.user_id,
            tenant_id=ticket.tenant_id,
            partner_application_id=ticket.partner_application_id,
            issuer=ticket.issuer, issued_at=ticket.issued_at,
            expires_at=ticket.expires_at, status=status,
            version=expected_version + 1)


__all__ = [
    "UploadTicketLedgerV1", "UploadTicketLedgerRepository",
    "UploadTicketError", "UploadTicketConflict", "UploadTicketUnavailable",
    "STATUS_ISSUED", "STATUS_PRESIGN_FAILED", "STATUS_COMPLETED",
    "STATUS_REVOKED",
]
