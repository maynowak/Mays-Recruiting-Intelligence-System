"""Synthetic tests for versioned capability privacy contract checkpoint A."""

import hashlib

from agents.ecosystem.eligibility import check_eligibility
from agents.ecosystem.privacy_contract import (
    PRIVACY_CONTRACT_VERSION,
    CapabilityPrivacyDeclaration,
    PrivacyEvidence,
    declaration_digest,
)
from agents.ecosystem.registry import AgentDescriptor, AgentStatus
from agents.ecosystem.registry import AgentRegistry


def declaration():
    return CapabilityPrivacyDeclaration(
        capability="test.synthetic", processing_purpose="synthetic-test",
        technical_inputs=("schemaVersion",), business_inputs=("reference",),
        allowed_input_fields=("reference",),
        input_field_types=(("reference", "opaque-reference"),),
        prohibited_inline_categories=("cv_document",),
        actor_identity="verified-runtime", requester_identity="verified-user",
        tenant_identity="verified-tenant", authorization_requirements=("test-auth",),
        storage_locations=("synthetic-memory",), external_recipients=(),
        result_categories=("synthetic-result",),
        allowed_result_fields=("synthetic-result",),
        order_result_disposition="allowlisted",
        allowed_order_result_fields=("synthetic-result",),
        result_field_types=(("synthetic-result", "string"),),
        lifecycle_phases=("create", "execution", "completion"),
        cleanup_mechanism="test-fixture-cleanup",
    )


def evidence(contract=None, **overrides):
    value = dict(
        agent_id="synthetic-agent", agent_version="1.0.0",
        capability="test.synthetic", contract_version=PRIVACY_CONTRACT_VERSION,
        contract_sha256=declaration_digest(contract or declaration()),
        source_sha="a" * 40, test_report_sha256=hashlib.sha256(b"tests").hexdigest(),
        artifact_sha256=hashlib.sha256(b"artifact").hexdigest(),
        tests_passed=True, required_tests_skipped=False,
    )
    value.update(overrides)
    return PrivacyEvidence(**value)


def descriptor(**kwargs):
    declaration_value = declaration()
    values = dict(
        agent_id="synthetic-agent", name="Synthetic", version="1.0.0",
        status=AgentStatus.ACTIVE, capabilities=["test.synthetic"],
        privacy_contract_version=PRIVACY_CONTRACT_VERSION,
        privacy_declarations={"test.synthetic": declaration_value},
        privacy_evidence={"test.synthetic": evidence(declaration_value)},
        source_sha="a" * 40,
        artifact_sha256=hashlib.sha256(b"artifact").hexdigest(),
    )
    values.update(kwargs)
    return AgentDescriptor(**values)


def test_missing_contract_or_evidence_fails_closed():
    d = descriptor(privacy_declarations={}, privacy_evidence={})
    result = check_eligibility(d.agent_id, d, capability="test.synthetic")
    assert not result.eligible
    assert "PRIVACY_EVIDENCE_MISSING" in result.reasons


def test_valid_synthetic_contract_evidence_is_eligible():
    d = descriptor()
    assert check_eligibility(d.agent_id, d, capability="test.synthetic").eligible


def test_stale_source_and_artifact_evidence_fails_closed():
    d = descriptor(privacy_evidence={
        "test.synthetic": evidence(source_sha="b" * 40)
    })
    result = check_eligibility(d.agent_id, d, capability="test.synthetic")
    assert not result.eligible
    assert "PRIVACY_EVIDENCE_STALE" in result.reasons


def test_skipped_or_failed_required_tests_never_pass():
    d = descriptor(privacy_evidence={
        "test.synthetic": evidence(required_tests_skipped=True)
    })
    assert not check_eligibility(d.agent_id, d, capability="test.synthetic").eligible


def test_unsupported_contract_version_is_blocked():
    d = descriptor(privacy_contract_version="RIS-CAPABILITY-PRIVACY/99")
    result = check_eligibility(d.agent_id, d, capability="test.synthetic")
    assert not result.eligible
    assert "PRIVACY_CONTRACT_VERSION_UNSUPPORTED" in result.reasons


def test_declaration_digest_changes_with_policy():
    original = declaration()
    changed = CapabilityPrivacyDeclaration(
        **{**original.__dict__, "order_result_disposition": "reference-only"}
    )
    assert declaration_digest(original) != declaration_digest(changed)


def test_direct_executor_uses_eligibility_privacy_gate():
    from agents.agent_body.executor import AgentExecutor
    from agents.agent_body.router import AgentRouter

    registry = AgentRegistry()
    registry.register("synthetic-agent", descriptor())
    called = []
    router = AgentRouter()
    router.register(work_type="synthetic-work",
                    handler=lambda work: called.append(work) or {"success": True})
    executor = AgentExecutor(router=router, registry=registry)
    work = {
        "workId": "synthetic-work-1", "type": "synthetic-work",
        "tenantId": "synthetic-tenant", "userId": "synthetic-user",
        "idempotencyKey": "synthetic-idempotency", "agentId": "synthetic-agent",
        "capability": "test.synthetic",
        "payload": {"reference": "ref:synthetic"},
    }
    assert executor.execute(work)["success"] is True
    assert len(called) == 1
    wrapped_work = {
        **work,
        "workId": "synthetic-wrapped-work",
        "payload": {
            "workId": "synthetic-wrapped-work",
            "capability": "test.synthetic",
            "payload": {"reference": "ref:synthetic"},
        },
    }
    assert executor.execute(wrapped_work)["success"] is True
    assert len(called) == 2


def test_capability_input_and_result_field_types_are_enforceable():
    from agents.ecosystem.privacy_contract import (
        capability_input_payload, validate_capability_input,
        validate_capability_result,
    )
    policy = declaration()
    assert validate_capability_input(policy, {"reference": "ref:synthetic"})
    assert not validate_capability_input(policy, {"reference": "ref:synthetic", "cv": "x"})
    wrapped = {"capability": "test.synthetic",
               "payload": {"reference": "ref:synthetic"}}
    assert capability_input_payload(policy, {"payload": wrapped}) == wrapped["payload"]
    wrapped["capability"] = "other.capability"
    assert capability_input_payload(policy, {"payload": wrapped}) is None
    assert validate_capability_result(policy, {"data": {"synthetic-result": "ok"}})
    assert not validate_capability_result(policy, {"data": {"synthetic-result": 42}})
