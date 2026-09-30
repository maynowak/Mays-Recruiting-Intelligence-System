#!/usr/bin/env python3
"""
Backend bootstrap for RIS foundation installation (minimal).

Creates the project-specific Terraform state backend (S3 bucket +
DynamoDB lock table) idempotently, or verifies existing resources.

Safety rules (hard):
- Naming derives ONLY from project_name/environment (isolation rule);
  no Mays-Orders names, no hardcoded accounts, no personal profiles.
- Existing resources are NEVER blindly adopted: bucket/tag ownership
  is checked (Project tag must match); foreign resources -> conflict
  error, installation STOPS.
- No state migration, no takeover, no deletion.
- All AWS calls are explicit boto3 resource operations (no shell-outs
  hiding behavior); every call is mockable for tests.
- Hardening mirrors the existing RIS app-bucket posture (SSE-S3,
  public-access block, versioning) — nothing invented beyond that.

Run ONLY via explicit installer invocation with --yes (never default).
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


class BackendConflictError(RuntimeError):
    """Existing backend resource is not owned by this project."""


@dataclass(frozen=True)
class BackendNames:
    """Project-derived backend resource names (pure derivation, no AWS)."""

    bucket: str
    lock_table: str
    key: str = "terraform.tfstate"
    region: str = "eu-central-1"

    @classmethod
    def for_project(
        cls,
        project_name: str,
        environment: str,
        region: str = "eu-central-1",
    ) -> "BackendNames":
        """Derive names: <project>-tf-state-<env> / <project>-tf-lock."""
        if not project_name or not project_name.strip():
            raise ValueError("project_name must not be empty")
        if not environment or not environment.strip():
            raise ValueError("environment must not be empty")
        project = project_name.strip()
        env = environment.strip()
        return cls(
            bucket=f"{project}-tf-state-{env}",
            lock_table=f"{project}-tf-lock",
            region=region,
        )


def _boto3_client(service: str, region: str, profile: Optional[str] = None):
    """Local boto3 import (keeps module importable without boto3)."""
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for backend bootstrap") from exc
    if profile:
        session = boto3.Session(profile_name=profile, region_name=region)
    else:
        session = boto3.Session(region_name=region)
    return session.client(service)


class BackendBootstrap:
    """Idempotent backend bootstrap (create-if-absent, verify-if-present)."""

    def __init__(
        self,
        names: BackendNames,
        project_name: str,
        profile: Optional[str] = None,
        client_factory=None,
    ) -> None:
        self.names = names
        self.project_name = project_name
        self.profile = profile
        self._client_factory = client_factory or _boto3_client

    # -- S3 ---------------------------------------------------------
    def _bucket_exists(self, s3) -> bool:
        try:
            s3.head_bucket(Bucket=self.names.bucket)
            return True
        except Exception as exc:
            if "404" in str(exc) or "NoSuchBucket" in str(exc):
                return False
            raise

    def _bucket_owned(self, s3) -> bool:
        """Ownership proof: Project tag must match (never name-only)."""
        try:
            tags = s3.get_bucket_tagging(Bucket=self.names.bucket).get(
                "TagSet", []
            )
        except Exception:
            return False
        return any(
            t.get("Key") == "Project" and t.get("Value") == self.project_name
            for t in tags
        )

    def ensure_bucket(self) -> Dict[str, Any]:
        """Create bucket if absent (hardened); verify ownership if present."""
        s3 = self._client_factory("s3", self.names.region, self.profile)
        if self._bucket_exists(s3):
            if not self._bucket_owned(s3):
                raise BackendConflictError(
                    f"bucket {self.names.bucket} exists but is not tagged "
                    f"Project={self.project_name}; refusing adopt"
                )
            return {"bucket": self.names.bucket, "created": False}
        kwargs: Dict[str, Any] = {"Bucket": self.names.bucket}
        if self.names.region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {
                "LocationConstraint": self.names.region
            }
        s3.create_bucket(**kwargs)
        s3.put_bucket_encryption(
            Bucket=self.names.bucket,
            ServerSideEncryptionConfiguration={
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            },
        )
        s3.put_public_access_block(
            Bucket=self.names.bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        s3.put_bucket_versioning(
            Bucket=self.names.bucket,
            VersioningConfiguration={"Status": "Enabled"},
        )
        s3.put_bucket_tagging(
            Bucket=self.names.bucket,
            Tagging={"TagSet": [{"Key": "Project", "Value": self.project_name}]},
        )
        return {"bucket": self.names.bucket, "created": True}

    # -- DynamoDB ---------------------------------------------------
    def _table_exists(self, dynamodb) -> bool:
        try:
            dynamodb.describe_table(TableName=self.names.lock_table)
            return True
        except Exception as exc:
            if "ResourceNotFound" in str(exc):
                return False
            raise

    def ensure_lock_table(self) -> Dict[str, Any]:
        """Create lock table if absent (Terraform lock schema)."""
        dynamodb = self._client_factory(
            "dynamodb", self.names.region, self.profile
        )
        if self._table_exists(dynamodb):
            return {"lock_table": self.names.lock_table, "created": False}
        dynamodb.create_table(
            TableName=self.names.lock_table,
            AttributeDefinitions=[{"AttributeName": "LockID", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "LockID", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
            Tags=[{"Key": "Project", "Value": self.project_name}],
        )
        return {"lock_table": self.names.lock_table, "created": True}

    def ensure_all(self) -> Dict[str, Any]:
        """Bootstrap bucket + lock table (idempotent)."""
        bucket = self.ensure_bucket()
        lock = self.ensure_lock_table()
        return {"bucket": bucket, "lock_table": lock}
