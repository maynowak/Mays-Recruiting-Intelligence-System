from installer.ris import (
    HEALTH_CLOUDFRONT_CREATE_ALLOWLIST,
    is_plan_safe,
)
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def change(address, resource_type, actions):
    return {
        "address": address,
        "type": resource_type,
        "change": {"actions": actions, "before": None, "after": {}},
    }


def plan(*changes):
    return {"resource_changes": list(changes)}


def test_health_cloudfront_allowlist_accepts_only_exact_creates():
    assert len(HEALTH_CLOUDFRONT_CREATE_ALLOWLIST) == 2
    safe, message = is_plan_safe(
        plan(
            change(
                "module.health_public.aws_cloudfront_distribution.health_public",
                "aws_cloudfront_distribution",
                ["create"],
            ),
            change(
                "module.health_public.aws_cloudfront_origin_access_control.health_public",
                "aws_cloudfront_origin_access_control",
                ["create"],
            ),
        ),
        "ris-dev2",
        "dev",
    )
    assert safe, message


def test_health_allowlist_rejects_other_address_or_action():
    cases = [
        change(
            "module.other.aws_cloudfront_distribution.health_public",
            "aws_cloudfront_distribution",
            ["create"],
        ),
        change(
            "module.health_public.aws_cloudfront_distribution.health_public",
            "aws_cloudfront_distribution",
            ["update"],
        ),
        change(
            "module.health_public.aws_cloudfront_distribution.health_public",
            "aws_cloudfront_distribution",
            ["delete", "create"],
        ),
    ]
    for item in cases:
        safe, message = is_plan_safe(plan(item), "ris-dev2", "dev")
        assert not safe
        assert "CloudFront" in message


def test_health_allowlist_is_not_valid_for_another_project():
    item = change(
        "module.health_public.aws_cloudfront_distribution.health_public",
        "aws_cloudfront_distribution",
        ["create"],
    )
    safe, message = is_plan_safe(plan(item), "ris-dev", "dev")
    assert not safe
    assert "CloudFront" in message


def test_cognito_dns_and_acm_remain_forbidden():
    for resource_type in (
        "aws_cognito_user_pool",
        "aws_cognito_user_pool_client",
        "aws_route53_record",
        "aws_acm_certificate",
    ):
        safe, message = is_plan_safe(
            plan(change("protected", resource_type, ["create"])),
            "ris-dev2",
            "dev",
        )
        assert not safe
        assert "Protected resource action" in message


def test_health_public_isolated_configuration_has_no_custom_domain_bindings():
    source = (ROOT / "terraform/modules/health_public/main.tf").read_text(
        encoding="utf-8"
    )
    assert '"${var.project_name}-${var.environment}-health-public"' in source
    assert '"${var.project_name}-${var.environment}-health-oac"' in source
    assert 'origin_id                = "S3-health-public"' in source
    assert "aliases" not in source
    assert "acm_certificate_arn" not in source
    assert "route53" not in source.lower()
    assert 'cloudfront_default_certificate = true' in source
