"""Registry integration for the Addition Agent.

Connects the agent to the EXISTING runtime registry and Agent Body. Selection
stays with the ecosystem (registry/discovery/eligibility/selection); this module
only declares that the agent exists and how it is routed.
"""

from __future__ import annotations

import logging
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from agents.addition_agent.agent import (
    ADDITION_AGENT_ID,
    ADDITION_AGENT_VERSION,
    ADDITION_CAPABILITY,
    ADDITION_WORK_TYPE,
    AdditionAgent,
)
from agents.ecosystem.registry import (
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
    ExecutionProfile,
)
from agents.ecosystem.privacy_contract import (
    PRIVACY_CONTRACT_VERSION, PrivacyEvidence, declaration_from_mapping,
)

logger = logging.getLogger(__name__)

BODY_VERSION = "1.0.0"
RUNTIME_LAMBDA = "python3.14"


def _load_local_privacy_material():
    """Load only evidence whose source, test report and built artifact still match."""
    root = Path(__file__).resolve().parents[2]
    package = root / "agent-installations" / "addition-agent"
    try:
        evidence_data = json.loads(
            (package / "privacy-evidence.json").read_text(encoding="utf-8"))
        contract_path = root / evidence_data["contract_path"]
        manifest_path = root / evidence_data["manifest_path"]
        source_paths = [root / name for name in evidence_data["source_paths"]]
        test_paths = [root / name for name in evidence_data["test_paths"]]
        report_path = root / evidence_data["test_report_path"]
        artifact_path = root / evidence_data["artifact_path"]
        files = [manifest_path, contract_path, *source_paths, *test_paths]
        if any(not path.is_file() or root not in path.resolve().parents for path in files):
            return None, None, None, None
        digest = hashlib.sha256()
        for path in sorted(set(files), key=lambda item: item.as_posix()):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        source_sha = digest.hexdigest()
        if source_sha != evidence_data.get("source_sha"):
            return None, None, None, None
        if not report_path.is_file() or hashlib.sha256(report_path.read_bytes()).hexdigest() != evidence_data.get("test_report_sha256"):
            return None, None, None, None
        if not artifact_path.is_file() or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != evidence_data.get("artifact_sha256"):
            return None, None, None, None
        privacy = json.loads(contract_path.read_text(encoding="utf-8"))
        declaration = declaration_from_mapping(privacy)
        evidence = PrivacyEvidence(
            **{key: evidence_data[key] for key in PrivacyEvidence.__dataclass_fields__}
        )
        selection = {"paths": evidence_data["test_paths"],
                     "args": evidence_data.get("test_args", [])}
        selection_sha = hashlib.sha256(json.dumps(
            selection, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False).encode()).hexdigest()
        if (selection_sha != evidence.test_selection_sha256
                or evidence.contract_version != PRIVACY_CONTRACT_VERSION
                or not evidence.tests_passed or evidence.required_tests_skipped):
            return None, None, None, None
        return declaration, evidence, source_sha, evidence.artifact_sha256
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, None, None, None


def get_addition_descriptor() -> AgentDescriptor:
    """Descriptor used by registry, discovery and eligibility."""
    declaration, evidence, source_sha, artifact_sha = _load_local_privacy_material()
    return AgentDescriptor(
        agent_id=ADDITION_AGENT_ID,
        name=ADDITION_AGENT_ID,
        version=ADDITION_AGENT_VERSION,
        status=AgentStatus.ACTIVE,
        capabilities=[ADDITION_CAPABILITY],
        supported_bodies=[BODY_VERSION],
        supported_runtimes=[RUNTIME_LAMBDA],
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level="low",
        description=(
            "Deterministischer Additions-Agent (math.add); keine Persistenz, "
            "keine Credentials, keine eigene Queue"
        ),
        privacy_contract_version=PRIVACY_CONTRACT_VERSION,
        privacy_declarations=({ADDITION_CAPABILITY: declaration}
                              if declaration is not None else {}),
        privacy_evidence=({ADDITION_CAPABILITY: evidence}
                          if evidence is not None else {}),
        source_sha=source_sha,
        artifact_sha256=artifact_sha,
    )


def register_addition_agent(
    registry: Optional[AgentRegistry] = None,
    body: Any = None,
) -> tuple:
    """Register descriptor and routes in the shared runtime objects.

    Idempotent: re-registration keeps the existing descriptor and only ensures
    the routes exist.
    """
    if registry is None:
        from agents.ecosystem.registry import get_registry

        registry = get_registry()
    if body is None:
        from agents.agent_body import AgentBody

        body = AgentBody()

    if not registry.is_registered(ADDITION_AGENT_ID):
        registry.register(ADDITION_AGENT_ID, get_addition_descriptor())
    # Use the requested registry for direct AgentBody eligibility too.
    if hasattr(body, "executor"):
        body.executor.registry = registry

    agent = AdditionAgent()
    body.register_agent(work_type=ADDITION_WORK_TYPE, handler=agent.process_work)
    body.register_agent(capability=ADDITION_CAPABILITY, handler=agent.process_work)
    body.register_agent(agent_id=ADDITION_AGENT_ID, handler=agent.process_work)

    logger.info(
        "addition agent registered: agentId=%s capability=%s",
        ADDITION_AGENT_ID,
        ADDITION_CAPABILITY,
    )
    return registry, body


def is_addition_registered(registry: Optional[AgentRegistry] = None) -> bool:
    if registry is None:
        from agents.ecosystem.registry import get_registry

        registry = get_registry()
    return registry.is_registered(ADDITION_AGENT_ID)


__all__ = [
    "get_addition_descriptor",
    "register_addition_agent",
    "is_addition_registered",
]
