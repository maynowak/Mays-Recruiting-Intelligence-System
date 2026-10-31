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


# Canonical Jobsearch Profile Data Contract v1 uses the INTEGER 1.
SCHEMA_VERSION = 1
# Accepted only when reading resources persisted before the R05-P0 repair.
LEGACY_SCHEMA_VERSION = "v1"

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
    "name", "size", "contentHash", "contentType", "etag", "uploadedAt",
    "documentId", "processingStatus", "createdAt", "updatedAt", "metadata",
})

# CV processing status machine (R04). READY requires a verified S3 object.
CV_STATUS_PENDING = "pending"
CV_STATUS_UPLOAD_PENDING = "upload_pending"
CV_STATUS_READY = "ready"
CV_STATUS_DELETE_FAILED = "delete_failed"
CV_STATUS_ERROR = "error"
CV_ALLOWED_STATUSES = frozenset({
    CV_STATUS_PENDING,
    CV_STATUS_UPLOAD_PENDING,
    CV_STATUS_READY,
    CV_STATUS_DELETE_FAILED,
    CV_STATUS_ERROR,
})
CV_SEARCH_PROFILE_FIELDS = frozenset({
    "resourceType", "schemaVersion", "searchProfileId", "cvId", "userId",
    "tenantId", "name", "description", "origin", "searchConfig",
    "profile", "searchConfiguration", "createdAt", "updatedAt", "metadata",
})
ATS_SEARCH_PROFILE_FIELDS = frozenset({
    "resourceType", "schemaVersion", "atsProfileId", "atsSearchProfileId",
    "searchProfileId", "cvId", "userId", "tenantId", "name", "targetRoles",
    "atsKeywords", "skills", "criteria", "requirements", "preferredCriteria",
    "exclusions", "location", "radius", "workMode", "createdAt", "updatedAt",
    "metadata", "version",
})
ATS_CRITERIA_FIELDS = frozenset({
    "schemaVersion", "requiredSkills", "preferredSkills", "excludedTerms",
})
MANUAL_SEARCH_PROFILE_FIELDS = frozenset({
    "resourceType", "schemaVersion", "manualProfileId", "userId", "tenantId",
    "name", "description", "origin", "searchConfig", "matchingPreferences",
    "createdAt", "updatedAt", "metadata",
})

# Canonical v1 SearchConfigurationV1 (nested object, exactly six fields).
SEARCH_CONFIGURATION_FIELDS = frozenset({
    "skills", "targetRoles", "city", "radiusKm", "workModes",
    "employmentTypes",
})
SEARCH_RADIUS_VALUES = frozenset({10, 25, 50, 100})
SEARCH_EMPLOYMENT_TYPES = frozenset({"full_time", "part_time"})

# Canonical v1 MatchingPreferencesV1 (three phrase lists only).
MATCHING_PREFERENCES_FIELDS = frozenset({
    "requiredSkills", "preferredSkills", "excludedTerms",
})
# Legacy R03 fields that are read for migration but never emitted in v1.
MATCHING_PREFERENCES_LEGACY_FIELDS = frozenset({
    "resourceType", "schemaVersion", "roles", "workModes",
    "employmentTypes", "locations", "salaryMin", "remoteOnly", "sources",
    "query",
})
MATCHING_PREFERENCES_KNOWN_FIELDS = (
    MATCHING_PREFERENCES_FIELDS | MATCHING_PREFERENCES_LEGACY_FIELDS)

MANUAL_PROFILE_ORIGIN = "manual"
CV_PROFILE_ORIGIN = "cv"


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


def _check_schema_version(value: Any) -> int:
    """Accept canonical integer 1 and legacy "v1"; reject everything else.

    Legacy ``"v1"`` is normalised to the canonical integer ``1`` on read so
    persisted R01-R04 records stay readable. New writes always emit ``1``.
    """
    if isinstance(value, bool):
        raise ProfileContractError(
            "INVALID_SCHEMA_VERSION",
            f"schemaVersion must be {SCHEMA_VERSION}, got {value!r}",
        )
    if value is None or value == SCHEMA_VERSION:
        return SCHEMA_VERSION
    if value == LEGACY_SCHEMA_VERSION:
        return SCHEMA_VERSION
    raise ProfileContractError(
        "INVALID_SCHEMA_VERSION",
        f"schemaVersion must be {SCHEMA_VERSION} (legacy {LEGACY_SCHEMA_VERSION!r} accepted on read), got {value!r}",
    )


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


def _dedupe_ci(values: List[str]) -> List[str]:
    """Deduplicate case-insensitively while preserving first-seen order."""
    seen = set()
    out = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


@dataclass
class SearchConfiguration:
    """Canonical Jobsearch ``SearchConfigurationV1`` (six fields).

    This is a nested contract object, not a standalone persisted resource.
    ``to_dict`` emits exactly the six v1 fields (no ``resourceType`` /
    ``schemaVersion``), matching ``additionalProperties: false``.
    """

    skills: str = ""
    target_roles: List[str] = field(default_factory=list)
    city: str = ""
    radius_km: Optional[int] = None
    work_modes: List[str] = field(default_factory=list)
    employment_types: List[str] = field(default_factory=list)

    # Migration diagnostics only; never serialized.
    legacy_incomplete: bool = False
    legacy_preserved: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skills": self.skills,
            "targetRoles": list(self.target_roles),
            "city": self.city,
            "radiusKm": self.radius_km,
            "workModes": list(self.work_modes),
            "employmentTypes": list(self.employment_types),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "SearchConfiguration":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "searchConfig must be an object")
        if strict:
            _check_unknown_fields(data, SEARCH_CONFIGURATION_FIELDS, "SearchConfiguration")
        skills = data.get("skills", "")
        if not isinstance(skills, str):
            raise ProfileContractError("INVALID_FIELD", "searchConfig.skills must be a string")
        city = data.get("city", "")
        if not isinstance(city, str):
            raise ProfileContractError("INVALID_FIELD", "searchConfig.city must be a string")
        radius = data.get("radiusKm")
        if radius is not None:
            if isinstance(radius, bool) or not isinstance(radius, int) or radius not in SEARCH_RADIUS_VALUES:
                raise ProfileContractError(
                    "INVALID_SEARCH_CONFIG",
                    f"searchConfig.radiusKm must be one of {sorted(SEARCH_RADIUS_VALUES)} or null",
                )
        obj = cls(
            skills=skills,
            target_roles=_str_list(data.get("targetRoles", []), "targetRoles"),
            city=city,
            radius_km=radius,
            work_modes=_str_list(data.get("workModes", []), "workModes"),
            employment_types=_str_list(data.get("employmentTypes", []), "employmentTypes"),
        )
        obj.validate()
        return obj

    @classmethod
    def from_legacy_matching_preferences(cls, mp: "MatchingPreferences") -> "SearchConfiguration":
        """Map legacy R03 fields into v1 searchConfig without inventing data.

        Lossless parts: targetRoles <- roles, workModes <- workModes,
        employmentTypes <- allowed subset. Everything that has no v1 slot
        (skills string, radiusKm, extra locations/employment types, query,
        salaryMin, remoteOnly, sources) is preserved in ``legacy_preserved``
        and the object is flagged ``legacy_incomplete``.
        """
        preserved: Dict[str, Any] = {}
        locations = list(mp.locations)
        if len(locations) == 1:
            city = locations[0]
        else:
            city = ""
            if locations:
                preserved["locations"] = locations
        allowed_emp = [e for e in mp.employment_types if e in SEARCH_EMPLOYMENT_TYPES]
        extra_emp = [e for e in mp.employment_types if e not in SEARCH_EMPLOYMENT_TYPES]
        if extra_emp:
            preserved["employmentTypes"] = extra_emp
        if mp.query:
            preserved["query"] = mp.query
        if mp.salary_min is not None:
            preserved["salaryMin"] = mp.salary_min
        if mp.remote_only:
            preserved["remoteOnly"] = True
        if mp.sources:
            preserved["sources"] = list(mp.sources)
        # A legacy record never carried a phrase-string skills value or radius.
        # Leaving them empty/null is the honest representation, not invented data.
        preserved["skillsMissing"] = True
        preserved["radiusMissing"] = True
        return cls(
            skills="",
            target_roles=list(mp.roles),
            city=city,
            radius_km=None,
            work_modes=list(mp.work_modes),
            employment_types=allowed_emp,
            legacy_incomplete=True,
            legacy_preserved=preserved,
        )

    @classmethod
    def from_legacy_cv(cls, profile: Dict[str, Any],
                       search_configuration: Dict[str, Any]) -> "SearchConfiguration":
        """Map the legacy R01 CV dicts into v1 searchConfig without invention."""
        p = profile or {}
        sc = search_configuration or {}
        preserved: Dict[str, Any] = {}

        raw_skills = sc.get("skills", p.get("skills"))
        if isinstance(raw_skills, str):
            skills = raw_skills
        else:
            skills = ""
            if raw_skills is not None:
                preserved["skills"] = raw_skills

        raw_roles = sc.get("targetRoles", p.get("targetRoles")) or []
        if isinstance(raw_roles, list):
            target_roles = list(raw_roles)
        else:
            target_roles = []
            preserved["targetRoles"] = raw_roles

        raw_city = sc.get("city", sc.get("location", p.get("city"))) or ""
        if isinstance(raw_city, str):
            city = raw_city
        else:
            city = ""
            preserved["city"] = raw_city

        raw_radius = sc.get("radiusKm", sc.get("locationRadius", p.get("radiusKm")))
        radius_km = None
        if raw_radius is not None:
            try:
                candidate = int(raw_radius)
            except (TypeError, ValueError):
                candidate = None
            if candidate in SEARCH_RADIUS_VALUES:
                radius_km = candidate
            else:
                preserved["radiusKm"] = raw_radius

        raw_work = sc.get("workModes", p.get("workModes")) or []
        if isinstance(raw_work, list):
            work_modes = list(raw_work)
        else:
            work_modes = []
            preserved["workModes"] = raw_work

        raw_emp = sc.get("employmentTypes", p.get("employmentTypes")) or []
        if isinstance(raw_emp, list):
            allowed_emp = [e for e in raw_emp if e in SEARCH_EMPLOYMENT_TYPES]
            extra_emp = [e for e in raw_emp if e not in SEARCH_EMPLOYMENT_TYPES]
        else:
            allowed_emp = []
            extra_emp = []
            preserved["employmentTypes"] = raw_emp
        if extra_emp:
            preserved["employmentTypes"] = extra_emp

        known = {"skills", "targetRoles", "city", "location", "radiusKm",
                 "locationRadius", "workModes", "employmentTypes"}
        for source in (p, sc):
            for key, value in source.items():
                if key not in known:
                    preserved.setdefault("legacy", {})[key] = value

        return cls(
            skills=skills,
            target_roles=target_roles,
            city=city,
            radius_km=radius_km,
            work_modes=work_modes,
            employment_types=allowed_emp,
            legacy_incomplete=bool(preserved) or not allowed_emp,
            legacy_preserved=preserved,
        )

    def validate(self) -> None:
        if not isinstance(self.skills, str):
            raise ProfileContractError("INVALID_SEARCH_CONFIG", "skills must be a string")
        if not isinstance(self.city, str):
            raise ProfileContractError("INVALID_SEARCH_CONFIG", "city must be a string")
        for name in ("target_roles", "work_modes", "employment_types"):
            if not isinstance(getattr(self, name), list):
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"{name} must be a list")
        if self.radius_km is not None:
            if isinstance(self.radius_km, bool) or not isinstance(self.radius_km, int) \
                    or self.radius_km not in SEARCH_RADIUS_VALUES:
                raise ProfileContractError(
                    "INVALID_SEARCH_CONFIG",
                    f"radiusKm must be one of {sorted(SEARCH_RADIUS_VALUES)} or null",
                )
        for wm in self.work_modes:
            if wm not in {e.value for e in WorkMode}:
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"Unknown workMode: {wm}")
        for et in self.employment_types:
            if et not in SEARCH_EMPLOYMENT_TYPES:
                raise ProfileContractError(
                    "INVALID_SEARCH_CONFIG", f"Unknown employmentType: {et}")
        self.target_roles = _dedupe_ci(self.target_roles)
        self.work_modes = _dedupe_ci(self.work_modes)
        self.employment_types = _dedupe_ci(self.employment_types)


@dataclass
class MatchingPreferences:
    """v1 MatchingPreferencesV1 (three phrase lists).

    The R03-era fields (roles/workModes/employmentTypes/locations/...) are
    kept read-only for migration. ``to_dict`` emits only the three v1 lists,
    matching ``additionalProperties: false``.
    """

    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    excluded_terms: List[str] = field(default_factory=list)

    # Legacy R03 fields, read-only for migration; never emitted in v1.
    roles: List[str] = field(default_factory=list)
    work_modes: List[str] = field(default_factory=list)
    employment_types: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    salary_min: Optional[int] = None
    remote_only: bool = False
    sources: List[str] = field(default_factory=list)
    query: str = ""

    resource_type: str = "MatchingPreferences"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requiredSkills": list(self.required_skills),
            "preferredSkills": list(self.preferred_skills),
            "excludedTerms": list(self.excluded_terms),
        }

    def has_legacy_fields(self) -> bool:
        return bool(
            self.roles or self.work_modes or self.employment_types
            or self.locations or self.salary_min is not None
            or self.remote_only or self.sources or self.query
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "MatchingPreferences":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "MatchingPreferences must be an object")
        if strict:
            _check_unknown_fields(data, MATCHING_PREFERENCES_KNOWN_FIELDS,
                                  "MatchingPreferences")
        _check_resource_type(data.get("resourceType"), "MatchingPreferences")
        _check_schema_version(data.get("schemaVersion"))
        prefs = cls(
            required_skills=_str_list(data.get("requiredSkills", []), "requiredSkills"),
            preferred_skills=_str_list(data.get("preferredSkills", []), "preferredSkills"),
            excluded_terms=_str_list(data.get("excludedTerms", []), "excludedTerms"),
            roles=_str_list(data.get("roles", []), "roles"),
            work_modes=_str_list(data.get("workModes", []), "workModes"),
            employment_types=_str_list(data.get("employmentTypes", []), "employmentTypes"),
            locations=_str_list(data.get("locations", []), "locations"),
            salary_min=_int_or_none(data.get("salaryMin"), "salaryMin"),
            remote_only=bool(data.get("remoteOnly", False)),
            sources=_str_list(data.get("sources", []), "sources"),
            query=str(data.get("query", "") or ""),
        )
        prefs.validate()
        return prefs

    def validate(self) -> None:
        for field_name in ("required_skills", "preferred_skills", "excluded_terms",
                           "roles", "work_modes", "employment_types", "locations",
                           "sources"):
            if not isinstance(getattr(self, field_name), list):
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"{field_name} must be a list")
        for wm in self.work_modes:
            if wm not in {e.value for e in WorkMode}:
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"Unknown workMode: {wm}")
        for et in self.employment_types:
            if et not in {e.value for e in EmploymentType}:
                raise ProfileContractError("INVALID_SEARCH_CONFIG", f"Unknown employmentType: {et}")
        self.required_skills = _dedupe_ci(self.required_skills)
        self.preferred_skills = _dedupe_ci(self.preferred_skills)
        self.excluded_terms = _dedupe_ci(self.excluded_terms)


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
    content_type: Optional[str] = None
    etag: Optional[str] = None
    uploaded_at: Optional[str] = None
    document_id: Optional[str] = None
    processing_status: str = CV_STATUS_PENDING
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
            "processingStatus": self.processing_status,
        }
        if self.content_hash:
            result["contentHash"] = self.content_hash
        if self.content_type:
            result["contentType"] = self.content_type
        if self.etag:
            result["etag"] = self.etag
        if self.uploaded_at:
            result["uploadedAt"] = self.uploaded_at
        if self.document_id:
            result["documentId"] = self.document_id
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
            content_type=_optional_str(data.get("contentType"), "contentType"),
            etag=_optional_str(data.get("etag"), "etag"),
            uploaded_at=_optional_str(data.get("uploadedAt"), "uploadedAt"),
            document_id=_optional_str(data.get("documentId"), "documentId"),
            processing_status=str(data.get("processingStatus", CV_STATUS_PENDING) or CV_STATUS_PENDING),
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
        if self.processing_status not in CV_ALLOWED_STATUSES:
            raise ProfileContractError(
                "INVALID_FIELD",
                f"processingStatus must be one of {sorted(CV_ALLOWED_STATUSES)}, got {self.processing_status!r}",
            )
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
    description: str = ""
    origin: str = CV_PROFILE_ORIGIN
    search_config: SearchConfiguration = field(default_factory=SearchConfiguration)
    # Legacy R01 dicts, read-only for migration; never emitted in v1.
    profile: Dict[str, Any] = field(default_factory=dict)
    search_configuration: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    resource_type: str = "CVSearchProfile"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "searchProfileId": self.search_profile_id,
            "cvId": self.cv_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "origin": self.origin,
            "searchConfig": self.search_config.to_dict(),
        }
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
        origin = data.get("origin", CV_PROFILE_ORIGIN)
        if origin != CV_PROFILE_ORIGIN:
            raise ProfileContractError(
                "INVALID_FIELD", f"origin must be '{CV_PROFILE_ORIGIN}', got {origin!r}")
        profile = data.get("profile") or {}
        search_configuration = data.get("searchConfiguration") or {}
        metadata = dict(data.get("metadata") or {})
        sc_raw = data.get("searchConfig")
        if isinstance(sc_raw, dict):
            search_config = SearchConfiguration.from_dict(sc_raw, strict=strict)
        else:
            search_config = SearchConfiguration.from_legacy_cv(
                profile if isinstance(profile, dict) else {},
                search_configuration if isinstance(search_configuration, dict) else {})
            if search_config.legacy_preserved or profile or search_configuration:
                metadata.setdefault("legacy", {})
                if search_config.legacy_preserved:
                    metadata["legacy"].setdefault(
                        "searchConfig", dict(search_config.legacy_preserved))
                if profile:
                    metadata["legacy"].setdefault("profile", dict(profile))
                if search_configuration:
                    metadata["legacy"].setdefault(
                        "searchConfiguration", dict(search_configuration))
                metadata["legacyIncomplete"] = True
        obj = cls(
            search_profile_id=_require_str(data.get("searchProfileId"), "searchProfileId"),
            cv_id=_require_str(data.get("cvId"), "cvId"),
            user_id=_require_str(data.get("userId"), "userId"),
            tenant_id=_require_str(data.get("tenantId"), "tenantId"),
            name=_require_str(data.get("name"), "name"),
            description=str(data.get("description", "") or ""),
            origin=origin,
            search_config=search_config,
            profile=profile,
            search_configuration=search_configuration,
            metadata=metadata,
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
        if self.origin != CV_PROFILE_ORIGIN:
            raise ProfileContractError(
                "INVALID_FIELD", f"origin must be '{CV_PROFILE_ORIGIN}', got {self.origin!r}")
        if not isinstance(self.search_config, SearchConfiguration):
            raise ProfileContractError("INVALID_FIELD", "searchConfig must be a SearchConfiguration")
        self.search_config.validate()
        if not isinstance(self.profile, dict):
            raise ProfileContractError("INVALID_FIELD", "profile must be an object")
        if not isinstance(self.search_configuration, dict):
            raise ProfileContractError("INVALID_FIELD", "searchConfiguration must be an object")


@dataclass
class ATSCriteria:
    """Canonical Jobsearch ``ATSCriteriaV1`` (optional, restrictive)."""

    schema_version: int = SCHEMA_VERSION
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    excluded_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "requiredSkills": list(self.required_skills),
            "preferredSkills": list(self.preferred_skills),
            "excludedTerms": list(self.excluded_terms),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, strict: bool = True) -> "ATSCriteria":
        if not isinstance(data, dict):
            raise ProfileContractError("INVALID_FIELD", "criteria must be an object")
        if strict:
            _check_unknown_fields(data, ATS_CRITERIA_FIELDS, "ATSCriteria")
        if "schemaVersion" not in data:
            raise ProfileContractError("MISSING_FIELD",
                                       "criteria.schemaVersion is required")
        sv = data.get("schemaVersion")
        if isinstance(sv, bool) or sv != SCHEMA_VERSION:
            raise ProfileContractError(
                "INVALID_SCHEMA_VERSION",
                f"criteria.schemaVersion must be {SCHEMA_VERSION}, got {sv!r}")
        obj = cls(
            schema_version=SCHEMA_VERSION,
            required_skills=_str_list(data.get("requiredSkills", []), "requiredSkills"),
            preferred_skills=_str_list(data.get("preferredSkills", []), "preferredSkills"),
            excluded_terms=_str_list(data.get("excludedTerms", []), "excludedTerms"),
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        if isinstance(self.schema_version, bool) or self.schema_version != SCHEMA_VERSION:
            raise ProfileContractError(
                "INVALID_SCHEMA_VERSION",
                f"criteria.schemaVersion must be {SCHEMA_VERSION}")
        for name in ("required_skills", "preferred_skills", "excluded_terms"):
            if not isinstance(getattr(self, name), list):
                raise ProfileContractError("INVALID_FIELD", f"{name} must be a list")
        self.required_skills = _dedupe_ci(self.required_skills)
        self.preferred_skills = _dedupe_ci(self.preferred_skills)
        self.excluded_terms = _dedupe_ci(self.excluded_terms)


@dataclass
class ATSSearchProfile:
    ats_profile_id: str
    search_profile_id: str
    user_id: str
    tenant_id: str
    name: str
    # cv_id is derived server-side from the parent CVSearchProfile; it is not
    # part of the canonical v1 DTO and may be empty in a standalone fixture.
    cv_id: str = ""
    target_roles: List[str] = field(default_factory=list)
    ats_keywords: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    criteria: Optional[ATSCriteria] = None
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
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        # Persistence shape (includes server-only identity and the internal
        # legacy cv_id). The public v1 serializer strips these.
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "atsProfileId": self.ats_profile_id,
            "searchProfileId": self.search_profile_id,
            "cvId": self.cv_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "name": self.name,
            "targetRoles": list(self.target_roles),
            "skills": list(self.skills),
        }
        if self.criteria is not None:
            result["criteria"] = self.criteria.to_dict()
        if self.ats_keywords:
            result["atsKeywords"] = list(self.ats_keywords)
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
        ats_id = data.get("atsProfileId") or data.get("atsSearchProfileId")
        metadata = dict(data.get("metadata") or {})
        criteria_raw = data.get("criteria")
        criteria: Optional[ATSCriteria] = None
        if criteria_raw is not None:
            if not isinstance(criteria_raw, dict):
                raise ProfileContractError("INVALID_FIELD",
                                           "criteria must be an object or null")
            criteria = ATSCriteria.from_dict(criteria_raw, strict=strict)
        requirements = _str_list(data.get("requirements", []), "requirements")
        preferred = _str_list(data.get("preferredCriteria", []), "preferredCriteria")
        exclusions = _str_list(data.get("exclusions", []), "exclusions")
        if criteria is None and (requirements or preferred or exclusions):
            # Legacy R01 criteria lived in separate lists; preserve them both
            # in the structured criteria and in metadata for lossless migration.
            criteria = ATSCriteria(required_skills=list(requirements),
                                   preferred_skills=list(preferred),
                                   excluded_terms=list(exclusions))
            metadata.setdefault("legacy", {})["criteria"] = {
                "requirements": list(requirements),
                "preferredCriteria": list(preferred),
                "exclusions": list(exclusions),
            }
            metadata["legacyIncomplete"] = True
        obj = cls(
            ats_profile_id=_require_str(ats_id, "atsSearchProfileId"),
            search_profile_id=_require_str(data.get("searchProfileId"), "searchProfileId"),
            cv_id=str(data.get("cvId", "") or ""),
            user_id=_require_str(data.get("userId"), "userId"),
            tenant_id=_require_str(data.get("tenantId"), "tenantId"),
            name=_require_str(data.get("name"), "name"),
            target_roles=_str_list(data.get("targetRoles", []), "targetRoles"),
            ats_keywords=_str_list(data.get("atsKeywords", []), "atsKeywords"),
            skills=_str_list(data.get("skills", []), "skills"),
            criteria=criteria,
            requirements=requirements,
            preferred_criteria=preferred,
            exclusions=exclusions,
            location=_optional_str(data.get("location"), "location"),
            radius=_optional_str(data.get("radius"), "radius"),
            work_mode=_optional_str(data.get("workMode"), "workMode"),
            metadata=metadata,
            created_at=_optional_str(data.get("createdAt"), "createdAt"),
            updated_at=_optional_str(data.get("updatedAt"), "updatedAt"),
            resource_type=rt,
            schema_version=sv,
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        _require_str(self.ats_profile_id, "atsSearchProfileId")
        _require_str(self.search_profile_id, "searchProfileId")
        _require_str(self.user_id, "userId")
        _require_str(self.tenant_id, "tenantId")
        _require_str(self.name, "name")
        if not isinstance(self.cv_id, str):
            raise ProfileContractError("INVALID_FIELD", "cvId must be a string")
        if self.criteria is not None:
            if not isinstance(self.criteria, ATSCriteria):
                raise ProfileContractError("INVALID_FIELD",
                                           "criteria must be an ATSCriteria")
            self.criteria.validate()
        for name in ("target_roles", "skills", "ats_keywords", "requirements",
                     "preferred_criteria", "exclusions"):
            if not isinstance(getattr(self, name), list):
                raise ProfileContractError("INVALID_FIELD", f"{name} must be a list")
        self.target_roles = _dedupe_ci(self.target_roles)
        self.skills = _dedupe_ci(self.skills)


@dataclass
class ManualSearchProfile:
    manual_profile_id: str
    user_id: str
    tenant_id: str
    name: str
    description: str = ""
    origin: str = MANUAL_PROFILE_ORIGIN
    search_config: SearchConfiguration = field(default_factory=SearchConfiguration)
    matching_preferences: MatchingPreferences = field(default_factory=MatchingPreferences)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    resource_type: str = "ManualSearchProfile"
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "resourceType": self.resource_type,
            "schemaVersion": self.schema_version,
            "manualProfileId": self.manual_profile_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "origin": self.origin,
            "searchConfig": self.search_config.to_dict(),
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
        sc_raw = data.get("searchConfig")
        metadata = dict(data.get("metadata") or {})
        if isinstance(sc_raw, dict):
            search_config = SearchConfiguration.from_dict(sc_raw, strict=strict)
        else:
            # Legacy R03 record: derive v1 searchConfig from the old fields and
            # preserve anything without a v1 slot instead of dropping it.
            search_config = SearchConfiguration.from_legacy_matching_preferences(mp)
            metadata.setdefault("legacy", {})
            metadata["legacy"].setdefault(
                "matchingPreferences", {k: v for k, v in (mp_raw or {}).items()
                                        if k in MATCHING_PREFERENCES_LEGACY_FIELDS})
            if search_config.legacy_preserved:
                metadata["legacy"].setdefault(
                    "searchConfig", dict(search_config.legacy_preserved))
            metadata["legacyIncomplete"] = bool(
                search_config.legacy_incomplete or mp.has_legacy_fields())
        origin = data.get("origin", MANUAL_PROFILE_ORIGIN)
        if origin != MANUAL_PROFILE_ORIGIN:
            raise ProfileContractError(
                "INVALID_FIELD",
                f"origin must be '{MANUAL_PROFILE_ORIGIN}', got {origin!r}",
            )
        obj = cls(
            manual_profile_id=_require_str(data.get("manualProfileId"), "manualProfileId"),
            user_id=_require_str(data.get("userId"), "userId"),
            tenant_id=_require_str(data.get("tenantId"), "tenantId"),
            name=_require_str(data.get("name"), "name"),
            description=str(data.get("description", "") or ""),
            origin=origin,
            search_config=search_config,
            matching_preferences=mp,
            metadata=metadata,
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
        if self.origin != MANUAL_PROFILE_ORIGIN:
            raise ProfileContractError(
                "INVALID_FIELD",
                f"origin must be '{MANUAL_PROFILE_ORIGIN}', got {self.origin!r}",
            )
        if not isinstance(self.search_config, SearchConfiguration):
            raise ProfileContractError("INVALID_FIELD", "searchConfig must be a SearchConfiguration")
        self.search_config.validate()
        if not isinstance(self.matching_preferences, MatchingPreferences):
            raise ProfileContractError("INVALID_FIELD", "matchingPreferences must be a MatchingPreferences")
        self.matching_preferences.validate()


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
