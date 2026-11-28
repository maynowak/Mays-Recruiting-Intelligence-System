# RIS Ecosystem Agent Privacy — IMPLEMENTATION-04 Approval Packet

**Status:** `DRAFT FOR OWNER REVIEW — NOT APPROVED; no declarations/evidence enabled`
**Source baseline inspected:** `e186df5cc1ac8caa5690d404229aa0cee3e6f935`
**Orders pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` (unchanged)

This packet records source-observed data flows and the policy questions required
before adding capability declarations to manifests/registries. It is not a
privacy contract, legal assessment, or execution approval. No proposed policy
is loaded by runtime code. Missing declarations and package-bound test/build
evidence continue to fail closed.

## Source-observed data flows and proposed review scope

| Package / capability | Inputs and purpose observed in code | Result, storage and recipients observed | Decision needed before a declaration |
|---|---|---|---|
| Reference / `reference.echo` | `agents/reference_agent/service.py` accepts the whole `payload` and echoes it. Technical purpose is a demonstration echo; the payload has no field or category restriction. | `data.echoed` contains the original payload plus work/agent/capability metadata. The runtime persists WorkItems/results; an ORDER_RESULT may reach Mays-Orders when the existing order transport is used. No agent-owned store or direct upstream API is present. | Narrow the payload/result schema, prohibit arbitrary text or explicitly approve its scope, decide whether order-result forwarding is allowed, and identify the WorkItem/result cleanup owner. Existing echo behavior is not safe to certify as a general-purpose reference privacy policy. |
| Dummy A/B / `dummy-a`, `dummy-b` | `agents/dummy/agents.py` echoes the complete `payload`; code labels both DEV/TEST ONLY and contains no domain processing. | `data.input` reproduces arbitrary payload. Runtime WorkItem/result storage applies; no direct external API or independent store is present. Optional Orders handoff remains controlled by the shared runtime path. | Confirm test-only registration boundary; replace unrestricted echo with a bounded synthetic schema if required; identify allowed result fields and cleanup. No production-like privacy approval is inferred from “dummy”. |
| ATS / `analyze.job` | `agents/ats_agent/agent.py` forwards `job` and optional `profile` to `ATSHttpClient`; endpoint is configuration-driven. Purpose is job/profile analysis. | `agents/ats_agent/result_body.py` projects score, coverage, requirements, matches, recommendations and privacy/AI metadata. Runtime persists results; ORDER_RESULT may send the body to Mays-Orders. Exact upstream operator, region, retention, and legal role are not established by these source files. | Name/approve the configured recipient and subprocessor, purpose/legal basis, data categories and fields sent, locations/retention, result projection and Orders recipient. Existing ATS result-link assertions cannot substitute for this approval. |
| CV parser / `parse.cv` | `agents/cv_parser_agent/agent.py` accepts inline `payload.text` and calls the shared Node parser. This standalone path accepts text, unlike Analysis’ server-side CV-reference path. | Parser result includes CV tags, skills, experience, education, languages, location and confidence; no independent agent store is declared. WorkItem/result persistence and optional ORDER_RESULT remain runtime-owned. CLI or configured parser-Lambda mode is the parser boundary. | Decide whether inline CV text is prohibited or only a verified reference is allowed; approve parser boundary/operator, exact output fields, storage/forwarding and lifecycle. Keep this separate from Analysis’ CV resolver controls. |
| Job parser / `parse.job` | `agents/job_parser_agent/agent.py` forwards `job` (title/description) to the shared Node parser. | Structured tags, skills/experience requirements, work mode/location and status return through the runtime; no independent agent store. WorkItem/result persistence and optional ORDER_RESULT apply. | Decide allowed job fields (including incidental contact data), parser boundary, result projection, recipient/forwarding and cleanup. |
| Analysis / `analysis.run` | `agents/analysis_agent/agent.py`, `agents/analysis/orchestrator.py`, `agents/analysis/cv_bridge.py`: request selects CV/job/ATS/comparison results; identity/tenant, partner, entitlements and purpose-specific consent are checked. CV can be structured or `cvId`; stored CV resolution is owner/tenant scoped and may load a PDF from RIS documents before parsing. Job input can be inline text or a tenant/user-scoped `jobRef`. | Orchestrator composes CV/job/ATS/comparison result bodies. Its idempotency cache is process-local; optional `cleanup_job` deletes a resolved temporary job reference best-effort. WorkItem/result persistence and optional Mays ORDER_RESULT are runtime-owned. Parser CLI or configured internal parser Lambda and the configured ATS endpoint are processing boundaries. | Approve purpose and notice, consent/entitlement semantics per requested result, exact CV/job/result fields, parser and ATS recipients, storage/retention/cleanup, idempotency/replay behavior and order-result allowlist. Existing “draft notice not approved” behavior remains binding. |

## Approval record required

Before any package becomes privacy-eligible, accountable owners must record for
each capability: purpose; data-subject/data categories; actor/requester/tenant
identity source; authorization and consent requirements; exact typed input and
result allowlists; storage locations; external recipients and regions; ORDER_RESULT
disposition; lifecycle phases and cleanup owner/mechanism; and original test/build
selection. Legal basis, notice, retention, recipient, and operational decisions
must be made by their respective owners, not inferred by this engineering task.

Only after those decisions are approved should a package manifest bind its
capability contract, source paths, original tests, deterministic artifact and
fresh evidence. No evidence is generated from this draft. The pre-existing 25
policy-dependent regression assertions and the ATS/Analysis failures remain
visible failures until the approved narrow contracts and corresponding tests
preserve authorization, routing, entitlement, idempotency and result-link
behavior without a bypass.
