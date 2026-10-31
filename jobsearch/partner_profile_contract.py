"""Partner profile persistence contract (schema v1).

Persistence-neutral contract and validation layer for the durable storage of
Jobsearch partner profiles inside RIS.

This module deliberately contains NO persistence (no DynamoDB, no API routes,
no AWS resources). It defines:

- the canonical resource types and their v1 schemas
- parent/child hierarchy validation (User -> CV -> CVSearchProfile -> ATSSearchProfile)
- independent manual search profiles
- validation of multi-value search configuration without loss
- separation of ATS criteria and manual MatchingPreferences
- server-authoritative identity handling
- error classification for invalid data

Identity fields (userId, tenantId) are NEVER accepted from client payloads;
they are injected by the server context.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from jobsearch.domain_models import WorkMode, EmploymentType


SCHEMA_VERSION = "v1"

RESOURCE_TYPES = frozenset({
    "UserProfile",
    "CVDocument",
    "CVSearchProfile",
    "ATSSearchProfile",
    "ManualSearchProfile",
    "MatchingPreferences",
})

# Capacity limits per product contract.
MAX_CVS_PER_USER = 10
MAX_SEARCH_PROFILES_PER_CV = 2
MAX_ATS_PROFILES_PER_SEARCH_PROFILE = 5
# Manual profile limit deliberately left open (product contract pending).

# Fields that must never be supplied by a client payload.
CLIENT_FORBIDDEN_IDENTITY_FIELDS = frozenset({
    "userId", "user_id", "tenantId", "tenant_id",
    "ownerId", "owner_id", "ownerUserId", "owner_user_id",
})

# Strict field sets per resource type (camelCase persisted form).
USER_PROFILE_FIELDS = frozenset({
    "resourceType", "schemaVersion", "userId", "tenantId",
    "displayName", "email", "createdAt", "updatedAt", "metadata",
})
CV_DOCUMENT_FIELDS = frozenset({
    "resourceType", "schemaVersion", "cvId", "userId", "tenantId",
    "name", "size", "contentHash", "createdAt", "updatedAt", "metadata",
})
CV_SEARCH_PROFILE_FIELDS = frozenset({
    "resourceType", "schemaVersion", "searchProfileId", "cvId", "userId",
    "tenantId", "name", "profile", "searchConfiguration", "createdAt",
    "updatedAt", "metadata",
})
ATS_SEARCH_PROFILE_FIELDS = frozenset({
    "resourceType", "schemaVersion", "atsProfileId", "searchProfileId", "cvId",
    "userId", "tenantId", "name", "targetRoles", "atsKeywords", "skills",
    "requirements", "preferredCriteria", "exclusions", "location", "radius",
    "workMode", "createdAt", "updatedAt", "metadata",
})
MANUAL_SEARCH_PROFILE_FIELDS = frozenset({
    "resourceType", "schemaVersion", "manualProfileId", "userId", "tenantId",
    "name", "matchingPreferences", "createdAt", "updatedAt", "metadata",
})
MATCHING_PREFERENCES_FIELDS = frozenset({
    "resourceType", "schemaVersion", "roles", "workModes", "employmentTypes",
    "locations", "salaryMin", "remoteOnly", "sources", "query",
})


class ProfileContractError(ValueError):
    """Classified contract validation error."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileContractError("MISSING_FIELD", f"{field} must be a non-empty string")
    return value.strip()


def _optional_str(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProfileContractError("INVALID_FIELD", f"{field} must be a string or null")
    v = value.strip()
    return v if v else None


def _str_list(value: Any, field: str, *, allow_empty: bool = True) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProfileContractError("INVALID_FIELD", f"{field} must be a list of strings")
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ProfileContractError("INVALID_FIELD", f"{field} entries must be strings")
        s = item.strip()
        if s:
            out.append(s)
    if not allow_empty and not out:
        raise ProfileContractError("MISSING_FIELD", f"{field} must not be empty")
    return out


def _int_or_none(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileContractError("INVALID_FIELD", f"{field} must be an integer or null")
    return value


def _check_unknown_fields(payload: Dict[str, Any], allowed: Set[str], resource_type: str) -> None:
    unknown = set(payload.keys()) - allowed
    if unknown:
        raise ProfileContractError(
            "UNKNOWN_FIELD",
            f"Unknown fields for {resource_type}: {sorted(unknown)}",
        )


def _check_schema_version(value: Any) -> str:
    if value is None:
        return SCHEMA_VERSION
    if not isinstance(value, str) or value != SCHEMA_VERSION:
        raise ProfileContractError(
            "INVALID_SCHEMA_VERSION",
            f"schemaVersion must be '{SCHEMA_VERSION}', got {value!r}",
        )
    return value


def _check_resource_type(value: Any, expected: str) -> str:
    if value is None:
        return expected
    if not isinstance(value, str) or value != expected:
        raise ProfileContractError(
            "INVALID_RESOURCE_TYPE",
            f"resourceType must be '{expected}', got {value!r}",
        )
    return value


def reject_client_identity(payload: Dict[str, Any]) -> None:
    """Raise if a client payload attempts to supply identity fields."""
    forbidden = set(payload.keys()) & CLIENT_FORBIDDEN_IDENTITY_FIELDS
    if forbidden:
        raise ProfileContractError(
            "CLIENT_IDENTITY_FORBIDDEN",
            f"Client must not supply identity fields: {sorted(forbidden)}",
        )


@dataclass
class MatchingPreferences:
    roles: List[str] = field(default_factory=list)
    work_modes: List[str] = field(default_factory=list)
    employment_types: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    salary_min: Optional[int] = None
    remote_only: bool = False
    sources: List[str] = field(default_factory=list)
    query: str = ""

    resource_type: str = "MatchingPreferences"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "roles": list(self.roles),
            "workModes": list(self.work_modes),
            "employmentTypes": list(self.employment_types),
            "locations": list(self.locations),
            "remoteOnly": bool(self.remote_only),
        }
        if self.salary_min is not None:
            result["salaryMin"] = self.salary_min
        if self.sources:
            result["sources"] = list(self.sources)
        if self.query:
            result["query"] = self.query
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "MatchingPreferences":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "MatchingPreferences must be an object")
        if strict:
            _check_unknown_fields(data, MATCHING_PREFERENCES_FIELDS, "MatchingPreferences")
        rt = _check_resource_type(data.get("resourceType"), "MatchingPreferences")
        sv = _check_schema_version(data.get("schemaVersion"))
        prefs = cls(
            roles=_str_list(data.get("roles", []), "roles"),
            work_modes=_str_list(data.get("workModes", []), "workModes"),
            employment_types=_str_list(data.get("employmentTypes", []), "employmentTypes"),
            locations=_str_list(data.get("locations", []), "locations"),
            salary_min=_int_or_none(data.get("salaryMin"), "salaryMin"),
            remote_only=bool(data.get("remoteOnly", False)),
            sources=_str_list(data.get("sources", []), "sources"),
            query=str(data.get("query", "") or ""),
            resource_type=rt,
            schema_version=sv,
        )
        prefs.validate()
        return prefs

    def validate(self) -> None:
        # Preserve multi-values: no deduplication, no collapse.
        for field_name in ("roles", "work_modes", "employment_types", "locations", "sources"):
            val = getattr(self, field_name)
            if not isinstance(val, list):
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"{field_name} must be a list")
        # work modes validated against known enum when provided
        for wm in self.work_modes:
            if wm not in {e.value for e in WorkMode}:
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"Unknown workMode: {wm}")
        for et in self.employment_types:
            if et not in {e.value for e in EmploymentType}:
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"Unknown employmentType: {et}")


@dataclass
class UserProfile:
    user_id: str
    tenant_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    resource_type: str = "UserProfile"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
        }
        if self.display_name:
            result["displayName"] = self.display_name
        if self.email:
            result["email"] = self.email
        if self.created_at:
            result["createdAt"] = self.created_at
        if self.updated_at:
            result["updatedAt"] = self.updated_at
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "UserProfile":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "UserProfile must be an object")
        if strict:
            _check_unknown_fields(data, USER_PROFILE_FIELDS, "UserProfile")
        rt = _check_resource_type(data.get("resourceType"), "UserProfile")
        sv = _check_schema_version(data.get("schemaVersion"))
        user_id = _require_str(data.get("userId"), "userId")
        tenant_id = _require_str(data.get("tenantId"), "tenantId")
        obj = cls(
            user_id=user_id,
            tenant_id=tenant_id,
            display_name=_optional_str(data.get("displayName"), "displayName"),
            email=_optional_str(data.get("email"), "email"),
            metadata=data.get("metadata") or {},
            created_at=_optional_str(data.get("createdAt"), "createdAt"),
            updated_at=_optional_str(data.get("updatedAt"), "updatedAt"),
            resource_type=rt,
            schema_version=sv,
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        _require_str(self.user_id, "userId")
        _require_str(self.tenant_id, "tenantId")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ProfileContractError("INVALID_FIELD", "metadata must be an object")


@dataclass
class CVDocument:
    cv_id: str
    user_id: str
    tenant_id: str
    name: str
    size: int = 0
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    resource_type: str = "CVDocument"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "cvId": self.cv_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "name": self.name,
            "size": int(self.size or 0),
        }
        if self.content_hash:
            result["contentHash"] = self.content_hash
        if self.created_at:
            result["createdAt"] = self.created_at
        if self.updated_at:
            result["updatedAt"] = self.updated_at
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "CVDocument":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "CVDocument must be an object")
        if strict:
            _check_unknown_fields(data, CV_DOCUMENT_FIELDS, "CVDocument")
        rt = _check_resource_type(data.get("resourceType"), "CVDocument")
        sv = _check_schema_version(data.get("schemaVersion"))
        obj = cls(
            cv_id=_require_str(data.get("cvId"), "cvId"),
            user_id=_require_str(data.get("userId"), "userId"),
            tenant_id=_require_str(data.get("tenantId"), "tenantId"),
            name=_require_str(data.get("name"), "name"),
            size=data.get("size", 0),
            content_hash=_optional_str(data.get("contentHash"), "contentHash"),
            metadata=data.get("metadata") or {},
            created_at=_optional_str(data.get("createdAt"), "createdAt"),
            updated_at=_optional_str(data.get("updatedAt"), "updatedAt"),
            resource_type=rt,
            schema_version=sv,
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        _require_str(self.cv_id, "cvId")
        _require_str(self.user_id, "userId")
        _require_str(self.tenant_id, "tenantId")
        _require_str(self.name, "name")
        if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size < 0:
            raise ProfileContractError("INVALID_FIELD", "size must be a non-negative integer")
        # No Browser File objects or original CV text may be stored.
        if "file" in (self.metadata or {}):
            raise ProfileContractError("FORBIDDEN_CONTENT", "Browser File objects must not be stored in profile JSON")
        if "cvText" in (self.metadata or {}) or "originalText" in (self.metadata or {}):
            raise ProfileContractError("FORBIDDEN_CONTENT", "Original CV text must not be stored in profile JSON")


@dataclass
class CVSearchProfile:
    search_profile_id: str
    cv_id: str
    user_id: str
    tenant_id: str
    name: str
    profile: Dict[str, Any] = field(default_factory=dict)
    search_configuration: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    resource_type: str = "CVSearchProfile"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "searchProfileId": self.search_profile_id,
            "cvId": self.cv_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "name": self.name,
        }
        if self.profile:
            result["profile"] = dict(self.profile)
        if self.search_configuration:
            result["searchConfiguration"] = dict(self.search_configuration)
        if self.created_at:
            result["createdAt"] = self.created_at
        if self.updated_at:
            result["updatedAt"] = self.updated_at
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "CVSearchProfile":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "CVSearchProfile must be an object")
        if strict:
            _check_unknown_fields(data, CV_SEARCH_PROFILE_FIELDS, "CVSearchProfile")
        rt = _check_resource_type(data.get("resourceType"), "CVSearchProfile")
        sv = _check_schema_version(data.get("schemaVersion"))
        obj = cls(
            search_profile_id=_require_str(data.get("searchProfileId"), "searchProfileId"),
            cv_id=_require_str(data.get("cvId"), "cvId"),
            user_id=_require_str(data.get("userId"), "userId"),
            tenant_id=_require_str(data.get("tenantId"), "tenantId"),
            name=_require_str(data.get("name"), "name"),
            profile=data.get("profile") or {},
            search_configuration=data.get("searchConfiguration") or {},
            metadata=data.get("metadata") or {},
            created_at=_optional_str(data.get("createdAt"), "createdAt"),
            updated_at=_optional_str(data.get("updatedAt"), "updatedAt"),
            resource_type=rt,
            schema_version=sv,
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        _require_str(self.search_profile_id, "searchProfileId")
        _require_str(self.cv_id, "cvId")
        _require_str(self.user_id, "userId")
        _require_str(self.tenant_id, "tenantId")
        _require_str(self.name, "name")
        if not isinstance(self.profile, dict):
            raise ProfileContractError("INVALID_FIELD", "profile must be an object")
        if not isinstance(self.search_configuration, dict):
            raise ProfileContractError("INVALID_FIELD", "searchConfiguration must be an object")
        # preserve multi-values: lists must stay lists
        sc = self.search_configuration
        for key in ("targetRoles", "workModes", "employmentTypes", "locations", "skills"):
            if key in sc and not isinstance(sc[key], list):
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"searchConfiguration.{key} must be a list")


@dataclass
class ATSSearchProfile:
    ats_profile_id: str
    search_profile_id: str
    cv_id: str
    user_id: str
    tenant_id: str
    name: str
    target_roles: List[str] = field(default_factory=list)
    ats_keywords: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    preferred_criteria: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    location: Optional[str] = None
    radius: Optional[str] = None
    work_mode: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    resource_type: str = "ATSSearchProfile"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "atsProfileId": self.ats_profile_id,
            "searchProfileId": self.search_profile_id,
            "cvId": self.cv_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "name": self.name,
        }
        if self.target_roles:
            result["targetRoles"] = list(self.target_roles)
        if self.ats_keywords:
            result["atsKeywords"] = list(self.ats_keywords)
        if self.skills:
            result["skills"] = list(self.skills)
        if self.requirements:
            result["requirements"] = list(self.requirements)
        if self.preferred_criteria:
            result["preferredCriteria"] = list(self.preferred_criteria)
        if self.exclusions:
            result["exclusions"] = list(self.exclusions)
        if self.location:
            result["location"] = self.location
        if self.radius:
            result["radius"] = self.radius
        if self.work_mode:
            result["workMode"] = self.work_mode
        if self.created_at:
            result["createdAt"] = self.created_at
        if self.updated_at:
            result["updatedAt"] = self.updated_at
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "ATSSearchProfile":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "ATSSearchProfile must be an object")
        if strict:
            _check_unknown_fields(data, ATS_SEARCH_PROFILE_FIELDS, "ATSSearchProfile")
        rt = _check_resource_type(data.get("resourceType"), "ATSSearchProfile")
        sv = _check_schema_version(data.get("schemaVersion"))
        obj = cls(
            ats_profile_id=_require_str(data.get("atsProfileId"), "atsProfileId"),
            search_profile_id=_require_str(data.get("searchProfileId"), "searchProfileId"),
            cv_id=_require_str(data.get("cvId"), "cvId"),
            user_id=_require_str(data.get("userId"), "userId"),
            tenant_id=_require_str(data.get("tenantId"), "tenantId"),
            name=_require_str(data.get("name"), "name"),
            target_roles=_str_list(data.get("targetRoles", []), "targetRoles"),
            ats_keywords=_str_list(data.get("atsKeywords", []), "atsKeywords"),
            skills=_str_list(data.get("skills", []), "skills"),
            requirements=_str_list(data.get("requirements", []), "requirements"),
            preferred_criteria=_str_list(data.get("preferredCriteria", []), "preferredCriteria"),
            exclusions=_str_list(data.get("exclusions", []), "exclusions"),
            location=_optional_str(data.get("location"), "location"),
            radius=_optional_str(data.get("radius"), "radius"),
            work_mode=_optional_str(data.get("workMode"), "workMode"),
            metadata=data.get("metadata") or {},
            created_at=_optional_str(data.get("createdAt"), "createdAt"),
            updated_at=_optional_str(data.get("updatedAt"), "updatedAt"),
            resource_type=rt,
            schema_version=sv,
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        _require_str(self.ats_profile_id, "atsProfileId")
        _require_str(self.search_profile_id, "searchProfileId")
        _require_str(self.cv_id, "cvId")
        _require_str(self.user_id, "userId")
        _require_str(self.tenant_id, "tenantId")
        _require_str(self.name, "name")


@dataclass
class ManualSearchProfile:
    manual_profile_id: str
    user_id: str
    tenant_id: str
    name: str
    matching_preferences: MatchingPreferences = field(default_factory=MatchingPreferences)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    resource_type: str = "ManualSearchProfile"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "manualProfileId": self.manual_profile_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "name": self.name,
            "matchingPreferences": self.matching_preferences.to_dict(),
        }
        if self.created_at:
            result["createdAt"] = self.created_at
        if self.updated_at:
            result["updatedAt"] = self.updated_at
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "ManualSearchProfile":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "ManualSearchProfile must be an object")
        if strict:
            _check_unknown_fields(data, MANUAL_SEARCH_PROFILE_FIELDS, "ManualSearchProfile")
        rt = _check_resource_type(data.get("resourceType"), "ManualSearchProfile")
        sv = _check_schema_version(data.get("schemaVersion"))
        mp_raw = data.get("matchingPreferences", {}) or {}
        mp = MatchingPreferences.from_dict(mp_raw, strict=strict) if isinstance(mp_raw, dict) else mp_raw
        obj = cls(
            manual_profile_id=_require_str(data.get("manualProfileId"), "manualProfileId"),
            user_id=_require_str(data.get("userId"), "userId"),
            tenant_id=_require_str(data.get("tenantId"), "tenantId"),
            name=_require_str(data.get("name"), "name"),
            matching_preferences=mp,
            metadata=data.get("metadata") or {},
            created_at=_optional_str(data.get("createdAt"), "createdAt"),
            updated_at=_optional_str(data.get("updatedAt"), "updatedAt"),
            resource_type=rt,
            schema_version=sv,
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        _require_str(self.manual_profile_id, "manualProfileId")
        _require_str(self.user_id, "userId")
        _require_str(self.tenant_id, "tenantId")
        _require_str(self.name, "name")
        if not isinstance(self.matching_preferences, MatchingPreferences):
            raise ProfileContractError("INVALID_FIELD", "matchingPreferences must be a MatchingPreferences")


# ---------------------------------------------------------------------------
# Hierarchy / capacity validators
# ---------------------------------------------------------------------------


def validate_cv_capacity(user_cvs: List[CVDocument]) -> None:
    if len(user_cvs) > MAX_CVS_PER_USER:
        raise ProfileContractError(
            "CAPACITY_EXCEEDED",
            f"User may have at most {MAX_CVS_PER_USER} CVs, got {len(user_cvs)}",
        )


def validate_search_profile_capacity(cv_search_profiles: List[CVSearchProfile]) -> None:
    if len(cv_search_profiles) > MAX_SEARCH_PROFILES_PER_CV:
        raise ProfileContractError(
            "CAPACITY_EXCEEDED",
            f"A CV may have at most {MAX_SEARCH_PROFILES_PER_CV} search profiles, got {len(cv_search_profiles)}",
        )


def validate_ats_profile_capacity(ats_profiles: List[ATSSearchProfile]) -> None:
    if len(ats_profiles) > MAX_ATS_PROFILES_PER_SEARCH_PROFILE:
        raise ProfileContractError(
            "CAPACITY_EXCEEDED",
            f"A search profile may have at most {MAX_ATS_PROFILES_PER_SEARCH_PROFILE} ATS profiles, got {len(ats_profiles)}",
        )


def validate_parent_link(child: Any, parent: Any) -> None:
    """Validate that a child's parent reference matches the parent resource."""
    if isinstance(child, CVSearchProfile):
        if getattr(parent, "cv_id", None) is not None and child.cv_id != parent.cv_id:
            raise ProfileContractError("INVALID_HIERARCHY", "CVSearchProfile.cvId must match parent CV")
        if child.user_id != getattr(parent, "user_id", child.user_id):
            raise ProfileContractError("INVALID_HIERARCHY", "CVSearchProfile.userId must match parent CV")
        if child.tenant_id != getattr(parent, "tenant_id", child.tenant_id):
            raise ProfileContractError("INVALID_HIERARCHY", "CVSearchProfile.tenantId must match parent CV")
    elif isinstance(child, ATSSearchProfile):
        if child.search_profile_id != getattr(parent, "search_profile_id", child.search_profile_id):
            raise ProfileContractError("INVALID_HIERARCHY", "ATSSearchProfile.searchProfileId must match parent search profile")
        if child.cv_id != getattr(parent, "cv_id", child.cv_id):
            raise ProfileContractError("INVALID_HIERARCHY", "ATSSearchProfile.cvId must match parent search profile")
        if child.user_id != getattr(parent, "user_id", child.user_id):
            raise ProfileContractError("INVALID_HIERARCHY", "ATSSearchProfile.userId must match parent")
        if child.tenant_id != getattr(parent, "tenant_id", child.tenant_id):
            raise ProfileContractError("INVALID_HIERARCHY", "ATSSearchProfile.tenantId must match parent")


def validate_ats_assignment(ats_profile: ATSSearchProfile, search_profile: CVSearchProfile) -> None:
    if ats_profile.search_profile_id != search_profile.search_profile_id:
        raise ProfileContractError("INVALID_HIERARCHY", "ATS profile must reference an existing search profile")
    if ats_profile.cv_id != search_profile.cv_id:
        raise ProfileContractError("INVALID_HIERARCHY", "ATS profile cvId must match search profile cvId")
    if ats_profile.user_id != search_profile.user_id or ats_profile.tenant_id != search_profile.tenant_id:
        raise ProfileContractError("INVALID_HIERARCHY", "ATS profile identity must match search profile")


def parse_resource(payload: Dict[str, Any], *, strict: bool = True) -> Any:
    """Parse a single resource payload into its typed object."""
    if not isinstance(payload, dict):
        raise ProfileContractError("INVALID_FIELD", "Resource payload must be an object")
    rt = payload.get("resourceType")
    if rt == "UserProfile":
        return UserProfile.from_dict(payload, strict=strict)
    if rt == "CVDocument":
        return CVDocument.from_dict(payload, strict=strict)
    if rt == "CVSearchProfile":
        return CVSearchProfile.from_dict(payload, strict=strict)
    if rt == "ATSSearchProfile":
        return ATSSearchProfile.from_dict(payload, strict=strict)
    if rt == "ManualSearchProfile":
        return ManualSearchProfile.from_dict(payload, strict=strict)
    if rt == "MatchingPreferences":
        return MatchingPreferences.from_dict(payload, strict=strict)
    raise ProfileContractError("INVALID_RESOURCE_TYPE", f"Unknown or missing resourceType: {rt!r}")


def build_from_client_payload(
    resource_type: str,
    payload: Dict[str, Any],
    *,
    server_user_id: str,
    server_tenant_id: str,
) -> Any:
    """Build a resource from a client payload, injecting server-authoritative identity.

    Client-supplied identity fields are rejected.
    """
    if not isinstance(payload, dict):
        raise ProfileContractError("INVALID_FIELD", "payload must be an object")
    reject_client_identity(payload)
    data = dict(payload)
    data["resourceType"] = resource_type
    # inject identity according to resource type
    if resource_type == "UserProfile":
        data["userId"] = server_user_id
        data["tenantId"] = server_tenant_id
    elif resource_type == "CVDocument":
        data["userId"] = server_user_id
        data["tenantId"] = server_tenant_id
    elif resource_type == "CVSearchProfile":
        data["userId"] = server_user_id
        data["tenantId"] = server_tenant_id
    elif resource_type == "ATSSearchProfile":
        data["userId"] = server_user_id
        data["tenantId"] = server_tenant_id
    elif resource_type == "ManualSearchProfile":
        data["userId"] = server_user_id
        data["tenantId"] = server_tenant_id
    return parse_resource(data, strict=True)
