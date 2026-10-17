"""Local state mirror — the S3-outage fallback.

Why this exists
---------------
RIS keeps its state in S3. A local copy is what survives an S3 outage, a
wrong bucket, or a lost lock. The component project already ships this
mechanism and it is the reference: `atomic_ops.AtomicStateManager` keeps a
`.backups` directory beside the state file and rotates `backup_count` copies.
RIS mirrors that shape, adapted to the one difference — the state is remote,
so the snapshot comes from `terraform state pull`, not a local file.

These tests never touch AWS and never invoke terraform.
"""

import json
from pathlib import Path

import pytest

from installer.state_mirror import (
    MIRROR_DIRNAME,
    MIRROR_KEEP,
    StateMirror,
    mirror_dir_for,
)


def _state(serial=42, lineage="9b14f5a3-82c2-f5b4", resources=1):
    return json.dumps(
        {
            "version": 4,
            "serial": serial,
            "lineage": lineage,
            "resources": [
                {
                    "mode": "managed",
                    "type": "aws_dynamodb_table",
                    "name": "orders",
                    "instances": [
                        {
                            "attributes": {
                                "arn": "arn:aws:dynamodb:eu-central-1:1:table/orders"
                            }
                        }
                    ],
                }
            ][:resources],
        },
        indent=2,
    )


@pytest.fixture()
def mirror(tmp_path):
    return StateMirror(tmp_path / "state-mirror")


class TestPlacement:
    def test_mirror_is_not_inside_the_isolated_workdir(self):
        """The workdir is deleted and recreated on every run, so a mirror
        inside it would vanish on the next invocation — the exact failure this
        exists to prevent."""
        d = mirror_dir_for("/base", "mays-ris", "dev")
        assert d.as_posix() == "/base/mays-ris/dev/state-mirror"
        assert not d.as_posix().endswith("/terraform")

    def test_mirror_is_a_sibling_of_the_workdir(self):
        d = mirror_dir_for("/base", "mays-ris", "dev")
        assert d.parent.as_posix() == "/base/mays-ris/dev"
        assert d.name == MIRROR_DIRNAME

    def test_mirror_is_per_project_and_environment(self):
        a = mirror_dir_for("/base", "mays-ris", "dev")
        b = mirror_dir_for("/base", "mays-ris", "test")
        c = mirror_dir_for("/base", "mays-ris-composite-a", "dev")
        assert len({a, b, c}) == 3

    def test_context_exposes_a_mirror_dir_outside_the_workdir(self, tmp_path):
        from installer.ris import RisInstallContext

        base = tmp_path / "base"
        ctx = RisInstallContext(
            project_name="mays-ris",
            environment="dev",
            dry_run=True,
            _workdir_base=str(base),
        )
        mirror = ctx.isolated_mirror_dir
        assert mirror == str(base / "mays-ris" / "dev" / MIRROR_DIRNAME)
        # The mirror must NOT live inside the recreated workdir tree.
        assert MIRROR_DIRNAME not in Path(ctx.isolated_workdir).parts


class TestSnapshot:
    def test_snapshot_is_written_verbatim(self, mirror):
        raw = _state()
        entry = mirror.snapshot(raw)
        assert entry.path.read_text() == raw

    def test_snapshot_records_serial_and_lineage(self, mirror):
        entry = mirror.snapshot(_state(serial=42, lineage="9b14f5a3-abcd"))
        assert entry.serial == 42
        assert entry.lineage == "9b14f5a3-abcd"

    def test_snapshot_records_a_sha256(self, mirror):
        import hashlib

        raw = _state()
        entry = mirror.snapshot(raw)
        assert entry.sha256 == hashlib.sha256(raw.encode()).hexdigest()

    def test_unparseable_payload_is_still_mirrored(self, mirror):
        """Exactly the case where a local copy matters most."""
        entry = mirror.snapshot("{not json")
        assert entry.path.read_text() == "{not json"
        assert entry.serial is None
        assert entry.sha256  # still hashed

    def test_two_snapshots_in_the_same_second_do_not_collide(self, mirror):
        """The timestamp has second resolution; a naive name would collide."""
        for serial in range(4):
            mirror.snapshot(_state(serial=serial))
        # no exception, and each snapshot is a distinct file
        assert len(mirror.entries()) == MIRROR_KEEP

    def test_the_same_payload_twice_in_the_same_second(self, mirror):
        """The digest alone is not enough.

        Two snapshots of identical state in one second get identical digests,
        so the disambiguating suffix has to come from somewhere else. This is
        the ordinary case, not an exotic one: applying a no-op plan does not
        change the state, so re-mirroring yields the same bytes.
        """
        raw = _state(serial=42)
        first = mirror.snapshot(raw)
        second = mirror.snapshot(raw)
        assert first.path != second.path
        assert first.path.read_text() == second.path.read_text() == raw

    def test_label_is_sanitised(self, mirror):
        entry = mirror.snapshot(_state(), label="../../escape")
        assert entry.path.parent == mirror.mirror_dir
        assert ".." not in entry.path.name


class TestRotation:
    def test_keeps_only_the_configured_number(self, mirror):
        for serial in range(10):
            mirror.snapshot(_state(serial=serial))
        assert len(mirror.entries()) == MIRROR_KEEP

    def test_keeps_the_newest(self, mirror):
        for serial in range(10):
            mirror.snapshot(_state(serial=serial))
        kept = [e.serial for e in mirror.entries()]
        # Written in order 0..9, keep=3 -> the three newest survive, newest
        # first. This is what a filename sort cannot guarantee inside one
        # second, which is why the rotation orders by write time.
        assert kept == [9, 8, 7]
        assert 0 not in kept

    def test_keep_must_be_positive(self, tmp_path):
        with pytest.raises(ValueError):
            StateMirror(tmp_path / "m", keep=0)

    def test_custom_keep(self, tmp_path):
        m = StateMirror(tmp_path / "m", keep=1)
        m.snapshot(_state(serial=1))
        m.snapshot(_state(serial=2))
        assert len(m.entries()) == 1


class TestOutageFallback:
    """The scenario the whole module exists for."""

    def test_state_survives_the_loss_of_the_backend(self, mirror):
        raw = _state(serial=42)
        mirror.snapshot(raw)
        # Simulate S3 being gone: nothing is reachable except this directory.
        recovered = json.loads(mirror.latest().path.read_text())
        assert recovered["serial"] == 42
        assert recovered["resources"][0]["instances"][0]["attributes"]["arn"]

    def test_arneeded_for_ownership_survive(self, mirror):
        mirror.snapshot(_state())
        data = json.loads(mirror.latest().path.read_text())
        arn = data["resources"][0]["instances"][0]["attributes"]["arn"]
        assert arn.startswith("arn:aws:")


class TestManifest:
    def test_manifest_lists_every_entry(self, mirror):
        for serial in range(3):
            mirror.snapshot(_state(serial=serial))
        man = mirror.manifest()
        assert man["count"] == 3
        assert {e["serial"] for e in man["entries"]} == {0, 1, 2}

    def test_manifest_carries_lineage_and_hash(self, mirror):
        mirror.snapshot(_state(lineage="9b14f5a3-dead"))
        entry = mirror.manifest()["entries"][0]
        assert entry["lineage"] == "9b14f5a3-dead"
        assert len(entry["sha256"]) == 64

    def test_manifest_is_written_to_disk(self, mirror):
        mirror.snapshot(_state())
        path = mirror.write_manifest()
        assert path.exists()
        assert json.loads(path.read_text())["count"] == 1

    def test_manifest_of_empty_mirror(self, mirror):
        assert mirror.manifest()["count"] == 0
        assert mirror.latest() is None


class TestReadOnlyByConstruction:
    def test_mirror_never_touches_the_backend(self, mirror):
        """No push, no state mutation, no terraform invocation."""
        import inspect
        import installer.state_mirror as sm

        src = inspect.getsource(sm)
        for forbidden in ("subprocess", "state_push", "terraform apply", "boto3"):
            assert forbidden not in src, f"mirror must not reference {forbidden}"


class TestPreApplyWiring:
    """The mirror must capture the PRE-apply state, and never block apply."""

    def test_apply_mirrors_before_the_apply_call(self):
        import inspect
        from installer.ris import _cmd_apply

        src = inspect.getsource(_cmd_apply)
        assert "mirror_project_state(ctx, runner)" in src
        assert src.index("mirror_project_state") < src.index(
            '["apply", plan_file]'
        ), "mirror must run before apply"

    def test_mirror_runs_after_the_safety_gate(self):
        import inspect
        from installer.ris import _cmd_apply

        src = inspect.getsource(_cmd_apply)
        assert src.index("is_plan_safe") < src.index("mirror_project_state")

    def test_mirror_does_not_take_a_second_state_lock(self):
        """Between the safety gate and apply, no new failure point.

        The plan in the same run already resolved the workspace, so the pull
        must not re-select it and take another state lock.

        Checked on the AST, not the source text: the docstring also mentions
        ensure_workspace=False, so a substring assertion would pass even after
        the call itself had been reverted - a test green for the wrong reason.
        """
        import ast
        import inspect
        import textwrap
        from installer.ris import mirror_project_state

        tree = ast.parse(textwrap.dedent(inspect.getsource(mirror_project_state)))
        pulls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "state_pull"
        ]
        assert len(pulls) == 1, "expected exactly one state_pull call"
        kwargs = {kw.arg: kw.value for kw in pulls[0].keywords}
        assert "ensure_workspace" in kwargs, "state_pull must pass the flag"
        assert isinstance(kwargs["ensure_workspace"], ast.Constant)
        assert kwargs["ensure_workspace"].value is False

    def test_state_pull_still_ensures_workspace_by_default(self):
        """Narrowing the mirror must not narrow every other caller."""
        import inspect
        from installer.terraform_runner import TerraformRunner

        sig = inspect.signature(TerraformRunner.state_pull)
        assert sig.parameters["ensure_workspace"].default is True


class TestCaptureInitialisesTheRequestedBackend:
    """Two bugs found by probing, both silent, both fixed here.

    Pulling without init made `terraform state pull` use whatever backend a
    previous run had left in the workdir, so --backend-bucket was ignored and
    the mirror captured the wrong bucket. And without -reconfigure, a run
    against a different bucket left the workdir pointing at the old one and
    every later run failed with "Backend configuration changed" - measured, not
    assumed.
    """

    def _capture_src(self):
        import inspect
        import textwrap
        from installer.ris import _cmd_state_mirror

        return textwrap.dedent(inspect.getsource(_cmd_state_mirror))

    def test_capture_inits_before_it_pulls(self):
        src = self._capture_src()
        assert ".init(" in src
        assert src.index(".init(") < src.index("mirror_project_state")

    def test_capture_inits_against_the_requested_backend_config(self):
        src = self._capture_src()
        assert "ctx.backend_config()" in src

    def test_capture_reconfigures_the_backend(self):
        import ast
        src = self._capture_src()
        tree = ast.parse(src)
        inits = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "init"
        ]
        assert len(inits) == 1
        kwargs = {kw.arg: kw.value for kw in inits[0].keywords}
        assert "reconfigure" in kwargs, "init must pass reconfigure"
        assert isinstance(kwargs["reconfigure"], ast.Constant)
        assert kwargs["reconfigure"].value is True

    def test_capture_needs_a_backend_bucket(self):
        from unittest.mock import MagicMock
        from installer.ris import _cmd_state_mirror

        ctx = MagicMock()
        ctx.backend_bucket = None
        assert _cmd_state_mirror(ctx, capture=True) == 2

    def test_failed_init_still_lists_the_local_mirror(self, tmp_path, capsys):
        """S3 broken must not take the local fallback down with it."""
        from unittest.mock import MagicMock, patch
        from installer.terraform_runner import TerraformResult
        from installer.ris import _cmd_state_mirror

        mirror = StateMirror(tmp_path / "m")
        mirror.snapshot(_state(serial=42))

        ctx = MagicMock()
        ctx.backend_bucket = "b"
        ctx.isolated_mirror_dir = str(mirror.mirror_dir)
        runner = MagicMock()
        runner.init.return_value = TerraformResult(
            command=["terraform"], returncode=1, stderr="bucket does not exist"
        )
        ctx.make_runner.return_value = runner

        with patch("installer.ris.validate_aws_context") as vctx:
            rc = _cmd_state_mirror(ctx, capture=True)
        assert rc == 0
        assert runner.state_pull.called is False, "must not pull after failed init"
        out = capsys.readouterr().out
        assert "serial=42" in out

    def test_listing_makes_no_terraform_call(self, tmp_path):
        from unittest.mock import MagicMock
        from installer.ris import _cmd_state_mirror

        mirror = StateMirror(tmp_path / "m")
        mirror.snapshot(_state())
        ctx = MagicMock()
        ctx.isolated_mirror_dir = str(mirror.mirror_dir)

        assert _cmd_state_mirror(ctx, capture=False) == 0
        ctx.make_runner.assert_not_called()

    def test_listing_needs_no_backend_and_no_credentials(self, tmp_path):
        """The fallback must not depend on the thing it is a fallback for."""
        from installer.ris import RisInstallContext

        ctx = RisInstallContext(
            project_name="mays-ris",
            environment="dev",
            dry_run=True,
            _workdir_base=str(tmp_path),
        )
        assert ctx.backend_bucket is None
        # No make_runner, no AWS validation: the listing must succeed as-is.
        mirror = StateMirror(ctx.isolated_mirror_dir)
        mirror.snapshot(_state(serial=7))
        from installer.ris import _list_mirror

        assert _list_mirror(mirror) == 0

    def test_mirror_failure_does_not_raise(self):
        """An S3 hiccup must not block an otherwise safe plan."""
        from unittest.mock import MagicMock
        from installer.ris import mirror_project_state
        from installer.terraform_runner import TerraformResult

        runner = MagicMock()
        runner.state_pull = MagicMock(
            return_value=TerraformResult(command=["terraform"], returncode=1, stderr="boom")
        )
        ctx = MagicMock()
        ctx.isolated_mirror_dir = "/tmp/does-not-matter"
        assert mirror_project_state(ctx, runner) is None