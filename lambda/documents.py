#!/usr/bin/env python3
"""Secure Document Storage — Presign-Logik (Gate 14, unser Bereich).

Prinzip: Der Browser erhaelt NIE AWS-Credentials, sondern kurzlebige,
auf exakt EINEN Key begrenzte Presigned-URLs. Keys baut AUSSCHLIESSLICH
der Server aus JWT-Identitaet (sub + Tenant); Request-Werte fuer userId,
tenantId oder Key-Bestandteile werden IGNORIERT (kein Spoofing).

Key-Schema: tenant/{tenantId}/users/{userId}/documents/{docId}
(kein PII im Key; Tenant strukturell).
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

UPLOAD_EXPIRY_SECONDS = 900

ALLOWED_CONTENT_TYPES = frozenset({
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
})

_DOC_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_doc_id() -> str:
    return uuid.uuid4().hex[:16]


def build_key(tenant_id: Optional[str], user_id: str, doc_id: str) -> str:
    """Server-seitiger Key (wirft bei ungueltiger docId)."""
    if not user_id or not (tenant_id or "").strip() or not _DOC_ID_RE.match(doc_id or ""):
        raise ValueError("Ungueltige Dokument-ID")
    tenant = tenant_id.strip()
    if not _DOC_ID_RE.match(tenant):
        raise ValueError("Ungueltiger Tenant-Kontext")
    return f"tenant/{tenant}/users/{user_id}/documents/{doc_id}"


def _s3_client():
    import boto3  # Lambda-Runtime; Tests injizieren Fake

    # Regionaler Endpoint (kein 307-Redirect: Redirects invalidieren SigV4).
    region = os.environ.get("AWS_REGION", "eu-central-1")
    return boto3.client("s3", region_name=region,
                        endpoint_url=f"https://s3.{region}.amazonaws.com")


def _bucket() -> str:
    bucket = os.environ.get("DOCUMENTS_BUCKET")
    if not bucket:
        raise RuntimeError("DOCUMENTS_BUCKET nicht konfiguriert")
    return bucket


def _require_tenant(tenant_id: str, require_tenant: bool) -> None:
    """Fail closed for every public document operation.

    ``require_tenant`` remains as a compatibility argument for internal
    callers, but no path may fall back to a shared ``default`` tenant.
    """
    if not (tenant_id or "").strip():
        raise ValueError("Tenant context required")


def _expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=UPLOAD_EXPIRY_SECONDS)).isoformat()


def presign_upload(s3: Any = None, tenant_id: str = "", user_id: str = "",
                   content_type: Optional[str] = None,
                   doc_id: Optional[str] = None,
                   require_tenant: bool = False) -> Dict[str, Any]:
    """Presigned PUT for one server-owned document id.

    The S3 key is deliberately kept inside this module and is never returned
    as a public DTO. ``requiredHeaders`` must match the signed request.
    """
    _require_tenant(tenant_id, require_tenant)
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Content-Type nicht zugelassen")
    client = s3 if s3 is not None else _s3_client()
    doc_id = doc_id or new_doc_id()
    if not _DOC_ID_RE.match(doc_id or ""):
        raise ValueError("Ungueltige Dokument-ID")
    key = build_key(tenant_id, user_id, doc_id)
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket(), "Key": key, "ContentType": content_type},
        ExpiresIn=UPLOAD_EXPIRY_SECONDS,
    )
    return {"documentId": doc_id, "uploadUrl": url,
            "expiresAt": _expires_at(),
            "requiredHeaders": {"Content-Type": content_type}}


def head_document(s3: Any = None, tenant_id: str = "", user_id: str = "",
                  doc_id: str = "", require_tenant: bool = False) -> Optional[Dict[str, Any]]:
    """Return S3 object metadata if the object exists, else None (404).

    Never returns a presigned URL; the upload is verified by actual object
    metadata (size/etag/content-type/last-modified).
    """
    _require_tenant(tenant_id, require_tenant)
    client = s3 if s3 is not None else _s3_client()
    key = build_key(tenant_id, user_id, doc_id)
    try:
        resp = client.head_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    last_modified = resp.get("LastModified")
    return {
        "key": key,
        "docId": doc_id,
        "size": int(resp.get("ContentLength", 0) or 0),
        "etag": str(resp.get("ETag", "") or "").strip('"'),
        "contentType": resp.get("ContentType"),
        "lastModified": last_modified.isoformat() if hasattr(last_modified, "isoformat") else last_modified,
    }


def presign_download(s3: Any = None, tenant_id: str = "",
                     user_id: str = "", doc_id: str = "",
                     require_tenant: bool = False) -> Optional[Dict[str, Any]]:
    """Presigned GET wenn Objekt existiert, sonst None (404)."""
    _require_tenant(tenant_id, require_tenant)
    client = s3 if s3 is not None else _s3_client()
    key = build_key(tenant_id, user_id, doc_id)
    try:
        client.head_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    url = client.generate_presigned_url(
        "get_object", Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=UPLOAD_EXPIRY_SECONDS,
    )
    return {"documentId": doc_id, "downloadUrl": url,
            "expiresAt": _expires_at()}


def delete_document_report(s3: Any = None, tenant_id: str = "",
                           user_id: str = "", doc_id: str = "",
                           require_tenant: bool = False) -> Dict[str, Any]:
    """Delete the CURRENT object version and classify the result.

    On a versioned bucket this creates a delete marker; it does NOT purge
    older versions. ``physicalPurge`` is therefore always False here, and
    callers must not claim full physical deletion.
    """
    _require_tenant(tenant_id, require_tenant)
    client = s3 if s3 is not None else _s3_client()
    key = build_key(tenant_id, user_id, doc_id)
    try:
        client.head_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return {"documentId": doc_id, "existed": False,
                    "deleted": True, "deleteMarker": False,
                    "versionId": None, "physicalPurge": False}
        raise
    resp = client.delete_object(Bucket=_bucket(), Key=key) or {}
    version_id = resp.get("VersionId")
    return {"documentId": doc_id, "existed": True, "deleted": True,
            "deleteMarker": bool(version_id), "versionId": version_id,
            "physicalPurge": False}


def delete_document(s3: Any = None, tenant_id: str = "",
                    user_id: str = "", doc_id: str = "",
                    require_tenant: bool = False) -> bool:
    """Loeschen (versioniert -> Delete-Marker). True wenn vorhanden war."""
    _require_tenant(tenant_id, require_tenant)
    client = s3 if s3 is not None else _s3_client()
    key = build_key(tenant_id, user_id, doc_id)
    try:
        client.head_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise
    client.delete_object(Bucket=_bucket(), Key=key)
    return True


def delete_all_for_user(s3: Any = None, user_id: str = "") -> int:
    """Alle Dokumentobjekte eines Users loeschen (G5-Erasure).

    Schluessel sind tenant-scoped (``tenant/{t}/users/{sub}/documents/...``),
    die Tenant-ID steht aber nicht im Objekt-Key selbst. Deshalb wird ueber
    das praefix-Suffix ``/users/{user_id}/documents/`` gefiltert -- der
    userId ist ein Cognito-Sub und damit tenant-uebergreifend eindeutig.

    Bewusst additiv: gibt die Zahl geloeschter Objekte zurueck und wirft
    nicht, damit ein Teilerfolg als Teilerfolg berichtet wird statt die
    gesamte Erasure zu blockieren.
    """
    if not user_id:
        return 0
    client = s3 if s3 is not None else _s3_client()
    bucket = _bucket()
    suffix = f"/users/{user_id}/documents/"
    token: Optional[str] = None
    deleted = 0
    while True:
        kwargs = {"Bucket": bucket, "ContinuationToken": token} if token \
            else {"Bucket": bucket}
        try:
            response = client.list_objects_v2(**kwargs)
        except Exception:
            return deleted
        contents = response.get("Contents", []) or []
        for obj in contents:
            key = obj.get("Key", "")
            if not key.endswith(suffix) and f"/users/{user_id}/documents/" \
                    not in key:
                continue
            try:
                client.delete_object(Bucket=bucket, Key=key)
                deleted += 1
            except Exception:
                continue
        if not response.get("IsTruncated"):
            return deleted
        token = response.get("NextContinuationToken")
        if not token:
            return deleted


__all__ = ["presign_upload", "presign_download", "head_document",
           "delete_document", "delete_document_report",
           "delete_all_for_user", "build_key", "new_doc_id",
           "UPLOAD_EXPIRY_SECONDS", "ALLOWED_CONTENT_TYPES"]
