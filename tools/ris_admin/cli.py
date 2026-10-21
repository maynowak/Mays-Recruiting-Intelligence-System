#!/usr/bin/env python3
"""RIS Admin CLI foundation.

Generic administrative CLI for Mays-RIS partner, APIProfile, credential and entitlement management.
Reuses existing agents.ecosystem modules. No AWS mutations in dry-run mode.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

try:
    import boto3
except Exception:
    boto3 = None  # type: ignore

def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2))


def _deny_message(message: str) -> None:
    print(json.dumps({"error": message}), file=sys.stderr)


def _deny(exc: Exception) -> int:
    """Neutral refusal. Never echoes a secret or an internal traceback."""
    _deny_message(str(exc))
    return 1


def _domain_error(operation: str, exc: Exception) -> int:
    """Map a RIS domain refusal onto the CLI without leaking internals."""
    from agents.ecosystem.credentials import (
        CredentialConflict,
        CredentialNotFound,
        CredentialStateConflict,
        UnauthorizedManagementAttempt,
    )
    if isinstance(exc, UnauthorizedManagementAttempt):
        _deny_message("not authorized to %s credentials" % operation)
        return 1
    if isinstance(exc, CredentialNotFound):
        _deny_message("credential not found")
        return 1
    if isinstance(exc, (CredentialConflict, CredentialStateConflict)):
        _deny_message("credential state conflict: %s" % exc)
        return 1
    _deny_message("credential %s failed (%s)"
                  % (operation, type(exc).__name__))
    return 1


def credops_error():
    from ris_admin.credentials import AdminAuthorizationError

    return (AdminAuthorizationError,)


def _credential_ops():
    import ris_admin.credentials as ops
    return ops


def _apiprofile_ops():
    import ris_admin.apiprofiles as ops
    return ops


def _offer_ops():
    import ris_admin.offers as ops
    return ops


def _apiprofile_error(operation: str, exc: Exception) -> int:
    """Map a RIS APIProfile refusal onto the CLI without leaking internals."""
    from agents.ecosystem.api_profiles import (
        InvalidProfileTransition,
        ProfileConflict,
        ProfileNotFound,
        UnauthorizedProfileAction,
    )
    if isinstance(exc, UnauthorizedProfileAction):
        _deny_message("not authorized to %s APIProfiles" % operation)
        return 1
    if isinstance(exc, ProfileNotFound):
        _deny_message("APIProfile not found")
        return 1
    if isinstance(exc, ProfileConflict):
        _deny_message("APIProfile conflict: %s" % exc)
        return 1
    if isinstance(exc, InvalidProfileTransition):
        _deny_message("APIProfile transition refused: %s" % exc)
        return 1
    if isinstance(exc, ValueError):
        _deny_message(str(exc))
        return 1
    _deny_message("APIProfile %s failed (%s)"
                  % (operation, type(exc).__name__))
    return 1


def _offer_error(operation: str, exc: Exception) -> int:
    """Map a RIS offer refusal onto the CLI without leaking internals."""
    from agents.ecosystem.offers import (
        EntitlementNotFound,
        GrantConflict,
        GrantDenied,
        OfferConflict,
        OfferNotFound,
        UnauthorizedOfferAction,
    )
    if isinstance(exc, UnauthorizedOfferAction):
        _deny_message("not authorized to %s offers" % operation)
        return 1
    if isinstance(exc, (OfferNotFound, EntitlementNotFound)):
        _deny_message("Offer not found")
        return 1
    if isinstance(exc, (OfferConflict, GrantConflict)):
        _deny_message("Offer conflict: %s" % exc)
        return 1
    if isinstance(exc, GrantDenied):
        # Admin-target problem (unknown agent, inactive offer, unusable
        # profile, bad window). Neutral message, but the honest reason.
        _deny_message(str(exc) or "Grant refused")
        return 1
    if isinstance(exc, ValueError):
        _deny_message(str(exc))
        return 1
    _deny_message("Offer %s failed (%s)"
                  % (operation, type(exc).__name__))
    return 1


def _caller_arn(args) -> str:
    """Authenticated AWS principal. Identity only - not authorization.

    STS proves who is calling. Whether that principal is a RIS administrator
    is decided separately by resolve_admin_authorization.
    """
    region = args.region or os.getenv("AWS_REGION", "eu-central-1")
    session_kwargs: Dict[str, Any] = {"region_name": region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.session.Session(**session_kwargs)
    return session.client("sts").get_caller_identity().get("Arn")

def cmd_doctor(args: argparse.Namespace) -> int:
    """Inspect AWS identity and required RIS resources."""
    region = args.region or os.getenv("AWS_REGION", "eu-central-1")
    profile = args.profile
    session_kwargs: Dict[str, Any] = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    try:
        if boto3 is None:
            raise RuntimeError("boto3 not available")
        session = boto3.session.Session(**session_kwargs)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        account = identity.get("Account")
        arn = identity.get("Arn")
    except Exception as e:
        print(f"AWS identity check failed: {e}", file=sys.stderr)
        return 1

    report = {
        "profile": profile or "default",
        "region": region,
        "account": account,
        "arn": arn,
        "required_tables": [
            "work-items",
            "agent-state",
            "user-profile",
            "agent-catalog",
            "entitlements",
            "api-profiles",
            "credentials",
        ],
        "notes": "Dry-run diagnostic only. Actual table existence check requires IAM permissions."
    }
    _print_json(report)
    return 0

def _get_dynamo_client(args: argparse.Namespace):
    if boto3 is None:
        raise RuntimeError("boto3 not available")
    region = args.region or os.getenv("AWS_REGION", "eu-central-1")
    session_kwargs = {"region_name": region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.session.Session(**session_kwargs)
    return session.client("dynamodb")

def _table_name(args: argparse.Namespace, suffix: str) -> str:
    project = os.getenv("RIS_PROJECT_NAME", "mays-ris")
    env = args.environment or os.getenv("RIS_ENVIRONMENT", "dev")
    return f"{project}-{env}-{suffix}"

def cmd_partner_list(args: argparse.Namespace) -> int:
    try:
        client = _get_dynamo_client(args)
        table = _table_name(args, "partner-applications")
        resp = client.scan(TableName=table, Limit=100)
        items = resp.get("Items", [])
        def unmarshal(it):
            return {k: list(v.values())[0] for k,v in it.items()}
        apps = [unmarshal(i) for i in items]
        _print_json({"applications": apps, "table": table})
        return 0
    except Exception as e:
        print(f"partner list failed: {e}", file=sys.stderr)
        return 1

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ris-admin", description="Mays-RIS Administration CLI")
    parser.add_argument("--profile", help="AWS profile")
    parser.add_argument("--region", help="AWS region")
    parser.add_argument("--environment", help="RIS environment")
    parser.add_argument("--dry-run", action="store_true", help="Do not perform mutations")
    parser.add_argument("--output", choices=["json"], default="json", help="Output format")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Inspect environment")
    doctor.set_defaults(func=cmd_doctor)

    partner = sub.add_parser("partner", help="Partner management")
    partner_sub = partner.add_subparsers(dest="partner_cmd", required=True)

    def _registry():
        sys.path.insert(0, os.getcwd())
        import agents.ecosystem.partner_registry as reg
        return reg

    def _partner_cmd_list(args):
        if args.dry_run:
            _print_json({"dry_run": True})
            return 0
        reg = _registry()
        rows = reg.list_partner_applications(
            table_name=_table_name(args, "partner-applications"))
        _print_json({"applications": rows})
        return 0

    partner_sub.add_parser("list", help="List partners").set_defaults(
        func=_partner_cmd_list)

    def _partner_cmd_show(args):
        reg = _registry()
        client = _get_dynamo_client(args)
        resp = client.get_item(
            TableName=_table_name(args, "partner-applications"),
            Key={"applicationId": {"S": args.applicationId}})
        item = resp.get("Item")
        if not item or reg._is_reservation(item):
            _print_json({"error": "not found"})
            return 1
        _print_json({k: list(v.values())[0] for k, v in item.items()})
        return 0

    show_p = partner_sub.add_parser("show", help="Show partner")
    show_p.add_argument("applicationId")
    show_p.set_defaults(func=_partner_cmd_show)

    def _partner_cmd_create(args):
        reg = _registry()
        if args.dry_run:
            _print_json({"dry_run": True,
                         "action": "create",
                         "applicationId": args.applicationId})
            return 0
        client = _get_dynamo_client(args)
        try:
            res = reg.create_partner_application(
                application_id=args.applicationId,
                cognito_client_id=args.cognitoClientId,
                api_profile_id=args.apiProfileId,
                tenant_id=args.tenantId,
                table_name=_table_name(args, "partner-applications"),
                dynamodb_client=client,
            )
            _print_json(res)
            return 0
        except Exception as e:
            print(f"partner create failed: {e}", file=sys.stderr)
            return 1

    create_p = partner_sub.add_parser("create", help="Create partner")
    create_p.add_argument("applicationId")
    create_p.add_argument("--cognitoClientId", required=True)
    create_p.add_argument("--apiProfileId", required=True)
    create_p.add_argument("--tenantId", required=True)
    create_p.set_defaults(func=_partner_cmd_create)

    def _partner_cmd_validate(args):
        reg = _registry()
        client = _get_dynamo_client(args)
        table = _table_name(args, "partner-applications")
        resp = client.get_item(TableName=table,
                               Key={"applicationId": {"S": args.applicationId}})
        item = resp.get("Item")
        if not item or reg._is_reservation(item):
            _print_json({"valid": False, "reason": "not found"})
            return 1
        rec = {k: list(v.values())[0] for k, v in item.items()}
        problems = []
        if rec.get("status") != "ACTIVE":
            problems.append(f"status={rec.get('status')}")
        for field in ("cognitoClientId", "tenantId", "apiProfileId"):
            if not rec.get(field):
                problems.append(f"missing {field}")
        _print_json({"valid": not problems, "problems": problems,
                     "record": rec})
        return 0 if not problems else 1

    val_p = partner_sub.add_parser("validate", help="Validate partner")
    val_p.add_argument("applicationId")
    val_p.set_defaults(func=_partner_cmd_validate)

    def _partner_cmd_deactivate(args):
        if args.dry_run:
            _print_json({"dry_run": True,
                         "action": "deactivate",
                         "applicationId": args.applicationId})
            return 0
        reg = _registry()
        try:
            res = reg.deactivate_partner_application(
                args.applicationId,
                table_name=_table_name(args, "partner-applications"),
                dynamodb_client=_get_dynamo_client(args),
            )
            _print_json(res)
            return 0
        except Exception as e:
            print(f"partner deactivate failed: {e}", file=sys.stderr)
            return 1

    deact_p = partner_sub.add_parser("deactivate", help="Deactivate partner")
    deact_p.add_argument("applicationId")
    deact_p.set_defaults(func=_partner_cmd_deactivate)
    
    ap = sub.add_parser("apiprofile", help="APIProfile management")
    ap_sub = ap.add_subparsers(dest="apiprofile_cmd", required=True)

    off = sub.add_parser("offer", help="Offer and entitlement grant")
    off_sub = off.add_subparsers(dest="offer_cmd", required=True)

    cred = sub.add_parser("credential", help="Credential management")
    cred_sub = cred.add_subparsers(dest="credential_cmd", required=True)

    def _actor(args, operation):
        """Derive the RIS actor contract from the authenticated AWS principal.

        There is intentionally no --actor-role flag: a CLI switch cannot grant
        administrator rights. Without an authorization file this raises and
        the operation fails closed.
        """
        credops = _credential_ops()
        try:
            principal_arn = _caller_arn(args)
        except credops_error() as exc:
            raise
        except Exception as exc:
            # An unavailable or misconfigured AWS identity must be a neutral
            # refusal, never an unhandled traceback.
            raise credops.AdminAuthorizationError(
                "AWS identity could not be established (%s); refusing to %s"
                % (type(exc).__name__, operation))
        if not principal_arn:
            raise credops.AdminAuthorizationError(
                "AWS identity could not be established; refusing to %s"
                % operation)
        return credops.resolve_admin_authorization(
            getattr(args, "authorization_file", None)
            or os.getenv("RIS_ADMIN_AUTHORIZATION_FILE"),
            principal_arn, operation)

    # ------------------------------------------------------------------
    # APIProfile management (existing domain lifecycle, operator
    # authorization file - the same trust anchor the credential commands
    # use). The CLI cannot set a tenant: the tenant always comes from the
    # authorization mapping, so a profile can never be written into a
    # tenant the operator is not authorized for.
    # ------------------------------------------------------------------

    def _aprof_cmd_create(args):
        ops = _apiprofile_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "apiprofile create",
                         "name": args.name,
                         "description": args.description,
                         "note": "no APIProfile was created"})
            return 0
        try:
            actor = _actor(args, "create an APIProfile")
        except credops_error() as exc:
            return _deny(exc)
        try:
            item = ops.create(
                name=args.name,
                actor=actor,
                description=args.description,
                target_owner=args.target_owner,
                idempotency_key=args.idempotency_key,
            )
        except Exception as exc:
            return _apiprofile_error("create", exc)
        _print_json(item)
        return 0

    ap_create = ap_sub.add_parser("create", help="Create an APIProfile")
    ap_create.add_argument("--name", required=True)
    ap_create.add_argument("--description", default=None)
    ap_create.add_argument("--target-owner", default=None,
                           help="Admin only: create the profile for another "
                                "owner (defaults to the operator principal)")
    ap_create.add_argument("--idempotency-key", default=None)
    ap_create.add_argument("--authorization-file", default=None)
    ap_create.set_defaults(func=_aprof_cmd_create)

    def _aprof_cmd_activate(args):
        ops = _apiprofile_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "apiprofile activate",
                         "apiProfileId": args.apiProfileId,
                         "note": "no APIProfile was changed"})
            return 0
        try:
            actor = _actor(args, "activate an APIProfile")
        except credops_error() as exc:
            return _deny(exc)
        try:
            item = ops.activate(api_profile_id=args.apiProfileId,
                                actor=actor, reason=args.reason)
        except Exception as exc:
            return _apiprofile_error("activate", exc)
        _print_json(item)
        return 0

    ap_activate = ap_sub.add_parser("activate",
                                    help="Activate an APIProfile (PENDING -> ACTIVE)")
    ap_activate.add_argument("--apiProfileId", required=True)
    ap_activate.add_argument("--reason", default=None)
    ap_activate.add_argument("--authorization-file", default=None)
    ap_activate.set_defaults(func=_aprof_cmd_activate)

    def _aprof_cmd_show(args):
        ops = _apiprofile_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "apiprofile show",
                         "apiProfileId": args.apiProfileId})
            return 0
        try:
            actor = _actor(args, "show an APIProfile")
        except credops_error() as exc:
            return _deny(exc)
        try:
            item = ops.show(api_profile_id=args.apiProfileId, actor=actor,
                            reason=args.reason)
        except Exception as exc:
            return _apiprofile_error("show", exc)
        if item is None:
            _print_json({"error": "Not found"})
            return 1
        _print_json(item)
        return 0

    ap_show = ap_sub.add_parser("show", help="Show an APIProfile")
    ap_show.add_argument("--apiProfileId", required=True)
    ap_show.add_argument("--reason", default=None)
    ap_show.add_argument("--authorization-file", default=None)
    ap_show.set_defaults(func=_aprof_cmd_show)

    def _aprof_cmd_list(args):
        ops = _apiprofile_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "apiprofile list"})
            return 0
        try:
            actor = _actor(args, "list APIProfiles")
        except credops_error() as exc:
            return _deny(exc)
        try:
            rows = ops.list_all(actor, reason=args.reason)
        except Exception as exc:
            return _apiprofile_error("list", exc)
        _print_json({"items": rows})
        return 0

    ap_list = ap_sub.add_parser("list", help="List APIProfiles")
    ap_list.add_argument("--reason", default=None)
    ap_list.add_argument("--authorization-file", default=None)
    ap_list.set_defaults(func=_aprof_cmd_list)

    # ------------------------------------------------------------------
    # Offer / Entitlement grant (existing offer domain, same operator
    # authorization file). The CLI cannot set a tenant: the tenant always
    # comes from the authorization mapping, so a grant can never be
    # written into a tenant the operator is not authorized for. The
    # target of a grant is the CONSUMER (Cognito sub).
    # ------------------------------------------------------------------

    def _offer_cmd_create(args):
        ops = _offer_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "offer create",
                         "name": args.name,
                         "agentIds": args.agent_ids,
                         "description": args.description,
                         "status": args.status,
                         "note": "no offer was created"})
            return 0
        try:
            actor = _actor(args, "create an offer")
        except credops_error() as exc:
            return _deny(exc)
        try:
            item = ops.create(
                name=args.name,
                actor=actor,
                agent_ids=list(args.agent_ids),
                description=args.description,
                status=args.status,
            )
        except Exception as exc:
            return _offer_error("create", exc)
        _print_json(item)
        return 0

    off_create = off_sub.add_parser("create", help="Create an offer")
    off_create.add_argument("--name", required=True)
    off_create.add_argument("--agent-ids", required=True, nargs="+",
                            help="Agent ids the offer grants (must exist in "
                                 "the catalog and be executable)")
    off_create.add_argument("--description", default=None)
    off_create.add_argument("--status", default="ACTIVE",
                            choices=["ACTIVE", "INACTIVE"])
    off_create.add_argument("--authorization-file", default=None)
    off_create.set_defaults(func=_offer_cmd_create)

    def _offer_cmd_grant(args):
        ops = _offer_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "offer grant",
                         "offerId": args.offerId,
                         "userId": args.user_id,
                         "scope": args.scope,
                         "validFrom": args.valid_from,
                         "validUntil": args.valid_until,
                         "note": "no entitlement was written"})
            return 0
        try:
            actor = _actor(args, "grant an offer")
        except credops_error() as exc:
            return _deny(exc)
        try:
            out = ops.grant(
                offer_id=args.offerId,
                actor=actor,
                target_user_id=args.user_id,
                valid_from=args.valid_from,
                valid_until=args.valid_until,
                reason=args.reason,
                scope=args.scope,
                api_profile_id=args.apiProfileId,
                idempotency_key=args.idempotency_key,
            )
        except Exception as exc:
            return _offer_error("grant", exc)
        _print_json(out)
        return 0

    off_grant = off_sub.add_parser("grant",
                                   help="Grant an offer to one consumer")
    off_grant.add_argument("--offerId", required=True)
    off_grant.add_argument("--user-id", required=True,
                           help="Consumer id (Cognito sub) that receives the "
                                "entitlement")
    off_grant.add_argument("--reason", required=True,
                           help="Mandatory audit reason for the grant")
    off_grant.add_argument("--valid-from", required=True,
                           help="Start of the validity window (ISO-8601)")
    off_grant.add_argument("--valid-until", required=True,
                           help="End of the validity window (ISO-8601)")
    off_grant.add_argument("--scope", default="USER",
                           choices=["USER", "APIPROFILE"])
    off_grant.add_argument("--apiProfileId", default=None,
                           help="Only for scope APIPROFILE")
    off_grant.add_argument("--idempotency-key", default=None)
    off_grant.add_argument("--authorization-file", default=None)
    off_grant.set_defaults(func=_offer_cmd_grant)

    def _offer_cmd_list(args):
        ops = _offer_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "offer list"})
            return 0
        try:
            actor = _actor(args, "list offers")
        except credops_error() as exc:
            return _deny(exc)
        try:
            rows = ops.list_all(actor, include_inactive=args.include_inactive)
        except Exception as exc:
            return _offer_error("list", exc)
        _print_json({"items": rows})
        return 0

    off_list = off_sub.add_parser("list", help="List offers")
    off_list.add_argument("--include-inactive", action="store_true")
    off_list.add_argument("--authorization-file", default=None)
    off_list.set_defaults(func=_offer_cmd_list)

    def _offer_cmd_show(args):
        ops = _offer_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "offer show",
                         "offerId": args.offerId})
            return 0
        try:
            item = ops.show(args.offerId)
        except Exception as exc:
            return _offer_error("show", exc)
        if item is None:
            _print_json({"error": "Not found"})
            return 1
        _print_json(item)
        return 0

    off_show = off_sub.add_parser("show", help="Show one offer")
    off_show.add_argument("--offerId", required=True)
    off_show.add_argument("--authorization-file", default=None)
    off_show.set_defaults(func=_offer_cmd_show)

    def _cred_list(args):
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "credential list"})
            return 0
        try:
            actor = _actor(args, "list credentials")
        except credops_error() as exc:
            return _deny(exc)
        try:
            rows = _credential_ops().list_all(
                actor, api_profile_id=args.apiProfileId, reason=args.reason)
        except Exception as exc:
            return _domain_error("list", exc)
        _print_json({"items": rows})
        return 0

    list_c = cred_sub.add_parser("list", help="List credentials")
    list_c.add_argument("--apiProfileId", default=None)
    list_c.add_argument("--reason", default=None)
    list_c.add_argument("--authorization-file", default=None)
    list_c.set_defaults(func=_cred_list)

    def _cred_show(args):
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "credential show",
                         "credentialId": args.credentialId})
            return 0
        try:
            actor = _actor(args, "show a credential")
        except credops_error() as exc:
            return _deny(exc)
        try:
            meta = _credential_ops().show(args.credentialId, actor,
                                          reason=args.reason)
        except Exception as exc:
            return _domain_error("show", exc)
        if meta is None:
            # Neutral: unknown and unauthorized are indistinguishable.
            _print_json({"error": "Not found"})
            return 1
        _print_json(meta)
        return 0

    show_c = cred_sub.add_parser("show", help="Show credential metadata")
    show_c.add_argument("credentialId")
    show_c.add_argument("--reason", default=None)
    show_c.add_argument("--authorization-file", default=None)
    show_c.set_defaults(func=_cred_show)

    def _cred_issue(args):
        ops = _credential_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "credential issue",
                         "apiProfileId": args.apiProfileId,
                         "expiresAt": args.expiresAt,
                         "outputFile": args.output_file,
                         "note": "no credential was created"})
            return 0
        if not args.output_file:
            _deny_message("--output-file is required; secrets are never "
                          "printed")
            return 1
        try:
            actor = _actor(args, "issue a credential")
        except credops_error() as exc:
            return _deny(exc)
        try:
            out = ops.issue(
                api_profile_id=args.apiProfileId,
                expires_at=args.expiresAt,
                actor=actor,
                output_path=args.output_file,
                label=args.label,
                reason=args.reason,
                idempotency_key=args.idempotency_key,
            )
        except ops.CredentialOutputFailed as exc:
            # The credential EXISTS. Never claim a rollback, never re-issue,
            # never reveal the secret.
            _print_json({
                "outcome": "CREDENTIAL_CREATED_OUTPUT_FAILED",
                "credentialId": exc.credential_id,
                "detail": exc.detail,
                "recovery": "the secret was never persisted and cannot be "
                            "recovered; revoke this credential and issue a "
                            "new one deliberately",
            })
            return 1
        except ops.AdminAuthorizationError as exc:
            return _deny(exc)
        except ops.OutputDestinationError as exc:
            _deny_message(str(exc))
            return 1
        except ValueError as exc:
            _deny_message(str(exc))
            return 1
        except Exception as exc:
            return _domain_error("issue", exc)
        # The secret is never part of this payload.
        _print_json(out)
        return 0

    issue_c = cred_sub.add_parser("issue", help="Issue a credential")
    issue_c.add_argument("--apiProfileId", required=True)
    issue_c.add_argument("--expiresAt", required=True)
    issue_c.add_argument("--output-file", required=True,
                         help="Secure destination for the once-only secret")
    issue_c.add_argument("--label", default=None)
    issue_c.add_argument("--reason", default=None)
    issue_c.add_argument("--idempotency-key", default=None)
    issue_c.add_argument("--authorization-file", default=None)
    issue_c.set_defaults(func=_cred_issue)

    def _cred_revoke(args):
        ops = _credential_ops()
        if args.dry_run:
            _print_json({"dryRun": True, "operation": "credential revoke",
                         "credentialId": args.credentialId})
            return 0
        if not args.yes:
            _deny_message("revocation is terminal; pass --yes to confirm")
            return 1
        try:
            actor = _actor(args, "revoke a credential")
        except credops_error() as exc:
            return _deny(exc)
        try:
            out = ops.revoke(args.credentialId, actor, reason=args.reason)
        except ops.AdminAuthorizationError as exc:
            return _deny(exc)
        except Exception as exc:
            return _domain_error("revoke", exc)
        _print_json(out)
        return 0

    revoke_c = cred_sub.add_parser("revoke", help="Revoke a credential")
    revoke_c.add_argument("credentialId")
    revoke_c.add_argument("--yes", action="store_true",
                          help="Confirm the terminal revocation")
    revoke_c.add_argument("--reason", default=None)
    revoke_c.add_argument("--authorization-file", default=None)
    revoke_c.set_defaults(func=_cred_revoke)

    ent = sub.add_parser("entitlement", help="Entitlement management")
    ent.add_subparsers(dest="entitlement_cmd", required=True)

    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func:
        return func(args)
    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())
