"""
Read-only introspection / capability contract (three contexts).

Contract: PROMPT 05-R4/R5 + PROMPT 06-R4 / Gate P12.

Resolves, for exactly one verified context, the POSITIVE effective
capabilities from existing sources only:

    Agent Catalog (P7 central status)
      + user-wide entitlements
      + APIProfile-bound entitlements   (UNION, P02/P04)
      + optional credential scope        (INTERSECT-only, never expands)

Credential+profile boundary is SHARED with P09 verification
(resolve_credential_profile — steps 1-11, no duplication). No second
permission world, no new tables, no writes, no oracle: denied agents
are ABSENT, never explained. The response authorizes nothing —
execution stays server-side authoritative.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class IntrospectionUnavailable(Exception):
    """Infrastructure failure (caller maps to neutral 503)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        from dateutil.parser import parse
        parsed = parse(value)
    except Exception:
        try:
            parsed = datetime.fromisoformat(value)
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _audit(action: str, outcome: str, fields: Dict[str, Any]) -> str:
    audit_ref = uuid.uuid4().hex[:16]
    logger.warning("introspection-audit ref=%s action=%s outcome=%s %s",
                   audit_ref, action, outcome,
                   " ".join(f"{k}={v}" for k, v in sorted(fields.items())))
    return audit_ref


def _min_expiry(*values: Any) -> Optional[str]:
    """Nearest upcoming expiry hint (ISO out, None when unbounded)."""
    moments = []
    for value in values:
        parsed = _parse_time(value)
        if parsed is not None:
            moments.append(parsed)
    if not moments:
        return None
    return min(moments).isoformat()


def _catalog_entry(catalog: Dict[str, Any], agent_id: str
                   ) -> Optional[Dict[str, Any]]:
    raw = (catalog or {}).get(agent_id)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    return {"status": raw}


def _tenant_ok(row: Dict[str, Any], tenant_id: Optional[str]) -> bool:
    """Handler tenant rule: rows without tenantId are tenant-global."""
    return not tenant_id or row.get("tenantId") is None \
        or row.get("tenantId") == tenant_id


def _build_capabilities(entitlements: List[Dict[str, Any]],
                        catalog: Dict[str, Any],
                        scope_filter: Optional[Any],
                        extra_expiry: Optional[Dict[str, Any]],
                        now: datetime) -> List[Dict[str, Any]]:
    """Positive capability list (fail-closed, positive-only)."""
    from agents.ecosystem.agent_status import is_executable_status
    from agents.ecosystem.worker_authorization import is_entitlement_valid

    seen = set()
    capabilities = []
    for row in entitlements or []:
        agent_id = row.get("agentId")
        if not agent_id or agent_id in seen:
            continue
        if scope_filter is not None and agent_id not in scope_filter:
            continue
        if not is_entitlement_valid(row, now):
            continue
        entry = _catalog_entry(catalog, agent_id)
        if entry is None or not is_executable_status(entry.get("status")):
            continue
        seen.add(agent_id)
        capabilities.append({
            "agentId": agent_id,
            "name": entry.get("name", agent_id),
            "capabilities": list(entry.get("capabilities", [])),
            "scopeRestricted": scope_filter is not None,
            "expiresHint": _min_expiry(
                row.get("validUntil"),
                (extra_expiry or {}).get(agent_id)),
        })
    capabilities.sort(key=lambda c: c["agentId"])
    return capabilities


def _display_offers(offer_store: Any) -> List[Dict[str, Any]]:
    """ACTIVE offers only (name/description — prices do not exist)."""
    try:
        items = offer_store.list_offers()
    except AttributeError:
        items = offer_store if isinstance(offer_store, list) else []
    return [{"offerId": o.get("offerId"), "name": o.get("name"),
             "description": o.get("description")}
            for o in items if o.get("status") == "ACTIVE"]


def _base_body(context: str, user_id: Any, tenant_id: Any,
               checked_at: str, selected_by: str,
               request_id: str) -> Dict[str, Any]:
    """Mandatory contract keys (present in EVERY context)."""
    return {"context": context,
            "subject": {"userId": user_id, "tenantId": tenant_id},
            "capabilities": [],
            "validity": {"checkedAt": checked_at},
            "resolution": {"selectedBy": selected_by,
                           "resolvedAt": checked_at,
                           "request": request_id}}


def _sources(profile_store: Any, entitlement_resolver: Any,
             offer_store: Any, catalog: Dict[str, Any],
             credential_store: Any = None) -> Dict[str, Any]:
    """Bundle source handles (handler builds the production set)."""
    return {"profile_store": profile_store,
            "entitlement_resolver": entitlement_resolver,
            "offer_store": offer_store, "catalog": catalog,
            "credential_store": credential_store}


def introspect_human(user_id: str, tenant_id: str,
                     sources: Dict[str, Any],
                     scope_filter: Optional[Any] = None,
                     now: Optional[datetime] = None,
                     request_id: Optional[str] = None
                     ) -> Tuple[int, Dict[str, Any]]:
    """Human/JWT context: own profiles + user-wide capabilities."""
    from agents.ecosystem import api_profiles

    profile_store = sources["profile_store"]
    entitlement_resolver = sources["entitlement_resolver"]
    offer_store = sources["offer_store"]
    catalog = sources["catalog"]
    moment = now or _utcnow()
    checked_at = moment.isoformat()
    req = request_id or "-"
    if not user_id or not tenant_id:
        _audit("introspect", "denied",
               {"context": "human", "request": req})
        return 401, {"error": "Unauthorized"}

    actor = {"userId": user_id, "tenantId": tenant_id, "groups": []}
    allowed = [{
        "apiProfileId": p.get("apiProfileId"), "name": p.get("name"),
        "status": p.get("status")}
        for p in api_profiles.list_profiles(profile_store, actor)
        if api_profiles.effective_status(p) == "ACTIVE"]
    try:
        rows = entitlement_resolver.find_entitlements(user_id)
    except Exception as exc:
        raise IntrospectionUnavailable(str(exc)) from exc
    mine = [r for r in rows
            if r.get("apiProfileId") is None and _tenant_ok(r, tenant_id)]
    body = _base_body("human", user_id, tenant_id, checked_at,
                      "default", req)
    body["allowedProfiles"] = sorted(
        allowed, key=lambda p: p["apiProfileId"] or "")
    body["capabilities"] = _build_capabilities(mine, catalog,
                                               scope_filter, None, moment)
    body["offers"] = _display_offers(offer_store)
    _audit("introspect", "success",
           {"context": "human", "tenant": tenant_id,
            "profiles": len(allowed),
            "capabilities": len(body["capabilities"]), "request": req})
    return 200, body


def introspect_profile(user_id: str, tenant_id: str,
                       sources: Dict[str, Any],
                       selection_hint: Optional[str] = None,
                       scope_filter: Optional[Any] = None,
                       now: Optional[datetime] = None,
                       request_id: Optional[str] = None
                       ) -> Tuple[int, Dict[str, Any]]:
    """APIProfile context (P10 resolution reused, never reimplemented)."""
    from agents.ecosystem import api_profiles

    profile_store = sources["profile_store"]
    entitlement_resolver = sources["entitlement_resolver"]
    offer_store = sources["offer_store"]
    catalog = sources["catalog"]
    moment = now or _utcnow()
    checked_at = moment.isoformat()
    req = request_id or "-"
    if not user_id or not tenant_id:
        _audit("introspect", "denied",
               {"context": "profile", "request": req})
        return 401, {"error": "Unauthorized"}
    actor = {"userId": user_id, "tenantId": tenant_id, "groups": []}
    profile, info = api_profiles.resolve_selection(
        profile_store, actor, selection_hint, req)
    if profile is None:
        _audit("introspect", "denied",
               {"context": "profile", "tenant": tenant_id, "request": req})
        return 404, {"error": "Not found"}
    try:
        rows = entitlement_resolver.find_entitlements(user_id)
    except Exception as exc:
        raise IntrospectionUnavailable(str(exc)) from exc
    pid = profile.get("apiProfileId")
    scoped = [r for r in rows
              if _tenant_ok(r, tenant_id)
              and ((r.get("apiProfileId") or None) == pid
                   or r.get("apiProfileId") is None)]
    extra = {}
    if profile.get("expiresAt"):
        for r in scoped:
            if r.get("agentId"):
                extra[r.get("agentId")] = profile.get("expiresAt")
    body = _base_body("profile", user_id, tenant_id, checked_at,
                      info.get("type", "explicit"), req)
    body["profile"] = {
        "apiProfileId": pid, "name": profile.get("name"),
        "status": profile.get("status"),
        "clientRef": profile.get("clientRef"),
        "expiresAt": profile.get("expiresAt"),
        "offerRefs": sorted({r.get("offerId") for r in scoped
                             if r.get("offerId")})}
    body["capabilities"] = _build_capabilities(
        scoped, catalog, scope_filter, extra, moment)
    body["validity"]["profileExpiresAt"] = profile.get("expiresAt")
    body["offers"] = _display_offers(offer_store)
    _audit("introspect", "success",
           {"context": "profile", "tenant": tenant_id,
            "apiProfileId": pid,
            "capabilities": len(body["capabilities"]), "request": req})
    return 200, body


def introspect_credential(bearer: str,
                          sources: Dict[str, Any],
                          selection_hint: Optional[str] = None,
                          scope_filter: Optional[Any] = None,
                          now: Optional[datetime] = None,
                          request_id: Optional[str] = None
                          ) -> Tuple[int, Dict[str, Any]]:
    """Credential context (P09 shared boundary reused, §11 intact)."""
    from agents.ecosystem.credentials import (
        CredentialStoreUnavailable,
        _Denied,
        resolve_credential_profile,
    )

    profile_store = sources["profile_store"]
    entitlement_resolver = sources["entitlement_resolver"]
    offer_store = sources["offer_store"]
    credential_store = sources["credential_store"]
    catalog = sources["catalog"]
    moment = now or _utcnow()
    checked_at = moment.isoformat()
    req = request_id or "-"
    try:
        meta, profile = resolve_credential_profile(
            bearer, credential_store, profile_store, moment,
            {"request": req})
    except CredentialStoreUnavailable as exc:
        raise IntrospectionUnavailable(str(exc)) from exc
    except _Denied as denied:
        # Neutral mapping, same as verification (no oracle).
        status = {"UNAUTHORIZED": 401, "FORBIDDEN": 403}.get(
            denied.outcome.value, 403)
        _audit("introspect", "denied",
               {"context": "credential", "request": req})
        return status, {"error": "Unauthorized"
                        if status == 401 else "Forbidden"}
    pid = profile.get("apiProfileId")
    if selection_hint and selection_hint != pid:
        _audit("introspect", "denied",
               {"context": "credential", "request": req})
        return 403, {"error": "Forbidden"}
    subject = {"userId": profile.get("ownerUserId"),
               "tenantId": profile.get("tenantId")}
    try:
        rows = entitlement_resolver.find_entitlements(subject["userId"])
    except Exception as exc:
        raise IntrospectionUnavailable(str(exc)) from exc
    scoped = [r for r in rows
              if _tenant_ok(r, subject["tenantId"])
              and ((r.get("apiProfileId") or None) == pid
                   or r.get("apiProfileId") is None)]
    body = _base_body("credential", subject["userId"],
                      subject["tenantId"], checked_at, "credential", req)
    body["profile"] = {
        "apiProfileId": pid, "name": profile.get("name"),
        "status": profile.get("status"),
        "clientRef": profile.get("clientRef"),
        "expiresAt": profile.get("expiresAt"),
        "offerRefs": sorted({r.get("offerId") for r in scoped
                             if r.get("offerId")})}
    body["capabilities"] = _build_capabilities(
        scoped, catalog, scope_filter,
        {r.get("agentId"): meta.get("expiresAt") for r in scoped},
        moment)
    body["validity"]["credentialExpiresAt"] = meta.get("expiresAt")
    body["validity"]["profileExpiresAt"] = profile.get("expiresAt")
    body["credential"] = {"credentialId": meta.get("credentialId"),
                          "expiresAt": meta.get("expiresAt")}
    body["offers"] = _display_offers(offer_store)
    _audit("introspect", "success",
           {"context": "credential", "tenant": subject["tenantId"],
            "apiProfileId": pid,
            "credentialId": meta.get("credentialId"),
            "capabilities": len(body["capabilities"]), "request": req})
    return 200, body


__all__ = [
    "IntrospectionUnavailable",
    "introspect_human",
    "introspect_profile",
    "introspect_credential",
]
