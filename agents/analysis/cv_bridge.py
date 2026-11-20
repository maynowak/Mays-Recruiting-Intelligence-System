"""RIS CV storage bridge: resolve an authorized CV into parser input.

Only server-side references are accepted. Structured CV data is reused as-is;
a PDF is fetched from the existing RIS documents bucket and forwarded to the
Node parser. No CV content is logged, and no CV bytes travel in WorkItems.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from agents.analysis.contracts import ContractError


@dataclass(frozen=True)
class CvInput:
    structured: Optional[Dict[str, Any]]
    pdf_base64: Optional[str]
    sha256: Optional[str]
    source: str

    @property
    def is_structured(self) -> bool:
        return self.structured is not None


DocumentLoader = Callable[[str, str, str], bytes]


class CvResolver:
    def resolve(self, cv: Dict[str, Any], identity: Any) -> CvInput:
        raise NotImplementedError


class RequestCvResolver(CvResolver):
    """Uses structured data from the request or a server-side RIS CV reference."""

    def __init__(self, document_loader: Optional[DocumentLoader] = None,
                 repository: Any = None):
        self._document_loader = document_loader
        self._repository = repository

    def resolve(self, cv: Dict[str, Any], identity: Any) -> CvInput:
        structured = cv.get("structured")
        if isinstance(structured, dict):
            if not isinstance(structured.get("skills"), list):
                raise ContractError("invalid_cv", "structured CV needs skills[]")
            return CvInput(structured=structured, pdf_base64=None,
                           sha256=hashlib.sha256(
                               repr(sorted(structured.items())).encode("utf-8")
                           ).hexdigest(),
                           source="structured")
        cv_id = cv.get("cvId")
        if not cv_id:
            raise ContractError("missing_cv", "cvId or structured CV is required")
        return self._resolve_stored(str(cv_id), identity)

    def _repo(self):
        if self._repository is None:
            from jobsearch.partner_profile_repository import (
                PartnerProfileRepository,
            )

            self._repository = PartnerProfileRepository()
        return self._repository

    def _load(self, tenant_id: str, user_id: str, doc_id: str) -> bytes:
        if self._document_loader is not None:
            return self._document_loader(tenant_id, user_id, doc_id)
        import os
        import re

        import boto3

        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", doc_id or ""):
            raise ValueError("invalid document id")
        bucket = os.environ.get("DOCUMENTS_BUCKET")
        if not bucket:
            raise RuntimeError("DOCUMENTS_BUCKET is not configured")
        key = f"tenant/{tenant_id}/users/{user_id}/documents/{doc_id}"
        obj = boto3.client("s3").get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()

    def _resolve_stored(self, cv_id: str, identity: Any) -> CvInput:
        tenant = getattr(identity, "tenant_id", "") or ""
        user = getattr(identity, "user_id", "") or ""
        if not tenant or not user:
            raise ContractError("cv_access_denied", "tenant and user are required")
        try:
            record = self._repo().get(
                cv_id, user, tenant,
                getattr(identity, "partner_application_id", None),
                getattr(identity, "issuer", None))
        except Exception as exc:  # noqa: BLE001 - storage boundary
            raise ContractError("cv_not_accessible", "CV cannot be resolved") from exc
        if record is None:
            raise ContractError("cv_not_found", "CV not found")
        owner = getattr(record, "user_id", None) or getattr(record, "owner_user_id", None)
        rec_tenant = getattr(record, "tenant_id", None)
        if owner and owner != user:
            raise ContractError("cv_access_denied", "CV belongs to another owner")
        if rec_tenant and rec_tenant != tenant:
            raise ContractError("cv_access_denied", "CV belongs to another tenant")
        status = str(getattr(record, "processing_status", "pending") or "pending")
        if status != "ready":
            raise ContractError("cv_not_ready", "CV is not ready for parsing")
        doc_id = getattr(record, "document_id", None)
        if not doc_id:
            raise ContractError("cv_not_ready", "CV has no document")
        content_type = getattr(record, "content_type", None)
        if content_type not in (None, "application/pdf"):
            raise ContractError("cv_unsupported", "CV document is not a PDF")
        try:
            raw = self._load(tenant, user, str(doc_id))
        except ContractError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ContractError("cv_not_accessible", "CV document is not readable") from exc
        if not raw:
            raise ContractError("cv_not_ready", "CV document is empty")
        return CvInput(structured=None,
                       pdf_base64=base64.b64encode(raw).decode("ascii"),
                       sha256=hashlib.sha256(raw).hexdigest(),
                       source="ris-cv")
