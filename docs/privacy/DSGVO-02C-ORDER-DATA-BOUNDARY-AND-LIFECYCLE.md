# RIS-DSGVO-02C — Order Data Boundary & Lifecycle Alignment

**Status:** `PARTIAL` — technical boundary is mapped; exclusive RIS storage and complete privacy coverage are not verified.
**RIS source:** `18f2128d6d60993b2cbe2296ac2a3f190617f289`, branch `feature/ris-dsgvo-compliance-01`.
**Integrated Mays-Orders pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` (unchanged).
**Provider source reviewed separately:** Mays-Orders Main `716a16590673cdb649df414c08fc0bf7814caac7`; provider response branch `b25cb89888af6c3d94fc8fe7060b6fbb5c3d5e95` is a review report, not the RIS pin.
**Scope:** documentation/source review only. No runtime/test/pin/AWS/deployment changes; no legal approval.

## Decision summary

An AgentOrder is an execution request, not a document store by design. The source does **not** enforce that boundary at the payload-content level: `input.data` is an opaque JSON object, can carry arbitrary non-secret data, is persisted in Orders and copied into RIS WorkItems. Result bodies are also persisted with WorkItems and, when result transport is configured, sent to the Orders result queue. The current evidence therefore does not support a claim that personal or sensitive content never enters Orders, or that results remain exclusively in RIS stores.

| Question | Finding |
|---|---|
| What does AgentOrder carry? | Target/capability and references/correlation are metadata; `input.data` is the executable domain payload; `resultContract` describes the expected output. The validator rejects unknown schema fields, credential-shaped keys/values, and over-limit content, but does not classify or prohibit personal/CV data. Serialized OrderV1 `orderDescription` is limited to 1,024 characters. |
| Are CV PDFs copied into Orders/WorkItems? | For `cvId` input, RIS resolves an authorized, ready, tenant/user-owned CV record and reads its PDF from RIS document S3. The PDF is transiently base64-encoded for the parser; `cv_bridge` states no CV bytes travel in WorkItems. This supports the narrow stored-PDF path only. Inline structured CV input is accepted and can enter the caller's AgentOrder/work payload; no general content exclusion is enforced. |
| Are sensitive results exclusive to RIS? | No. Runtime persists the complete result on the WorkItem row. `result_from_work_item` places the result body in `ORDER_RESULT.payload`; the sender publishes it when configured. The Orders reader public projection also permits `processing.result`. Provider-side storage/retention and actual deployment routing are not proven here. This is a verified code-path capability and a material boundary gap, not proof that a particular deployment currently carries CV content. |
| Are there existing RIS privacy flows? | Yes: self-scoped partner inspect/export, `/me/erasure`, and document/CV delete/erasure integrations. They cover RIS-owned stores and selected work lifecycle actions, but do not establish complete Orders-provider coverage or erase terminal WorkItem result payloads. Reuse them; do not create an AgentOrder for a privacy request. |
| Do existing provider capabilities suffice? | Provider inspect/export/erase exist, but the integrated pin's RIS AgentOrder create path has no demonstrated GSI2 subject linkage. Current provider Main has optional consumer scope and incomplete `ANONYMIZE` residual coverage (embedded AgentOrder remains). Neither source establishes a complete RIS-to-provider subject-bound inspect/export/erase flow. |

## 1. Producers, content classes, and lifecycle

### Order creation and persistence

`agents/orders/real.py::RealMaysOrdersAdapter._create_body()` builds the existing OrderV1 HTTP body. For `orders.create`, it serializes a validated AgentOrder V1 into `orderDescription`; it does not send a root `agentOrder` or a trusted RIS subject reference. AgentOrder V1 distinguishes:

- **Execution metadata:** `target.agentId`, `target.capability`, optional version; `metadata` source/request/profile/application/idempotency references; processing trigger/parent references; result format/delivery contract.
- **Fachliche Nutzdaten:** arbitrary object `input.data`. It is the only dispatch payload (`dispatch_payload()`), not merely a storage reference. Its secret scan and size limits do not prevent personal data.
- **OrderV1 metadata/identifiers:** required customer name/email, one item/SKU/price, currency, order ID, owner key, profile/entitlement context, work/correlation IDs, status, timestamps and version. These are persisted fields with their own disclosure and retention implications.

`lambda/orders_reader.py::_create_agent_order()` validates the serialized description, requires `metadata.requestId` and `apiProfileRef`, resolves an active owner-bound API profile, and checks the agent entitlement before `put_item`. It stores both `orderDescription` and an internal normalized `agentOrder` copy, plus fingerprint, dispatch state and owner/index metadata. It then builds `ORDER_DISPATCH` from `agentOrder.input.data`. Therefore the order row holds the domain payload in two representations (serialized and structured), even though only `orderDescription` is the public OrderV1 field. The public read allowlist returns `orderDescription` as opaque caller-provided text; it is not a sanitizer and can expose the serialized AgentOrder/input. The reader separately allows `processing.result` in the public projection.

### Dispatch, work, execution, result

`agents/transport/order_transport.py::dispatch_to_work_item()` requires a validated dispatch payload and a server-resolved `VerifiedContext`; identity claims must match it. It maps the full payload into the canonical WorkItem. `agents/runtime/work_item.py::build_work_item()` stores the payload with user/tenant/profile/application/issuer/actor, correlation/order references, status and default expiry metadata. Runtime `_persist_result()` writes the full result object into the WorkItems table. Terminal WorkItems are intentionally retained by the existing erasure lifecycle for duplicate suppression; G5 cancels non-terminal work but does not erase completed/failed result rows.

`result_from_work_item()` maps completed WorkItem results to `ORDER_RESULT.payload` after the credential/size scan. The runtime forwards that envelope over the configured Orders result queue and records delivery state; this is result **transport**, not proof of provider receipt or deletion. Failed results use a minimized error envelope, but the persisted RIS failure row still records error fields. SQS/DLQ/log retention and live delivery configuration are outside this repository-source conclusion.

### Data classification conclusion

Do not classify the entire AgentOrder as metadata. Its wrapper contains metadata, but `input.data` is an opaque business payload, and results are opaque JSON. Current checks are schema/size/credential checks, not a personal-data policy. The <=1,024-character serialized description limit bounds volume, not sensitivity. The processing result can include CV tags, skills, experience, education, language, location, matched/missing skills, ATS requirements, matches, gaps and scores as shown by `agents/analysis/contracts.py`.

## 2. CV, job text, and result storage paths

- **Stored CV document path:** `RequestCvResolver` accepts a `cvId`, resolves it through the existing PartnerProfileRepository with tenant/user/partner/issuer context, rejects deleted/erased/unready/foreign records, and fetches `tenant/{tenant}/users/{user}/documents/{document}` from `DOCUMENTS_BUCKET`. The source documents that bytes are not put in WorkItems. Parser input receives transient base64. This is a narrow verified code path; no live bucket configuration or all-agent behavior is attested.
- **Inline structured CV path:** `validate_request()` expressly permits `input.cv.structured`. `RequestCvResolver` returns it as-is and analysis derives result fields from it. Thus a caller can put structured personal/CV data in the generic AgentOrder `input.data`; no validator rule forces use of `cvId`.
- **Job text:** analysis accepts inline job text up to 32 KiB. `jobRef` can resolve through the private S3 job store, keyed by tenant/user and checked server-side; default expiry is two hours, hard maximum four hours/1 MiB. Optional best-effort cleanup occurs only when `cleanup_job` is enabled. This temporary store does not imply the input cannot also be copied into an AgentOrder/WorkItem by another caller. Do not claim deletion of S3 versions or provider copies from source alone.
- **Result:** `AnalysisOrchestrator` creates structured CV/job/ATS/comparison results, and runtime persists/forwards the result object as above. Hashes/stable IDs and derived attributes remain potentially linkable/personal; calling them “metadata” does not establish anonymization.

## 3. Identity, consent, profiles, and entitlements

- Orders HTTP admission uses verified Cognito JWT identity and owner binding; public body identity is not trusted. The AgentOrder reader additionally resolves `apiProfileRef` to an active profile owned by that JWT subject and checks agent entitlement before persistence. The RIS dispatch ingress resolves `contextRef` server-side and checks queue ARN and identity claims against verified context; worker execution rechecks authorization/entitlement.
- Analysis orchestration checks partner binding, requested capability entitlements, consent boolean, exact `analysis-processing` purpose, and approved notice version (except synthetic fixtures). Current checked-in config fails closed when required consent/notice/entitlement configuration is missing. This is technical enforcement evidence, not legal validation of consent or the notice.
- CV lookup has tenant/user/owner checks. These boundaries protect access but do not reduce copied payload content or prove cross-system erasure.

## 4. Existing privacy capability reuse; no privacy AgentOrder

RIS already exposes self-scoped partner `GET /v1/partner/me/privacy/inspect` and `/export`, and `POST /me/erasure`. The privacy routes use the existing JWT + partner credential/profile context and report category-level unavailable/partial results rather than treating failures as empty. The user erasure lifecycle revokes credentials/profiles, cancels non-terminal work, runs existing application/document/profile erasure components, and honestly reports partial completion. The document integration reuses the fenced S3 erasure path. These remain the correct RIS entry points.

Do **not** submit an AgentOrder for inspect/export/erase. Those are control-plane/privacy operations and must not depend on the data-processing order path. Existing RIS flows do not currently prove removal of terminal WorkItem `result`/`error` payloads; G5 explicitly retains terminal work to preserve duplicate suppression. The existing docs already flag Orders untouched/provider-owned and privacy completeness as partial.

## 5. Provider CR correction / minimal next decision

The prior 02B draft overstates **CR-MO-PRIVACY-RIS-SUBJECT-DELEGATION-01** as if a provider feature were the immediate blocker. At the integrated pin, OrderV1 creates are owner-bound to the verified JWT and RIS does not send a distinct subject. The immediate demonstrated issue is the **RIS integration/data contract**: sensitive/identifiable data can be copied into `orderDescription`/stored `agentOrder`, WorkItems and result transport, while the existing privacy service does not show a provider-linked subject flow. First decide whether RIS Orders are strictly minimal technical records and whether subject-bound provider DSAR coverage is required for the actual identity used by the Orders API. Only then retain a narrowly scoped provider request for a missing supported binding; do not require generalized delegation, a global mapping service, or new erasure architecture by default.

**CR-MO-PRIVACY-ANONYMIZE-COVERAGE-02 remains relevant but should be narrowed.** Current Main ANONYMIZE leaves embedded `agentOrder` and identity/consumer attributes. Since actual AgentOrder/input and result paths can carry personal/derived data, provider field coverage is a real concern if these rows are expected to be anonymized. However the integrated pin and deployed provider behavior must be checked independently; do not use current Main as proof of pin behavior. First minimize/prohibit sensitive content in OrderV1, then have the provider owner define residual fields and test complete rows if ANONYMIZE is selected. Do not make a legal anonymity claim.

No new global subject map is justified by this source review. Existing RIS tenant/user/profile keys and provider owner/index fields are the applicable local identity mechanisms. No code change or provider/pin request is authorized here.

## 6. Concrete gaps and verification needed

1. **Payload minimization gap:** no enforced AgentOrder input schema/content allowlist prevents CV, job, or other personal data in `input.data` or `orderDescription`. Set a domain-specific contract and tests before claiming orders contain metadata only.
2. **Cross-system result boundary:** result envelopes intentionally carry result payloads; provider-side result persistence/retention and exact deployed wiring are not proven at the integrated pin. Verify provider result consumer/storage and retention at the exact pin before asserting result locality.
3. **RIS terminal data lifecycle:** WorkItems persist input payload/results; current user erasure retains terminal rows. Resolve retention/erasure policy and verify existing privacy components' category reporting. This does not justify an unrelated global mapping architecture.
4. **Provider linkage:** integrated AgentOrder rows' subject-index linkage and effective provider privacy operations remain unproven. A synthetic exact-pin create→inspect/export/preview sequence is needed only after identity/contract owners confirm what subject the Orders HTTP JWT represents.
5. **Evidence scope:** source and existing reports were reviewed; no tests or live deployment were run. No claim is made about current AWS contents, queue configuration, provider deployment, backup/version purge, legal basis, or regulatory sufficiency.

**Final status: `PARTIAL` — order contents and lifecycle are mapped, but the required “CV documents and sensitive results remain exclusively in designated RIS stores” boundary is not enforced or fully evidenced.** No runtime changes, pin upgrades, deployments or AWS mutations.
