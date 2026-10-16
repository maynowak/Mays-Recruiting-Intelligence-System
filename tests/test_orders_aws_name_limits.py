"""Fail-closed guard for AWS resource-name limits of the Orders component.

The Orders Terraform derives almost every AWS resource name from its
``project_name``. AWS rejects names that exceed service-specific maximums, but
Terraform only surfaces the overflow during plan -- one resource at a time,
after the backend is already initialised. These tests pin the guard that makes
the operator learn the real limit before any AWS call.

Rules were read off the pinned Mays-Orders-AWS Terraform (5cf50a0), not guessed.
See docs/installer/AWS-NAME-LIMITS.md.
"""

import pytest

from installer.ris import (
    ORDERS_AWS_NAME_RULES,
    ORDERS_COGNITO_BACKUP_NAME_RULES,
    ORDERS_ENABLE_COGNITO_BACKUP,
    ORDERS_PROJECT_NAME_MAX_LENGTH,
    RIS_AWS_NAME_RULES,
    RIS_PROJECT_NAME_MAX_LENGTH,
    RisInstallContext,
    orders_component_project_name,
    orders_max_project_name,
    orders_name_limit_violations,
    validate_orders_aws_name_limits,
    validate_ris_aws_name_limits,
)

COMPOSITE = "mays-ris-composite-a-mays-orders"


class TestRuleTableIntegrity:
    def test_core_rules_present(self):
        resources = {r.resource for r in ORDERS_AWS_NAME_RULES}
        for required in (
            "cloudtrail_s3_bucket",
            "lambda_handler",
            "dynamodb_orders_table",
            "sqs_orders_queue",
            "iam_role_handler",
        ):
            assert required in resources

    def test_backup_rules_present(self):
        resources = {r.resource for r in ORDERS_COGNITO_BACKUP_NAME_RULES}
        assert "cognito_backup_s3_bucket" in resources

    def test_no_duplicate_resources(self):
        all_rules = list(ORDERS_AWS_NAME_RULES) + list(
            ORDERS_COGNITO_BACKUP_NAME_RULES
        )
        names = [r.resource for r in all_rules]
        assert len(names) == len(set(names))

    def test_all_overheads_non_negative(self):
        for rule in list(ORDERS_AWS_NAME_RULES) + list(
            ORDERS_COGNITO_BACKUP_NAME_RULES
        ):
            assert rule.overhead >= 0, rule.resource

    def test_limit_derived_from_rules_not_magic(self):
        """The published constant must be derived, never hardcoded twice."""
        expected = min(r.max_project_name for r in ORDERS_AWS_NAME_RULES)
        assert ORDERS_PROJECT_NAME_MAX_LENGTH == expected

    def test_cloudtrail_bucket_is_binding_core_rule(self):
        """39 chars is the CloudTrail bucket, per the documented derivation."""
        assert ORDERS_PROJECT_NAME_MAX_LENGTH == 39
        binding = min(ORDERS_AWS_NAME_RULES, key=lambda r: r.max_project_name)
        assert binding.resource == "cloudtrail_s3_bucket"


class TestMaxProjectName:
    def test_backup_disabled_uses_core_limit(self):
        assert orders_max_project_name(enable_cognito_backup=False) == 39

    def test_backup_enabled_is_tighter(self):
        assert orders_max_project_name(enable_cognito_backup=True) == 23

    def test_composite_fits_only_with_backup_disabled(self):
        assert orders_max_project_name(enable_cognito_backup=False) >= len(
            COMPOSITE
        )
        assert orders_max_project_name(enable_cognito_backup=True) < len(
            COMPOSITE
        )


class TestViolations:
    def test_no_violations_for_composite_with_backup_disabled(self):
        assert (
            orders_name_limit_violations(
                COMPOSITE, enable_cognito_backup=False
            )
            == []
        )

    def test_backup_bucket_violation_named(self):
        violations = orders_name_limit_violations(
            COMPOSITE, enable_cognito_backup=True
        )
        assert any("cognito_backup_s3_bucket" in v for v in violations)

    def test_violation_states_the_actual_limit(self):
        violations = orders_name_limit_violations(
            COMPOSITE, enable_cognito_backup=True
        )
        bucket = next(
            v for v in violations if "cognito_backup_s3_bucket" in v
        )
        assert "63" in bucket
        assert "max project_name 23" in bucket

    def test_every_violation_is_reported_not_just_the_first(self):
        """A single reported overflow would let the operator fix one and
        immediately hit the next."""
        violations = orders_name_limit_violations(
            COMPOSITE, enable_cognito_backup=True
        )
        assert len(violations) >= 2
        assert any("scheduler_role" in v for v in violations)

    def test_violations_ordered_tightest_first(self):
        violations = orders_name_limit_violations(
            COMPOSITE, enable_cognito_backup=True
        )
        assert "s3_bucket" in violations[0]

    def test_exact_boundary_accepted(self):
        name = "a" * 23
        assert orders_name_limit_violations(
            name, enable_cognito_backup=True
        ) == []

    def test_one_over_boundary_rejected(self):
        name = "a" * 24
        assert any(
            "s3_bucket" in v
            for v in orders_name_limit_violations(
                name, enable_cognito_backup=True
            )
        )


class TestFailClosedValidation:
    def test_passes_for_composite_default(self):
        # Composite installs disable the backup module; must not raise.
        validate_orders_aws_name_limits(
            COMPOSITE, enable_cognito_backup=ORDERS_ENABLE_COGNITO_BACKUP
        )

    def test_raises_with_backup_enabled(self):
        with pytest.raises(ValueError) as exc:
            validate_orders_aws_name_limits(
                COMPOSITE, enable_cognito_backup=True
            )
        assert "AWS name limit" in str(exc.value)

    def test_error_names_every_violated_resource(self):
        with pytest.raises(ValueError) as exc:
            validate_orders_aws_name_limits(
                COMPOSITE, enable_cognito_backup=True
            )
        message = str(exc.value)
        assert "cognito_backup_s3_bucket" in message
        assert "cognito_backup_scheduler_role" in message

    def test_error_reports_actual_length_and_max(self):
        with pytest.raises(ValueError) as exc:
            validate_orders_aws_name_limits(
                COMPOSITE, enable_cognito_backup=True
            )
        message = str(exc.value)
        assert f"({len(COMPOSITE)} chars)" in message
        assert "of 23 chars" in message

    def test_error_hints_the_disabled_backup_option(self):
        """The remedy must be actionable, not just a rejection."""
        with pytest.raises(ValueError) as exc:
            validate_orders_aws_name_limits(
                COMPOSITE, enable_cognito_backup=True
            )
        assert "enable_cognito_backup" in str(exc.value)


class TestDerivationIntegration:
    def test_composite_derivation_succeeds(self):
        assert orders_component_project_name("mays-ris-composite-a") == COMPOSITE

    def test_composite_is_validated_on_derivation(self):
        """Regression guard: derivation must not bypass the name check."""
        with pytest.raises(ValueError):
            # 45 chars -> exceeds the 39-char core limit.
            orders_component_project_name("mays-ris-" + "x" * 32)

    def test_default_flag_matches_composite_reality(self):
        """The constant the installer passes must be the composite default."""
        assert ORDERS_ENABLE_COGNITO_BACKUP is False


class TestRealWorldEvidence:
    def test_observed_plan_failure_is_prevented(self):
        """This exact name produced a 71-char S3 bucket in a real plan.

        Verified evidence: terraform reported
        "expected length of bucket to be in the range (0 - 63), got
        mays-orders-cognito-backup-development-mays-ris-composite-a-mays-orders".
        The deployed name is lowercased by locals.bucket_name (71 chars); the
        rule table keeps the capitalised module template (72 chars). Both
        exceed the 63-char limit, so the guard rejects either form.

        It must now fail up front if the backup module is ever switched back
        on, instead of failing late inside terraform.
        """
        observed = (
            "mays-orders-cognito-backup-development-"
            "mays-ris-composite-a-mays-orders"
        )
        assert len(observed) == 71
        assert len(observed) > 63  # the AWS limit that rejected it
        with pytest.raises(ValueError):
            validate_orders_aws_name_limits(
                COMPOSITE, enable_cognito_backup=True
            )

class TestRisOwnNameLimits:
    """RIS derives its own AWS names; the same fail-closed rule applies."""

    def test_binding_limit_is_cloudtrail_bucket(self):
        assert RIS_PROJECT_NAME_MAX_LENGTH == 39
        binding = min(RIS_AWS_NAME_RULES, key=lambda r: r.max_project_name)
        assert binding.resource == "cloudtrail_s3_bucket"

    def test_limit_derived_not_hardcoded(self):
        assert RIS_PROJECT_NAME_MAX_LENGTH == min(
            r.max_project_name for r in RIS_AWS_NAME_RULES
        )

    def test_ris_rules_cover_s3_lambda_and_iam(self):
        types = {r.resource for r in RIS_AWS_NAME_RULES}
        assert "cloudtrail_s3_bucket" in types
        assert any(t.startswith("lambda_") for t in types)
        assert any(t.startswith("iam_role") for t in types)

    def test_environment_placeholder_does_not_crash(self):
        """Regression: {env} in a pattern broke str.format()."""
        rule = next(r for r in RIS_AWS_NAME_RULES if "{env}" in r.pattern)
        message = rule.violation("mays-ris-demo")
        assert "mays-ris-demo" in message
        assert "{env}" in message

    def test_valid_ris_name_accepted(self):
        validate_ris_aws_name_limits("mays-ris-composite-a")

    def test_too_long_ris_name_rejected(self):
        with pytest.raises(ValueError) as exc:
            validate_ris_aws_name_limits("x" * 45)
        assert "AWS name limit" in str(exc.value)

    def test_boundary_accepted(self):
        validate_ris_aws_name_limits("a" * 39)

    def test_one_over_boundary_rejected(self):
        with pytest.raises(ValueError):
            validate_ris_aws_name_limits("a" * 40)

    def test_context_rejects_too_long_name(self):
        """The guard must fire from the single identity entry point."""
        with pytest.raises(ValueError):
            RisInstallContext(
                project_name="x" * 45, environment="test", dry_run=True
            )

    def test_context_accepts_valid_name(self):
        ctx = RisInstallContext(
            project_name="mays-ris-composite-a",
            environment="test",
            dry_run=True,
        )
        assert ctx.project_name == "mays-ris-composite-a"

    def test_context_still_rejects_bad_environment(self):
        """The new guard must not shadow the environment contract."""
        with pytest.raises(ValueError) as exc:
            RisInstallContext(
                project_name="mays-ris-demo",
                environment="production",
                dry_run=True,
            )
        assert "environment" in str(exc.value)

    def test_empty_name_still_rejected(self):
        with pytest.raises(ValueError):
            RisInstallContext(project_name="", environment="test", dry_run=True)


class TestPersistedPlanWiring:
    """The backup flag must travel with every plan, not be caller-supplied.

    A CLI-only pin is lost on the next run without explicit flags; see
    G3-COGNITO-CONFIG-PERSISTENCE-01 in AI_AUDITLOG.md for the precedent.
    """

    def test_backup_flag_is_false(self):
        assert ORDERS_ENABLE_COGNITO_BACKUP is False

    def test_plan_args_carry_the_flag(self):
        from installer.ris import _run_orders_component
        import inspect

        source = inspect.getsource(_run_orders_component)
        assert "enable_cognito_backup=" in source
        assert "orders_plan_vars" in source

    def test_name_validation_runs_before_orchestration(self):
        from installer.ris import _run_orders_component
        import inspect

        source = inspect.getsource(_run_orders_component)
        # guard must appear before the first run_project_installer call
        assert source.index("validate_orders_aws_name_limits") < source.index(
            "run_project_installer"
        )
