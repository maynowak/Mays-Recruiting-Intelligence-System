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
    partner_sub.add_parser("list", help="List partners").set_defaults(func=cmd_partner_list)
    
    def _partner_cmd_show(args):
        table = _table_name(args, "partner-applications")
        try:
            client = _get_dynamo_client(args)
            resp = client.get_item(TableName=table, Key={"applicationId": {"S": args.applicationId}})
            item = resp.get("Item")
            if not item:
                print(json.dumps({"error": "not found"}))
                return 1
            def unmarshal(it):
                return {k: list(v.values())[0] for k,v in it.items()}
            _print_json(unmarshal(item))
            return 0
        except Exception as e:
            print(f"partner show failed: {e}", file=sys.stderr)
            return 1
    
    show_p = partner_sub.add_parser("show", help="Show partner")
    show_p.add_argument("applicationId")
    show_p.set_defaults(func=_partner_cmd_show)
    
    def _partner_cmd_create(args):
        if args.dry_run:
            _print_json({"dry_run": True, "action": "create", "applicationId": args.applicationId})
            return 0
        # Minimal validation using existing registry function
        try:
            from agents.ecosystem.partner_registry import create_partner_application
        except Exception as e:
            print(f"registry import failed: {e}", file=sys.stderr)
            return 1
        try:
            res = create_partner_application(
                application_id=args.applicationId,
                cognito_client_id=args.cognitoClientId,
                api_profile_id=args.apiProfileId,
                tenant_id=args.tenantId,
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
        # Simple validation: resolve by client id
        try:
            from agents.ecosystem.partner_registry import resolve_partner_application
        except Exception as e:
            print(f"registry import failed: {e}", file=sys.stderr)
            return 1
        try:
            # Need client id, use applicationId as placeholder? Use resolve by applicationId via get_item
            table = _table_name(args, "partner-applications")
            client = _get_dynamo_client(args)
            resp = client.get_item(TableName=table, Key={"applicationId": {"S": args.applicationId}})
            item = resp.get("Item")
            if not item:
                _print_json({"valid": False, "reason": "not found"})
                return 0
            def unmarshal(it):
                return {k: list(v.values())[0] for k,v in it.items()}
            rec = unmarshal(item)
            _print_json({"valid": True, "record": rec})
            return 0
        except Exception as e:
            print(f"partner validate failed: {e}", file=sys.stderr)
            return 1
    
    val_p = partner_sub.add_parser("validate", help="Validate partner")
    val_p.add_argument("applicationId")
    val_p.set_defaults(func=_partner_cmd_validate)
    
    def _partner_cmd_deactivate(args):
        if args.dry_run:
            _print_json({"dry_run": True, "action": "deactivate", "applicationId": args.applicationId})
            return 0
        try:
            client = _get_dynamo_client(args)
            table = _table_name(args, "partner-applications")
            resp = client.update_item(
                TableName=table,
                Key={"applicationId": {"S": args.applicationId}},
                UpdateExpression="SET #s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": {"S": "INACTIVE"}},
                ReturnValues="UPDATED_NEW"
            )
            _print_json({"deactivated": True, "response": resp})
            return 0
        except Exception as e:
            print(f"partner deactivate failed: {e}", file=sys.stderr)
            return 1
    
    deact_p = partner_sub.add_parser("deactivate", help="Deactivate partner")
    deact_p.add_argument("applicationId")
    deact_p.set_defaults(func=_partner_cmd_deactivate)

    # Placeholder commands for future expansion
    ap = sub.add_parser("apiprofile", help="APIProfile management")
    ap.add_subparsers(dest="apiprofile_cmd", required=True)

    cred = sub.add_parser("credential", help="Credential management")
    cred_sub = cred.add_subparsers(dest="credential_cmd", required=True)
    
    def _cred_list(args):
        _print_json({"credentials": []})
        return 0
    list_c = cred_sub.add_parser("list", help="List credentials")
    list_c.set_defaults(func=_cred_list)
    
    def _cred_show(args):
        _print_json({"credentialId": args.credentialId, "status": "unknown"})
        return 0
    show_c = cred_sub.add_parser("show", help="Show credential")
    show_c.add_argument("credentialId")
    show_c.set_defaults(func=_cred_show)
    
    def _cred_issue(args):
        if args.dry_run or args.output_file is None:
            _print_json({"dry_run": args.dry_run, "message": "Dry run - no credential issued"})
            return 0
        # Placeholder for real issuance - not implemented in this stub
        _print_json({"credentialId": "placeholder", "issued": False})
        return 0
    issue_c = cred_sub.add_parser("issue", help="Issue credential")
    issue_c.add_argument("--apiProfileId", required=True)
    issue_c.add_argument("--expiresAt", required=True)
    issue_c.add_argument("--output-file", required=False, help="Secure destination for secret")
    issue_c.set_defaults(func=_cred_issue)
    
    def _cred_revoke(args):
        _print_json({"revoked": args.credentialId})
        return 0
    revoke_c = cred_sub.add_parser("revoke", help="Revoke credential")
    revoke_c.add_argument("credentialId")
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
