"""Security tests for the guarded Partner Application CLI path."""

import json
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "tools")
from ris_admin import cli  # noqa: E402


PRINCIPAL = "arn:aws:iam::262370457690:user/devnemo"
TENANT = "tenant-synthetic-19"


def _anchor(path, principal=PRINCIPAL, role="admin", tenant=TENANT):
    path.write_text(json.dumps({"principals": {
        principal: {"role": role, "tenantId": tenant}}}), encoding="utf-8")
    os.chmod(path, 0o600)


def _args(parser, *extra):
    return parser.parse_args([
        "partner", "create", "partner-19", "--cognitoClientId", "client-19",
        "--apiProfileId", "aprof_19", *extra])


def test_partner_create_has_no_tenant_override():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        _args(parser, "--tenantId", "foreign-tenant")


def test_partner_create_missing_authorization_fails_before_registry(monkeypatch):
    parser = cli.build_parser()
    args = _args(parser)
    monkeypatch.delenv("RIS_ADMIN_AUTHORIZATION_FILE", raising=False)
    with patch.object(cli, "_caller_arn", return_value=PRINCIPAL), \
            patch.object(cli, "_get_dynamo_client",
                         side_effect=AssertionError("DynamoDB must not be reached")), \
            patch.object(cli, "_apiprofile_ops",
                         side_effect=AssertionError("profile must not be reached")):
        assert args.func(args) == 1


def test_partner_create_unmapped_authorization_fails_before_registry(tmp_path):
    parser = cli.build_parser()
    anchor = tmp_path / "auth.json"
    _anchor(anchor, principal="arn:aws:iam::262370457690:user/other")
    args = _args(parser, "--authorization-file", str(anchor))
    with patch.object(cli, "_caller_arn", return_value=PRINCIPAL), \
            patch.object(cli, "_get_dynamo_client",
                         side_effect=AssertionError("DynamoDB must not be reached")), \
            patch.object(cli, "_apiprofile_ops",
                         side_effect=AssertionError("profile must not be reached")):
        assert args.func(args) == 1


def test_partner_create_rejects_profile_from_foreign_tenant(tmp_path):
    parser = cli.build_parser()
    anchor = tmp_path / "auth.json"
    _anchor(anchor)
    args = _args(parser, "--authorization-file", str(anchor))
    profile_ops = MagicMock()
    profile_ops.show.return_value = {"apiProfileId": "aprof_19",
                                     "status": "ACTIVE",
                                     "tenantId": "foreign-tenant"}
    with patch.object(cli, "_caller_arn", return_value=PRINCIPAL), \
            patch.object(cli, "_apiprofile_ops", return_value=profile_ops), \
            patch.object(cli, "_get_dynamo_client",
                         side_effect=AssertionError("DynamoDB must not be reached")):
        assert args.func(args) == 1


def test_partner_create_passes_authorized_tenant_to_registry(tmp_path):
    parser = cli.build_parser()
    args = _args(parser)
    profile_ops = MagicMock()
    profile_ops.show.return_value = {"apiProfileId": "aprof_19",
                                     "status": "ACTIVE", "tenantId": TENANT}
    import agents.ecosystem.partner_registry as registry
    create = MagicMock(return_value={
        "applicationId": "partner-19", "status": "ACTIVE"})
    fake_client = object()
    auth_ops = types.SimpleNamespace(
        resolve_admin_authorization=lambda *args, **kwargs: {
            "actor_role": "admin", "actor_id": PRINCIPAL,
            "actor_tenant": TENANT})
    with patch.object(cli, "_credential_ops", return_value=auth_ops), \
            patch.object(cli, "_caller_arn", return_value=PRINCIPAL), \
            patch.object(cli, "_apiprofile_ops", return_value=profile_ops), \
            patch.object(cli, "_get_dynamo_client", return_value=fake_client), \
            patch.object(registry, "create_partner_application", create):
        assert args.func(args) == 0
    call = create.call_args.kwargs
    assert call["tenant_id"] == TENANT
    assert call["dynamodb_client"] is fake_client


def test_partner_deactivate_passes_authorized_tenant_to_registry():
    parser = cli.build_parser()
    args = parser.parse_args(["partner", "deactivate", "partner-19"])
    registry = MagicMock()
    registry.deactivate_partner_application.return_value = {
        "applicationId": "partner-19", "status": "INACTIVE"}
    fake_client = object()
    auth_ops = types.SimpleNamespace(
        resolve_admin_authorization=lambda *args, **kwargs: {
            "actor_role": "admin", "actor_id": PRINCIPAL,
            "actor_tenant": TENANT})
    import agents.ecosystem.partner_registry as registry_module
    with patch.object(cli, "_credential_ops", return_value=auth_ops), \
            patch.object(cli, "_caller_arn", return_value=PRINCIPAL), \
            patch.object(cli, "_get_dynamo_client", return_value=fake_client), \
            patch.object(registry_module, "deactivate_partner_application",
                         registry.deactivate_partner_application):
        assert args.func(args) == 0
    call = registry.deactivate_partner_application.call_args.kwargs
    assert call["expected_tenant"] == TENANT
    assert call["dynamodb_client"] is fake_client
    assert call["release_reservation"] is False


def test_partner_deactivate_release_passes_dependency_checker():
    parser = cli.build_parser()
    args = parser.parse_args([
        "partner", "deactivate", "partner-19", "--release-reservation"])
    registry = MagicMock()
    registry.deactivate_partner_application.return_value = {
        "applicationId": "partner-19", "status": "INACTIVE",
        "reservationReleased": True}
    fake_client = MagicMock()
    fake_client.scan.return_value = {"Count": 0}
    profile_ops = MagicMock()
    profile_ops.show.return_value = {"status": "REVOKED"}
    auth_ops = types.SimpleNamespace(
        resolve_admin_authorization=lambda *args, **kwargs: {
            "actor_role": "admin", "actor_id": PRINCIPAL,
            "actor_tenant": TENANT})
    import agents.ecosystem.partner_registry as registry_module
    with patch.object(cli, "_credential_ops", return_value=auth_ops), \
            patch.object(cli, "_caller_arn", return_value=PRINCIPAL), \
            patch.object(cli, "_get_dynamo_client", return_value=fake_client), \
            patch.object(cli, "_apiprofile_ops", return_value=profile_ops), \
            patch.object(registry_module, "deactivate_partner_application",
                         registry.deactivate_partner_application):
        assert args.func(args) == 0
        call = registry.deactivate_partner_application.call_args.kwargs
        assert call["release_reservation"] is True
        checker = call["dependency_check"]
        assert callable(checker)
        assert checker("aprof_x") is False


def test_partner_deactivate_release_blocked_for_active_profile():
    parser = cli.build_parser()
    args = parser.parse_args([
        "partner", "deactivate", "partner-19", "--release-reservation"])
    registry = MagicMock()
    registry.deactivate_partner_application.return_value = {
        "applicationId": "partner-19", "status": "INACTIVE"}
    fake_client = MagicMock()
    fake_client.scan.return_value = {"Count": 0}
    profile_ops = MagicMock()
    profile_ops.show.return_value = {"status": "ACTIVE"}
    auth_ops = types.SimpleNamespace(
        resolve_admin_authorization=lambda *args, **kwargs: {
            "actor_role": "admin", "actor_id": PRINCIPAL,
            "actor_tenant": TENANT})
    import agents.ecosystem.partner_registry as registry_module
    with patch.object(cli, "_credential_ops", return_value=auth_ops), \
            patch.object(cli, "_caller_arn", return_value=PRINCIPAL), \
            patch.object(cli, "_get_dynamo_client", return_value=fake_client), \
            patch.object(cli, "_apiprofile_ops", return_value=profile_ops), \
            patch.object(registry_module, "deactivate_partner_application",
                         registry.deactivate_partner_application):
        args.func(args)
        checker = registry.deactivate_partner_application.call_args.kwargs[
            "dependency_check"]
        assert checker("aprof_x") is True


def _release_checker_with_scans(scan_results):
    parser = cli.build_parser()
    args = parser.parse_args([
        "partner", "deactivate", "partner-19", "--release-reservation"])
    registry = MagicMock()
    registry.deactivate_partner_application.return_value = {
        "applicationId": "partner-19", "status": "INACTIVE"}
    fake_client = MagicMock()
    fake_client.scan.side_effect = scan_results
    profile_ops = MagicMock()
    profile_ops.show.return_value = {"status": "REVOKED"}
    auth_ops = types.SimpleNamespace(
        resolve_admin_authorization=lambda *args, **kwargs: {
            "actor_role": "admin", "actor_id": PRINCIPAL,
            "actor_tenant": TENANT})
    import agents.ecosystem.partner_registry as registry_module
    with patch.object(cli, "_credential_ops", return_value=auth_ops), \
            patch.object(cli, "_caller_arn", return_value=PRINCIPAL), \
            patch.object(cli, "_get_dynamo_client", return_value=fake_client), \
            patch.object(cli, "_apiprofile_ops", return_value=profile_ops), \
            patch.object(registry_module, "deactivate_partner_application",
                         registry.deactivate_partner_application):
        args.func(args)
        checker = registry.deactivate_partner_application.call_args.kwargs[
            "dependency_check"]
        return checker("aprof_x")


def test_partner_deactivate_release_blocked_by_active_credential():
    assert _release_checker_with_scans([{"Count": 1}, {"Count": 0}]) is True


def test_partner_deactivate_release_blocked_by_active_entitlement():
    assert _release_checker_with_scans([{"Count": 0}, {"Count": 1}]) is True
