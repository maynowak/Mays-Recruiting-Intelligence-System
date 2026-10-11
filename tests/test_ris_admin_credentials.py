"""Tests for the RIS Admin CLI credential operations.

Every case runs against the REAL domain (`agents.ecosystem.credentials`) with
in-memory stores. No credential generator is reimplemented, no secret is
asserted in output, and no test contacts AWS.
"""

import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "lambda"))

from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.credentials import InMemoryCredentialStore  # noqa: E402
from agents.ecosystem.credentials import (  # noqa: E402
    UnauthorizedManagementAttempt,
)

import ris_admin.cli as cli  # noqa: E402
import ris_admin.credentials as ops  # noqa: E402

PRINCIPAL = "arn:aws:iam::240571105849:user/ris-operator"
TENANT = "tenant-a"
OWNER = "user-1"


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class SecretGrabber:
    """Captures the CLI stdout so tests can assert the secret never appears."""

    def __init__(self):
        self.out = ""

    def __call__(self, text):
        self.out += text


class Base(unittest.TestCase):
    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        self.creds = InMemoryCredentialStore()
        owner = {"userId": OWNER, "tenantId": TENANT, "groups": []}
        admin = {"userId": "a1", "tenantId": TENANT, "groups": ["admins"]}
        self.pid = ap.create_profile(self.profiles, owner, "cli")[
            "apiProfileId"]
        ap.transition_status(self.profiles, admin, self.pid, "ACTIVE")

        self.tmp = tempfile.mkdtemp()
        os.chmod(self.tmp, 0o700)
        self.auth_file = os.path.join(self.tmp, "auth.json")
        with open(self.auth_file, "w") as fh:
            json.dump({"principals": {
                PRINCIPAL: {"role": "admin", "tenantId": TENANT}}}, fh)
        os.chmod(self.auth_file, 0o600)

        self.out = os.path.join(self.tmp, "secret.txt")
        self.actor = {"actor_role": "admin", "actor_id": PRINCIPAL,
                      "actor_tenant": TENANT}

    def _patch_cli(self):
        """Patch store access and AWS identity so nothing leaves the process."""
        return [
            patch.object(ops, "_stores",
                         return_value=(self.creds, self.profiles)),
            patch.object(cli, "_caller_arn", return_value=PRINCIPAL),
        ]


# ----------------------------------------------------------------------
# Authorization: fail closed, no role flag
# ----------------------------------------------------------------------

class TestAuthorization(Base):
    def test_no_authorization_file_fails_closed(self):
        with self.assertRaises(ops.AdminAuthorizationError):
            ops.resolve_admin_authorization(None, PRINCIPAL, "issue")

    def test_missing_authorization_file_fails_closed(self):
        with self.assertRaises(ops.AdminAuthorizationError):
            ops.resolve_admin_authorization("/nonexistent/auth.json",
                                            PRINCIPAL, "issue")

    def test_unmapped_principal_is_denied(self):
        with self.assertRaises(ops.AdminAuthorizationError):
            ops.resolve_admin_authorization(self.auth_file,
                                            "arn:aws:iam::1:user/nobody",
                                            "issue")

    def test_entry_without_role_is_denied(self):
        path = os.path.join(self.tmp, "norole.json")
        with open(path, "w") as fh:
            json.dump({"principals": {PRINCIPAL: {"tenantId": TENANT}}}, fh)
        with self.assertRaises(ops.AdminAuthorizationError):
            ops.resolve_admin_authorization(path, PRINCIPAL, "issue")

    def test_entry_without_tenant_scope_is_denied(self):
        path = os.path.join(self.tmp, "notenant.json")
        with open(path, "w") as fh:
            json.dump({"principals": {PRINCIPAL: {"role": "admin"}}}, fh)
        with self.assertRaises(ops.AdminAuthorizationError):
            ops.resolve_admin_authorization(path, PRINCIPAL, "issue")

    def test_unparsable_authorization_file_fails_closed(self):
        path = os.path.join(self.tmp, "bad.json")
        with open(path, "w") as fh:
            fh.write("{not json")
        with self.assertRaises(ops.AdminAuthorizationError):
            ops.resolve_admin_authorization(path, PRINCIPAL, "issue")

    def test_cli_has_no_actor_role_flag(self):
        """A role flag would be a privilege-escalation surface."""
        parser = cli.build_parser()
        sub = None
        for action in parser._actions:
            if isinstance(getattr(action, "choices", None), dict) \
                    and "credential" in action.choices:
                sub = action.choices["credential"]
                break
        self.assertIsNotNone(sub, "credential subcommand missing")
        cred_sub = None
        for action in sub._actions:
            if isinstance(getattr(action, "choices", None), dict):
                cred_sub = action.choices
                break
        self.assertIsNotNone(cred_sub)
        flags = set()
        for name in ("issue", "revoke", "list", "show"):
            self.assertIn(name, cred_sub)
            for action in cred_sub[name]._actions:
                flags.update(action.option_strings)
        self.assertNotIn("--actor-role", flags)
        self.assertNotIn("--role", flags)
        self.assertNotIn("--admin", flags)

    def test_world_writable_authorization_file_is_rejected(self):
        """The mapping is a trust anchor; anyone who can edit it can grant
        themselves admin rights."""
        path = os.path.join(self.tmp, "loose-auth.json")
        with open(path, "w") as fh:
            json.dump({"principals": {
                PRINCIPAL: {"role": "admin", "tenantId": "victim-tenant"}}},
                fh)
        os.chmod(path, 0o666)
        try:
            with self.assertRaises(ops.AdminAuthorizationError):
                ops.resolve_admin_authorization(path, PRINCIPAL, "issue")
        finally:
            os.chmod(path, 0o600)

    def test_aws_identity_alone_does_not_authorize(self):
        """Correct AWS identity, unmapped principal -> still denied."""
        with self.assertRaises(ops.AdminAuthorizationError):
            ops.resolve_admin_authorization(
                self.auth_file, "arn:aws:iam::240571105849:user/intruder",
                "revoke a credential")


# ----------------------------------------------------------------------
# Output destination safety
# ----------------------------------------------------------------------

class TestOutputDestination(Base):
    def test_missing_directory_rejected(self):
        with self.assertRaises(ops.OutputDestinationError):
            ops.precheck_output_destination("/no/such/dir/secret.txt")

    def test_existing_file_rejected(self):
        with open(self.out, "w") as fh:
            fh.write("existing")
        with self.assertRaises(ops.OutputDestinationError):
            ops.precheck_output_destination(self.out)

    def test_symlink_rejected(self):
        target = os.path.join(self.tmp, "target.txt")
        with open(target, "w") as fh:
            fh.write("x")
        link = os.path.join(self.tmp, "link.txt")
        os.symlink(target, link)
        with self.assertRaises(ops.OutputDestinationError):
            ops.precheck_output_destination(link)

    def test_open_refuses_symlink_even_after_precheck(self):
        """TOCTOU: a symlink planted between precheck and open must fail.

        O_EXCL is the guard that actually carries this - on Linux
        open(O_CREAT|O_EXCL) fails when the final component is a symlink even
        though O_NOFOLLOW is absent. Verified: removing O_NOFOLLOW does not
        change this outcome.
        """
        target = os.path.join(self.tmp, "target2.txt")
        with open(target, "w") as fh:
            fh.write("x")
        link = os.path.join(self.tmp, "link2.txt")
        os.symlink(target, link)
        with self.assertRaises(ops.OutputDestinationError):
            ops.open_secret_file(link)
        # The symlink target must be untouched.
        self.assertEqual(open(target).read(), "x")

    def test_symlink_guard_survives_without_nofollow(self):
        """Proves O_EXCL, not O_NOFOLLOW, is the symlink guard."""
        target = os.path.join(self.tmp, "target3.txt")
        with open(target, "w") as fh:
            fh.write("x")
        link = os.path.join(self.tmp, "link3.txt")
        os.symlink(target, link)

        real_open = os.open
        try:
            os.open = lambda path, flags, mode=0o777: real_open(
                path, flags & ~getattr(os, "O_NOFOLLOW", 0), mode)
            with self.assertRaises(ops.OutputDestinationError):
                ops.open_secret_file(link)
        finally:
            os.open = real_open
        self.assertEqual(open(target).read(), "x")

    def test_symlinked_parent_directory_is_rejected(self):
        """Only the final component is covered by O_EXCL, so a symlinked
        intermediate directory would redirect the entire write."""
        real_dir = os.path.join(self.tmp, "realdir")
        os.makedirs(real_dir, exist_ok=True)
        link_dir = os.path.join(self.tmp, "linkdir")
        os.symlink(real_dir, link_dir)
        with self.assertRaises(ops.OutputDestinationError):
            ops.precheck_output_destination(
                os.path.join(link_dir, "secret.txt"))
        # Nothing may have been created in the redirect target.
        self.assertFalse(os.path.exists(os.path.join(real_dir, "secret.txt")))

    def test_nested_symlinked_directory_is_rejected(self):
        deep_real = os.path.join(self.tmp, "deep")
        os.makedirs(deep_real, exist_ok=True)
        mid = os.path.join(self.tmp, "mid")
        os.makedirs(mid, exist_ok=True)
        os.symlink(deep_real, os.path.join(mid, "hop"))
        with self.assertRaises(ops.OutputDestinationError):
            ops.precheck_output_destination(
                os.path.join(mid, "hop", "secret.txt"))

    def test_open_refuses_existing_file(self):
        with open(self.out, "w") as fh:
            fh.write("existing")
        with self.assertRaises(ops.OutputDestinationError):
            ops.open_secret_file(self.out)

    def test_world_writable_directory_rejected(self):
        loose = os.path.join(self.tmp, "loose")
        os.makedirs(loose)
        os.chmod(loose, 0o777)
        try:
            with self.assertRaises(ops.OutputDestinationError):
                ops.precheck_output_destination(
                    os.path.join(loose, "s.txt"))
        finally:
            os.chmod(loose, 0o700)

    def test_group_writable_directory_rejected(self):
        loose = os.path.join(self.tmp, "grp")
        os.makedirs(loose)
        os.chmod(loose, 0o770)
        try:
            with self.assertRaises(ops.OutputDestinationError):
                ops.precheck_output_destination(
                    os.path.join(loose, "s.txt"))
        finally:
            os.chmod(loose, 0o700)


# ----------------------------------------------------------------------
# Issuance
# ----------------------------------------------------------------------

class TestIssue(Base):
    def issue(self, **kwargs):
        params = dict(api_profile_id=self.pid, expires_at=_ts(30),
                      actor=self.actor, output_path=self.out, label="cli-test",
                      reason="cli test", idempotency_key=None)
        params.update(kwargs)
        return ops.issue(profile_store=self.profiles,
                         credential_store=self.creds, **params)

    def test_issue_writes_owner_only_secret_file(self):
        result = self.issue()
        self.assertTrue(result["secretWritten"])
        self.assertTrue(result["credentialId"])
        mode = stat.S_IMODE(os.stat(self.out).st_mode)
        self.assertEqual(mode, 0o600, "secret file must be owner-only")
        with open(self.out) as fh:
            secret = fh.read()
        self.assertTrue(secret.startswith("ris_"))
        self.assertNotIn(secret, json.dumps(result),
                         "secret must never appear in the returned payload")

    def test_invalid_api_profile_rejected_before_creating_a_file(self):
        with self.assertRaises(ValueError):
            self.issue(api_profile_id="does-not-exist")
        self.assertFalse(os.path.exists(self.out))

    def test_inactive_api_profile_rejected(self):
        admin = {"userId": "a1", "tenantId": TENANT, "groups": ["admins"]}
        ap.transition_status(self.profiles, admin, self.pid, "DISABLED",
                             reason="t")
        with self.assertRaises(Exception):
            self.issue()
        self.assertFalse(os.path.exists(self.out),
                         "no placeholder may survive a failed issuance")

    def test_invalid_expiration_rejected(self):
        with self.assertRaises(ValueError):
            self.issue(expires_at="not-a-timestamp")
        self.assertFalse(os.path.exists(self.out))

    def test_empty_expiration_rejected(self):
        with self.assertRaises(ValueError):
            self.issue(expires_at="")
        self.assertFalse(os.path.exists(self.out))

    def test_expiry_beyond_profile_expiry_rejected(self):
        """The MIN rule: a credential must not outlive its profile."""
        admin_actor = {"userId": "a1", "tenantId": TENANT,
                       "groups": ["admins"], "role": "admin"}
        ap.set_expires_at(self.profiles, admin_actor, self.pid, _ts(2))
        with self.assertRaises(Exception):
            self.issue(expires_at=_ts(3650))
        self.assertFalse(os.path.exists(self.out))

    def test_cross_tenant_actor_denied_without_reason(self):
        """Cross-tenant admin is permitted ONLY with an explicit reason;
        that is the existing domain contract (_check_cross_tenant)."""
        foreign = {"actor_role": "admin", "actor_id": PRINCIPAL,
                   "actor_tenant": "tenant-z"}
        with self.assertRaises(UnauthorizedManagementAttempt):
            self.issue(actor=foreign, reason=None)
        self.assertFalse(os.path.exists(self.out))

    def test_non_admin_role_denied_for_issuance(self):
        weak = {"actor_role": "staff", "actor_id": PRINCIPAL,
                "actor_tenant": TENANT}
        with self.assertRaises(Exception):
            self.issue(actor=weak)

    def test_idempotent_replay_does_not_rewrite_secret(self):
        # expiresAt participates in the idempotency content check, so a true
        # replay must reuse the identical value.
        fixed_expiry = _ts(30)
        first = self.issue(idempotency_key="k1", expires_at=fixed_expiry)
        secret_first = open(self.out).read()
        # A replay has no secret to write, so it targets a fresh destination.
        replay_out = os.path.join(self.tmp, "replay.txt")
        self.assertTrue(secret_first)
        second = self.issue(idempotency_key="k1", output_path=replay_out,
                            expires_at=fixed_expiry)
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["credentialId"], second["credentialId"])
        self.assertFalse(second["secretWritten"])
        # The placeholder for the replay is cleaned up, and the ORIGINAL
        # secret file is untouched and still owner-only.
        self.assertFalse(os.path.exists(replay_out))
        self.assertEqual(open(self.out).read(), secret_first)
        self.assertEqual(stat.S_IMODE(os.stat(self.out).st_mode), 0o600)

    def test_output_failure_after_issuance_is_reported_not_rolled_back(self):
        real_open = ops.open_secret_file

        def exploding_open(path):
            fd = real_open(path)
            os.close(fd)
            raise ops.OutputDestinationError("simulated destination failure")

        with patch.object(ops, "open_secret_file",
                          side_effect=exploding_open):
            with self.assertRaises(ops.OutputDestinationError):
                self.issue()

    def test_write_failure_reports_the_real_credential_id(self):
        """A write failure AFTER issuance must carry the credential id so an
        operator can revoke it. The secret is never in the exception."""
        import ris_admin.credentials as mod

        def boom(fd, secret):
            raise mod.CredentialOutputFailed("", "disk full")

        with patch.object(mod, "write_secret", side_effect=boom):
            with self.assertRaises(mod.CredentialOutputFailed) as ctx:
                self.issue()
        self.assertTrue(ctx.exception.credential_id)
        self.assertIn(ctx.exception.credential_id, self.creds.by_id)
        self.assertNotIn("ris_", ctx.exception.detail)

    def test_unexpected_write_error_still_reports_credential_id(self):
        """A non-OSError failure must not orphan a credential silently.

        The credential is already issued at this point, so the operator must
        always receive the id regardless of how the write failed.
        """
        import ris_admin.credentials as mod

        def boom(fd, secret):
            raise ValueError("simulated non-OSError")

        with patch.object(mod, "write_secret", side_effect=boom):
            with self.assertRaises(mod.CredentialOutputFailed) as ctx:
                self.issue()
        self.assertTrue(ctx.exception.credential_id)
        self.assertIn(ctx.exception.credential_id, self.creds.by_id)
        self.assertNotIn("ris_", ctx.exception.detail)

    def test_cli_reports_credential_created_output_failed(self):
        """The CLI must never claim a rollback it cannot perform."""
        import ris_admin.credentials as mod
        grab = SecretGrabber()
        patches = self._patch_cli()
        for p in patches:
            p.start()
        try:
            def boom(fd, secret):
                raise mod.CredentialOutputFailed("", "simulated write error")
            with patch.object(mod, "write_secret", side_effect=boom), \
                 patch("builtins.print") as printer, \
                 patch("sys.stderr"):
                printer.side_effect = lambda text="", **kw: grab(text)
                code = cli.main([
                    "--environment", "dev", "credential", "issue",
                    "--apiProfileId", self.pid, "--expiresAt", _ts(30),
                    "--output-file", self.out,
                    "--authorization-file", self.auth_file])
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(code, 1)
        self.assertIn("CREDENTIAL_CREATED_OUTPUT_FAILED", grab.out)
        self.assertNotIn("ris_", grab.out)
        payload = json.loads(grab.out)
        self.assertTrue(payload["credentialId"])
        self.assertEqual(len(self.creds.by_id), 1)


# ----------------------------------------------------------------------
# Revocation
# ----------------------------------------------------------------------

class TestRevoke(Base):
    def issued(self):
        result = ops.issue(api_profile_id=self.pid, expires_at=_ts(30),
                           actor=self.actor, output_path=self.out,
                           reason="t", profile_store=self.profiles,
                           credential_store=self.creds)
        return result["credentialId"]

    def test_revoke_marks_revoked(self):
        cid = self.issued()
        out = ops.revoke(cid, self.actor, reason="t",
                         credential_store=self.creds)
        self.assertEqual(out["status"], "REVOKED")

    def test_revoked_credential_no_longer_verifies(self):
        from agents.ecosystem.credentials import resolve_credential_profile
        res = ops.issue(api_profile_id=self.pid, expires_at=_ts(30),
                        actor=self.actor, output_path=self.out, reason="t",
                        profile_store=self.profiles,
                        credential_store=self.creds)
        secret = open(self.out).read()
        ops.revoke(res["credentialId"], self.actor, reason="t",
                   credential_store=self.creds)
        with self.assertRaises(Exception) as ctx:
            resolve_credential_profile(
                bearer=secret, credential_store=self.creds,
                profile_store=self.profiles, now=datetime.now(timezone.utc))
        self.assertIn("revoked", str(ctx.exception).lower())

    def test_revoking_unknown_credential_raises(self):
        with self.assertRaises(Exception):
            ops.revoke("cred-nope", self.actor, reason="t",
                       credential_store=self.creds)

    def test_cross_tenant_revoke_denied_without_reason(self):
        cid = self.issued()
        foreign = {"actor_role": "admin", "actor_id": PRINCIPAL,
                   "actor_tenant": "tenant-z"}
        with self.assertRaises(UnauthorizedManagementAttempt):
            ops.revoke(cid, foreign, reason=None, credential_store=self.creds)


# ----------------------------------------------------------------------
# List / show
# ----------------------------------------------------------------------

class TestListShow(Base):
    def test_list_returns_only_tenant_scope(self):
        ops.issue(api_profile_id=self.pid, expires_at=_ts(30),
                  actor=self.actor, output_path=self.out, reason="t",
                  profile_store=self.profiles, credential_store=self.creds)
        rows = ops.list_all(self.actor, reason="t",
                            credential_store=self.creds)
        self.assertEqual(len(rows), 1)
        # Never any secret material in the listing.
        blob = json.dumps(rows)
        self.assertNotIn("ris_", blob)
        self.assertNotIn("secret", blob.lower())

    def test_show_returns_metadata_without_secret(self):
        res = ops.issue(api_profile_id=self.pid, expires_at=_ts(30),
                        actor=self.actor, output_path=self.out, reason="t",
                        profile_store=self.profiles,
                        credential_store=self.creds)
        meta = ops.show(res["credentialId"], self.actor, reason="t",
                        credential_store=self.creds)
        self.assertIsNotNone(meta)
        blob = json.dumps(meta)
        self.assertNotIn("ris_", blob)
        self.assertNotIn("digest", blob.lower())

    def test_show_unknown_credential_returns_none(self):
        self.assertIsNone(ops.show("cred-nope", self.actor, reason="t",
                                   credential_store=self.creds))


# ----------------------------------------------------------------------
# CLI surface: dry-run, confirmation, no secret in output
# ----------------------------------------------------------------------

class TestCliSurface(Base):
    def run_cli(self, argv):
        """Run the real CLI entry point, capturing stdout AND stderr so a
        secret written to either stream would be caught."""
        out, err = SecretGrabber(), SecretGrabber()
        patches = self._patch_cli()
        for p in patches:
            p.start()
        try:
            with patch("builtins.print") as printer, \
                 patch("sys.stderr") as err_stream:
                printer.side_effect = lambda text="", **kw: out(text)
                err_stream.write.side_effect = lambda text="", **kw: err(text)
                code = cli.main(argv)
        finally:
            for p in patches:
                p.stop()
        return code, out.out + err.out

    def test_dry_run_creates_nothing(self):
        code, out = self.run_cli([
            "--environment", "dev", "--dry-run", "credential", "issue",
            "--apiProfileId", self.pid, "--expiresAt", _ts(30),
            "--output-file", self.out])
        self.assertEqual(code, 0)
        self.assertIn("dryRun", out)
        self.assertFalse(os.path.exists(self.out))
        self.assertEqual(len(self.creds.by_id), 0)

    def test_dry_run_revoke_creates_nothing(self):
        code, out = self.run_cli([
            "--environment", "dev", "--dry-run", "credential", "revoke",
            "cred-x"])
        self.assertEqual(code, 0)
        self.assertIn("dryRun", out)

    def test_revoke_requires_explicit_confirmation(self):
        code, out = self.run_cli([
            "--environment", "dev", "credential", "revoke", "cred-x"])
        self.assertEqual(code, 1)
        self.assertNotIn("REVOKED", out)

    def test_issue_without_output_file_is_refused(self):
        parser = cli.build_parser()
        # argparse marks --output-file required, so the CLI cannot proceed
        # without an explicit destination.
        with self.assertRaises(SystemExit):
            parser.parse_args(["credential", "issue", "--apiProfileId", "p",
                               "--expiresAt", "t"])

    def test_cli_issue_output_never_contains_secret(self):
        code, out = self.run_cli([
            "--environment", "dev", "credential", "issue",
            "--apiProfileId", self.pid, "--expiresAt", _ts(30),
            "--output-file", self.out,
            "--authorization-file", self.auth_file])
        self.assertEqual(code, 0)
        self.assertNotIn("ris_", out)
        self.assertTrue(os.path.exists(self.out))
        self.assertEqual(stat.S_IMODE(os.stat(self.out).st_mode), 0o600)

    def test_aws_identity_failure_is_a_neutral_refusal(self):
        """An unavailable AWS identity must not produce a traceback."""
        patches = [patch.object(cli, "_caller_arn",
                                side_effect=RuntimeError("no credentials"))]
        for p in patches:
            p.start()
        try:
            grab = SecretGrabber()
            with patch("builtins.print") as printer, patch("sys.stderr"):
                printer.side_effect = lambda text="", **kw: grab(text)
                code = cli.main([
                    "--environment", "dev", "credential", "issue",
                    "--apiProfileId", self.pid, "--expiresAt", _ts(30),
                    "--output-file", self.out])
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", grab.out)
        self.assertFalse(os.path.exists(self.out))

    def test_cli_issue_denied_without_authorization_file(self):
        code, out = self.run_cli([
            "--environment", "dev", "credential", "issue",
            "--apiProfileId", self.pid, "--expiresAt", _ts(30),
            "--output-file", self.out])
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(self.out))

    def test_cli_does_not_reuse_a_second_secret_generator(self):
        source = open(ops.__file__, encoding="utf-8").read()
        for forbidden in ("secrets.token_urlsafe", "uuid4()", "token_hex"):
            self.assertNotIn(forbidden, source,
                             "CLI must not generate secrets itself")
        self.assertIn("issue_credential", source)
        self.assertIn("revoke_credential", source)


    def test_issue_called_once_per_successful(self):
        """Ensure domain issue_credential is invoked exactly once per issuance."""
        from agents.ecosystem import credentials as cred_domain
        with patch.object(cred_domain, "issue_credential", wraps=cred_domain.issue_credential) as mock_issue:
            ops.issue(
                api_profile_id=self.pid,
                expires_at=_ts(30),
                actor=self.actor,
                output_path=self.out,
                label="cli-test",
                reason="cli test",
                idempotency_key=None,
                profile_store=self.profiles,
                credential_store=self.creds,
            )
            self.assertEqual(mock_issue.call_count, 1)

    def test_concurrent_issuance_same_output(self):
        """Simulate two threads racing to write the same output path.
        Only one should succeed; the other must get OutputDestinationError."""
        out = os.path.join(self.tmp, "concurrent.txt")
        def dummy_write(fd, secret):
            os.write(fd, secret.encode("utf-8"))
            os.fsync(fd)
        with patch.object(ops, "write_secret", side_effect=dummy_write):
            results = [None, None]
            def worker(idx):
                try:
                    ops.issue(
                        api_profile_id=self.pid,
                        expires_at=_ts(30),
                        actor=self.actor,
                        output_path=out,
                        label="cli-test",
                        reason="cli test",
                        idempotency_key=None,
                        profile_store=self.profiles,
                        credential_store=self.creds,
                    )
                except Exception as exc:
                    results[idx] = exc
            t1 = threading.Thread(target=worker, args=(0,))
            t2 = threading.Thread(target=worker, args=(1,))
            t1.start(); t2.start(); t1.join(); t2.join()
            self.assertEqual(sum(1 for e in results if isinstance(e, ops.OutputDestinationError)), 1)
            self.assertEqual(len(self.creds.by_id), 1)
            self.assertTrue(os.path.exists(out))
            self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)

if __name__ == "__main__":
    unittest.main()