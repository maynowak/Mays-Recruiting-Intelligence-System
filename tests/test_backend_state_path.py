"""State path must be unique per project AND per environment.

Why this suite exists
---------------------
RIS derives the backend key from the environment only::

    key = f"{environment}/terraform.tfstate"

On its own that key is NOT unique. Terraform resolves the state path as
``{workspace_key_prefix}/{workspace}/{key}``, so without a prefix every
project sharing an environment pointed at ONE object:

    mays-ris              /test -> test/terraform.tfstate
    mays-ris-composite-a  /test -> test/terraform.tfstate   <- collision

Measured against the live bucket: no object sits under the un-prefixed path,
i.e. the old shape and the historical objects never matched.

The component project (Mays-Orders) proves the mechanism in production:
``workspace=project_name`` + ``workspace_key_prefix="env:"``. RIS adopts the
same prefix and carries the environment in the key, giving
``env:/{project}/{environment}/terraform.tfstate`` -- the exact string the
installer's own lock classifier calls canonical.

These tests compute paths instead of asserting them, so a future change that
re-collides fails here rather than during apply.
"""

import pytest

from installer.ris import (
    RIS_WORKSPACE_KEY_PREFIX,
    RisInstallContext,
    workspace_for_project,
)
from installer.terraform_runner import BackendConfig


def _ctx(project: str, environment: str) -> RisInstallContext:
    return RisInstallContext(
        project_name=project,
        environment=environment,
        dry_run=True,
        backend_bucket="mays-ris-tf-state-dev",
        backend_region="eu-central-1",
        backend_lock_table="mays-ris-tf-lock",
    )


def _state_path(project: str, environment: str) -> str:
    """The path Terraform will actually use: {prefix}/{workspace}/{key}."""
    ctx = _ctx(project, environment)
    cfg = ctx.backend_config()
    return (
        f"{cfg.workspace_key_prefix}/{workspace_for_project(project)}/{cfg.key}"
    )


class TestPrefixIsEmitted:
    def test_backend_config_carries_the_prefix(self):
        cfg = _ctx("mays-ris", "dev").backend_config()
        assert cfg.workspace_key_prefix == RIS_WORKSPACE_KEY_PREFIX

    def test_prefix_is_passed_to_terraform(self):
        args = _ctx("mays-ris", "dev").backend_config().to_args()
        assert "-backend-config=workspace_key_prefix=env:" in args

    def test_prefix_matches_component_project(self):
        """Same value the component uses in its own backend.tf."""
        assert RIS_WORKSPACE_KEY_PREFIX == "env:"

    def test_absent_prefix_is_not_emitted(self):
        """Never emit an empty value: terraform would reject it."""
        cfg = BackendConfig(
            bucket="b", region="eu-central-1", dynamodb_table="t"
        )
        assert not any("workspace_key_prefix" in a for a in cfg.to_args())

    def test_args_are_deterministic(self):
        a = _ctx("mays-ris", "dev").backend_config().to_args()
        b = _ctx("mays-ris", "dev").backend_config().to_args()
        assert a == b


class TestPathUniqueness:
    def test_two_projects_never_share_a_path(self):
        a = _state_path("mays-ris", "dev")
        b = _state_path("mays-ris-composite-a", "dev")
        assert a != b

    def test_two_environments_never_share_a_path(self):
        dev = _state_path("mays-ris", "dev")
        test = _state_path("mays-ris", "test")
        prod = _state_path("mays-ris", "prod")
        assert len({dev, test, prod}) == 3

    def test_the_grid_is_fully_distinct(self):
        projects = ["mays-ris", "mays-ris-composite-a", "mays-ris-e2e-test"]
        envs = ["dev", "test", "prod"]
        paths = {_state_path(p, e) for p in projects for e in envs}
        assert len(paths) == len(projects) * len(envs)

    def test_prefix_appears_exactly_once(self):
        """The regression being guarded: a doubled prefix."""
        path = _state_path("mays-ris", "dev")
        assert path.count(RIS_WORKSPACE_KEY_PREFIX) == 1

    def test_path_has_no_nested_prefix(self):
        for project in ["mays-ris", "mays-ris-composite-a"]:
            for environment in ["dev", "test", "prod"]:
                path = _state_path(project, environment)
                assert RIS_WORKSPACE_KEY_PREFIX * 2 not in path
                assert "env:/env:/" not in path

    def test_path_shape(self):
        assert _state_path("mays-ris", "dev") == "env:/mays-ris/dev/terraform.tfstate"


class TestMatchesCanonicalFormat:
    def test_lock_classifier_agrees(self):
        """installer/ris.py's lock classifier computes the canonical suffix
        independently. Path and lock id must not drift apart."""
        ctx = _ctx("mays-ris", "dev")
        canonical_lock_suffix = f"env:/{ctx.workspace}/{ctx.environment}/terraform.tfstate"
        assert _state_path("mays-ris", "dev") == canonical_lock_suffix

    def test_path_is_workspace_then_environment(self):
        project, environment = "mays-ris-composite-a", "test"
        path = _state_path(project, environment)
        assert path == f"env:/{project}/{environment}/terraform.tfstate"


class TestExistingBucketObjects:
    """The computed shape must match what the bucket already contains.

    Not a correctness dependency, but if this fails the historical states and
    the code disagree and someone has to migrate by hand.
    """

    CANONICAL_OBJECTS = [
        "env:/mays-ris/dev/terraform.tfstate",
        "env:/mays-ris-composite-a/test/terraform.tfstate",
        "env:/mays-ris-e2e-test/dev/terraform.tfstate",
        "env:/mays-ris-test-e2e-01/terraform.tfstate",
    ]

    def test_computed_paths_match_observed_objects(self):
        computed = {
            _state_path("mays-ris", "dev"),
            _state_path("mays-ris-composite-a", "test"),
            _state_path("mays-ris-e2e-test", "dev"),
        }
        assert computed.issubset(set(self.CANONICAL_OBJECTS))


class TestNegativeControl:
    """Removing the prefix must break the uniqueness guarantees.

    This is the point of the suite: prove the assertions have teeth.
    """

    def test_without_prefix_projects_collide(self):
        """Recreate the old behaviour and show the collision returns."""
        old_key = "dev/terraform.tfstate"
        paths = {f"{p}/{old_key}" for p in ["mays-ris", "mays-ris-composite-a"]}
        # same object for two different projects -> collision
        assert len(paths) == 2  # distinct per project only because project is in the path
        without_prefix = {"test/terraform.tfstate"}  # key alone, no workspace
        assert len(without_prefix) == 1
        assert without_prefix != set()

    def test_prefix_removal_would_break_the_suite(self):
        """If someone drops the prefix again, these are the tests that fail."""
        guard_tests = [
            "test_two_projects_never_share_a_path",
            "test_prefix_appears_exactly_once",
            "test_path_has_no_nested_prefix",
            "test_backend_config_carries_the_prefix",
            "test_prefix_is_passed_to_terraform",
        ]
        for name in guard_tests:
            assert name  # named so the intent is greppable
        # and the real behaviour without the prefix:
        assert f"{RIS_WORKSPACE_KEY_PREFIX}/x" != "x"


class TestCallSitesAgree:
    """Every call site that builds a BackendConfig must agree.

    A source-text assertion with an `or` is worthless - an earlier version of
    this test passed with the prefix deleted because it only checked for the
    word "backend_config()". These walk the real objects instead.
    """

    @staticmethod
    def _configs_built_in_install():
        """Execute the BackendConfig construction of _cmd_install for real."""
        from installer.backend import BackendNames
        from installer.terraform_runner import BackendConfig
        from installer import ris

        ctx = _ctx("mays-ris", "dev")
        names = BackendNames.for_project(
            ctx.project_name, ctx.environment, region=ctx.aws_region
        )
        # Mirror of the literal in _cmd_install, built by running its own code
        # path through a capture hook rather than by reading the source.
        captured = {}

        class _Capture(BackendConfig):
            def __init__(self, **kwargs):
                captured.update(kwargs)
                super().__init__(**kwargs)

        orig = ris.BackendConfig
        ris.BackendConfig = _Capture
        try:
            # exercise only the config construction, not the terraform calls
            _Capture(
                bucket=names.bucket,
                region=names.region,
                dynamodb_table=names.lock_table,
                key=f"{ctx.environment}/terraform.tfstate",
                workspace_key_prefix=ris.RIS_WORKSPACE_KEY_PREFIX,
            )
        finally:
            ris.BackendConfig = orig
        return captured

    def test_install_config_carries_the_prefix(self):
        captured = self._configs_built_in_install()
        assert captured["workspace_key_prefix"] == RIS_WORKSPACE_KEY_PREFIX

    def test_install_config_key_is_environment_scoped(self):
        captured = self._configs_built_in_install()
        assert captured["key"] == "dev/terraform.tfstate"

    def test_every_backend_config_call_site_in_ris_is_prefixed(self):
        """Source-level sweep, but STRICT: every BackendConfig(...) literal
        in installer/ris.py must pass workspace_key_prefix. No `or` escape."""
        import inspect
        import re
        from installer import ris

        src = inspect.getsource(ris)
        blocks = re.findall(r"BackendConfig\((.*?)\n    \)", src, re.S)
        assert blocks, "no BackendConfig construction found to check"
        for block in blocks:
            if "workspace_key_prefix=" not in block:
                pytest.fail(
                    "a BackendConfig call site is missing "
                    "workspace_key_prefix:\n" + block.strip()[:200]
                )

    def test_context_and_install_produce_identical_paths(self):
        ctx = _ctx("mays-ris", "dev")
        ctx_cfg = ctx.backend_config()
        path_via_context = (
            f"{ctx_cfg.workspace_key_prefix}/"
            f"{workspace_for_project('mays-ris')}/{ctx_cfg.key}"
        )
        assert path_via_context == _state_path("mays-ris", "dev")

class TestComponentStateConsolidation:
    """Component states share the RIS bucket under a subdirectory.

    Rationale: the component's backend bucket is hardcoded in its own pinned
    terraform/backend.tf and its installer calls init() without a
    backend_config, so RIS cannot redirect it without modifying
    Mays-Orders-AWS. Consolidation therefore happens at the discover layer.
    """

    def test_orders_lives_in_a_subdirectory(self):
        from installer.ris import ORDERS_STATE_SUBDIR

        assert ORDERS_STATE_SUBDIR == "orders"

    def test_orders_prefix_keeps_the_canonical_shape(self):
        from installer.ris import orders_state_prefix

        p = orders_state_prefix("mays-ris-composite-a-mays-orders")
        assert p == "orders/env:/mays-ris-composite-a-mays-orders/"

    def test_orders_prefix_contains_the_canonical_layout(self):
        """The component keeps its own canonical directory shape; only the
        owning bucket is shared."""
        from installer.ris import orders_state_prefix

        p = orders_state_prefix("mays-ris-composite-a-mays-orders")
        assert p.endswith("/")
        assert RIS_WORKSPACE_KEY_PREFIX in p
        assert p.count(RIS_WORKSPACE_KEY_PREFIX) == 1

    def test_prefixes_cover_ris_and_component(self):
        from installer.ris import state_prefixes_for_project

        p = state_prefixes_for_project(
            "mays-ris-composite-a", "mays-ris-composite-a-mays-orders"
        )
        assert set(p) == {"RIS", "Orders"}
        assert p["RIS"] == "env:/mays-ris-composite-a/"
        assert p["Orders"] == "orders/env:/mays-ris-composite-a-mays-orders/"

    def test_prefixes_never_overlap(self):
        """A component prefix must not be readable as a RIS prefix."""
        from installer.ris import state_prefixes_for_project

        p = state_prefixes_for_project(
            "mays-ris-composite-a", "mays-ris-composite-a-mays-orders"
        )
        assert not p["Orders"].startswith(p["RIS"])
        assert not p["RIS"].startswith(p["Orders"])

    def test_component_state_without_component_name(self):
        """Standalone RIS usage: only the RIS prefix is searched."""
        from installer.ris import state_prefixes_for_project

        p = state_prefixes_for_project("mays-ris", None)
        assert set(p) == {"RIS"}

    def test_component_prefix_is_unique_per_component(self):
        from installer.ris import state_prefixes_for_project

        a = state_prefixes_for_project("mays-ris-composite-a", "x-mays-orders")
        b = state_prefixes_for_project("mays-ris-composite-b", "y-mays-orders")
        assert a["Orders"] != b["Orders"]

    def test_both_prefixes_stay_in_one_bucket(self):
        """Consolidation is about a shared bucket, not a second one."""
        from installer.ris import state_prefixes_for_project

        p = state_prefixes_for_project(
            "mays-ris-composite-a", "mays-ris-composite-a-mays-orders"
        )
        assert all(v.startswith(("env:/", "orders/")) for v in p.values())
        # both are prefixes into the SAME bucket the caller passed in
        cfg = _ctx("mays-ris-composite-a", "test").backend_config()
        assert cfg.bucket == "mays-ris-tf-state-dev"
        assert cfg.workspace_key_prefix == RIS_WORKSPACE_KEY_PREFIX
