"""Temporary private job-ad storage with a hard 4-hour access limit.

Default TTL 2h, max 4h, max 1 MiB. The object key is never client-chosen; the
reference is opaque and bound to tenant, user and the request. S3 lifecycle is
only a backup; access is refused server-side.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

STANDARD_TTL_SECONDS = 2 * 60 * 60
MAX_TTL_SECONDS = 4 * 60 * 60
MAX_JOB_BYTES = 1024 * 1024
REF_PREFIX = "job_"


class JobStoreError(RuntimeError):
    code = "job_store_error"


class JobNotFound(JobStoreError):
    code = "job_not_found"


class JobExpired(JobStoreError):
    code = "job_ref_expired"


class JobAccessDenied(JobStoreError):
    code = "job_access_denied"


class JobTooLarge(JobStoreError):
    code = "job_too_large"


@dataclass(frozen=True)
class JobRecord:
    ref: str
    text: str
    tenant_id: str
    user_id: str
    created_at: float
    expires_at: float
    max_expires_at: float
    sha256: str
    size: int


def _validate(text: str) -> bytes:
    if not isinstance(text, str) or not text.strip():
        raise JobStoreError("job text must be a non-empty string")
    try:
        raw = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise JobStoreError("job text must be valid UTF-8") from exc
    if len(raw) > MAX_JOB_BYTES:
        raise JobTooLarge(f"job text exceeds {MAX_JOB_BYTES} bytes")
    return raw


class InMemoryJobStore:
    """Deterministic store for tests and local verification."""

    def __init__(self, clock: Optional[Callable[[], float]] = None):
        self._clock = clock or time.time
        self._records: Dict[str, JobRecord] = {}

    def put(self, text: str, tenant_id: str, user_id: str,
            ttl_seconds: int = STANDARD_TTL_SECONDS) -> JobRecord:
        raw = _validate(text)
        if not tenant_id or not user_id:
            raise JobAccessDenied("tenant and user are required")
        ttl = min(max(int(ttl_seconds), 1), MAX_TTL_SECONDS)
        now = self._clock()
        ref = REF_PREFIX + secrets.token_urlsafe(24)
        record = JobRecord(
            ref=ref, text=text, tenant_id=tenant_id, user_id=user_id,
            created_at=now, expires_at=now + ttl,
            max_expires_at=now + MAX_TTL_SECONDS,
            sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
        self._records[ref] = record
        return record

    def get(self, ref: str, tenant_id: str, user_id: str) -> JobRecord:
        record = self._records.get(ref)
        if record is None:
            raise JobNotFound("jobRef not found")
        if record.tenant_id != tenant_id or record.user_id != user_id:
            raise JobAccessDenied("jobRef belongs to another owner")
        if self._clock() >= record.expires_at:
            raise JobExpired("jobRef has expired")
        return record

    def extend(self, ref: str, tenant_id: str, user_id: str,
               extend_seconds: int = STANDARD_TTL_SECONDS) -> JobRecord:
        record = self.get(ref, tenant_id, user_id)
        now = self._clock()
        expires = min(record.expires_at + int(extend_seconds),
                      record.max_expires_at)
        if expires <= now:
            raise JobExpired("jobRef cannot be extended beyond 4 hours")
        updated = JobRecord(
            ref=record.ref, text=record.text, tenant_id=record.tenant_id,
            user_id=record.user_id, created_at=record.created_at,
            expires_at=expires, max_expires_at=record.max_expires_at,
            sha256=record.sha256, size=record.size)
        self._records[ref] = updated
        return updated

    def delete(self, ref: str) -> bool:
        return self._records.pop(ref, None) is not None

    def cleanup_expired(self) -> int:
        now = self._clock()
        expired = [ref for ref, record in self._records.items()
                   if now >= record.max_expires_at]
        for ref in expired:
            self._records.pop(ref, None)
        return len(expired)


class S3JobStore:
    """Private S3 store; lifecycle is only a backup for access control."""

    def __init__(self, bucket: str, *, client: Any = None,
                 prefix: str = "jobs", clock: Optional[Callable[[], float]] = None):
        if not bucket:
            raise JobStoreError("bucket is required")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = client
        self._clock = clock or time.time

    def _s3(self):
        if self._client is None:
            import boto3

            self._client = boto3.client("s3")
        return self._client

    def _key(self, ref: str, tenant_id: str, user_id: str) -> str:
        if not ref.startswith(REF_PREFIX):
            raise JobNotFound("jobRef not found")
        return f"{self.prefix}/{tenant_id}/{user_id}/{ref}.txt"

    def put(self, text: str, tenant_id: str, user_id: str,
            ttl_seconds: int = STANDARD_TTL_SECONDS) -> JobRecord:
        raw = _validate(text)
        if not tenant_id or not user_id:
            raise JobAccessDenied("tenant and user are required")
        ttl = min(max(int(ttl_seconds), 1), MAX_TTL_SECONDS)
        now = self._clock()
        ref = REF_PREFIX + secrets.token_urlsafe(24)
        key = self._key(ref, tenant_id, user_id)
        self._s3().put_object(
            Bucket=self.bucket, Key=key, Body=raw,
            ContentType="text/plain; charset=utf-8",
            ServerSideEncryption="AES256",
            Metadata={
                "tenant": tenant_id,
                "user": user_id,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "expires-at": str(int(now + ttl)),
                "max-expires-at": str(int(now + MAX_TTL_SECONDS)),
            })
        return JobRecord(ref=ref, text=text, tenant_id=tenant_id,
                         user_id=user_id, created_at=now,
                         expires_at=now + ttl,
                         max_expires_at=now + MAX_TTL_SECONDS,
                         sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))

    def get(self, ref: str, tenant_id: str, user_id: str) -> JobRecord:
        key = self._key(ref, tenant_id, user_id)
        try:
            obj = self._s3().get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 - boundary
            raise JobNotFound("jobRef not found") from exc
        metadata = obj.get("Metadata") or {}
        if metadata.get("tenant") != tenant_id or metadata.get("user") != user_id:
            raise JobAccessDenied("jobRef belongs to another owner")
        now = self._clock()
        if now >= float(metadata.get("max-expires-at", 0) or 0):
            raise JobExpired("jobRef has expired")
        if now >= float(metadata.get("expires-at", 0) or 0):
            raise JobExpired("jobRef has expired")
        raw = obj["Body"].read()
        if len(raw) > MAX_JOB_BYTES:
            raise JobTooLarge("stored job exceeds the size limit")
        text = raw.decode("utf-8")
        return JobRecord(ref=ref, text=text, tenant_id=tenant_id,
                         user_id=user_id,
                         created_at=float(metadata.get("created-at", now)),
                         expires_at=float(metadata.get("expires-at", now)),
                         max_expires_at=float(metadata.get("max-expires-at", now)),
                         sha256=str(metadata.get("sha256", "")), size=len(raw))

    def extend(self, ref: str, tenant_id: str, user_id: str,
               extend_seconds: int = STANDARD_TTL_SECONDS) -> JobRecord:
        record = self.get(ref, tenant_id, user_id)
        now = self._clock()
        expires = min(record.expires_at + int(extend_seconds),
                      record.max_expires_at)
        if expires <= now:
            raise JobExpired("jobRef cannot be extended beyond 4 hours")
        key = self._key(ref, tenant_id, user_id)
        self._s3().copy_object(
            Bucket=self.bucket, Key=key, CopySource={"Bucket": self.bucket, "Key": key},
            MetadataDirective="REPLACE",
            ContentType="text/plain; charset=utf-8",
            ServerSideEncryption="AES256",
            Metadata={
                "tenant": tenant_id, "user": user_id,
                "sha256": record.sha256,
                "created-at": str(int(record.created_at)),
                "expires-at": str(int(expires)),
                "max-expires-at": str(int(record.max_expires_at)),
            })
        return JobRecord(ref=record.ref, text=record.text,
                         tenant_id=tenant_id, user_id=user_id,
                         created_at=record.created_at, expires_at=expires,
                         max_expires_at=record.max_expires_at,
                         sha256=record.sha256, size=record.size)

    def delete(self, ref: str, tenant_id: str, user_id: str) -> bool:
        key = self._key(ref, tenant_id, user_id)
        try:
            self._s3().delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001 - delete is best effort
            return False

    def cleanup_expired(self) -> int:
        """Best-effort sweep; S3 lifecycle remains the backup."""
        removed = 0
        paginator = self._s3().get_paginator("list_objects_v2")
        now = self._clock()
        for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{self.prefix}/"):
            for item in page.get("Contents", []):
                key = item.get("Key", "")
                try:
                    head = self._s3().head_object(Bucket=self.bucket, Key=key)
                except Exception:  # noqa: BLE001
                    continue
                if now >= float((head.get("Metadata") or {}).get(
                        "max-expires-at", 0) or 0):
                    self._s3().delete_object(Bucket=self.bucket, Key=key)
                    removed += 1
        return removed


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
