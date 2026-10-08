# RIS-ARCHITECTURE-KNOWLEDGE-RECONSTRUCTION-01

## SECTION 1: EXECUTIVE ARCHITECTURE SUMMARY
Mays Recruiting Intelligence System is a serverless agent runtime on AWS eu-central-1. Core flow: SQS work queue → Worker Lambda → Ecosystem Registry/Discovery/Eligibility/Selection → Agent Body → Domain Agents → DynamoDB results. Platform API Gateway exposes /health, /me, /agents, /orders routes. Cognito JWT auth with custom:tenant_id. Tenant isolation enforced at data and entitlement layers. Orders integration via OrdersPort + RealMaysOrdersAdapter. Jobsearch domain APIs are canonical external source installer/projects/mays_jobsearch, encapsulated via future agents. Health Plane with CloudWatch Logs sink. Privacy erasure lifecycle implemented G5. Timestamp serialization contract preserved G6.

## SECTION 2: SYSTEM RESPONSIBILITY MATRIX
RIS owns agent encapsulation, discovery, invocation, orchestration, adapters, WorkItem lifecycle, health, privacy.
Orders owns order lifecycle, status transitions, persistence, idempotency. Integration via OrdersPort.
Jobsearch owns job sourcing, CV processing, ATS, matching, cover letters. Reused via prepared APIs.

## SECTION 3: ARCHITECTURE EVOLUTION
Ground Zero G0-1 repo init, G0-2 Terraform foundation. G2 Agent API + Orders boundary. G5 Agent Body Integration. G2.7-2.9 Ecosystem foundation. Gates 3-9: Orders live, Agent run body, Idempotency, OrdersPort adapter, ATS domain agent, Multi-agent, JobSearch domain. Gates 10-12 Identity/Profile. Gate 13A Google federation foundation. G5 Privacy erasure, G6 Timestamp contract, G7 Health sink. Consolidated docs supersede CURRENT-ARCHITECTURE.md.

## SECTION 4: CURRENT VERIFIED ARCHITECTURE
Components: API GW aboqolpm0f, Lambda mays-ris-dev-agent, SQS work-queue + DLQ, DynamoDB work-items/jobsearches/user-profile/credentials/agent-catalog/entitlements/agent-state, S3 documents. Registry/Discovery/Eligibility/Selection in agents/ecosystem. Agent Body in agents/agent_body. Domain agents: reference_agent, dummy-a/b DEV, ats-agent, jobsearch-agent, orders_function.

Runtime path: SQS record → lambda/handler → runtime/pipeline.process_record → parse WorkItem → ProcessingEnvelope → AgentDiscovery → Eligibility → Selection → conditional write WorkItem → entitlement re-check → AgentInvoker → AgentBody.execute → agent process_work → persist result → health events → sink.

## SECTION 5: ORDERS INTEGRATION
Existing implementation:
agents/orders/port.py OrdersPort interface submit_order/get_order_status/can_handle
agents/orders/real.py RealMaysOrdersAdapter uses stdlib HTTP to external Orders API
agents/orders/function.py orders_function agent capabilities orders.create/status/cancel
Real integration: RIS creates/reads Orders via adapter, correlates workId/orderId, persists result_reference. WorkItem stores orderId. Errors handled with safe_to_retry False for POST. Retry via SQS redelivery for transient errors. Idempotency via WorkItem workId. Open issues: POST timeout reconciliation, server-side MO idempotency key OPEN.

## SECTION 6: JOBSEARCH INTEGRATION
Canonical checkout installer/projects/mays_jobsearch pinned at 29d8b730bb0660d48d1ba774c773e88d9aa7142e. Prepared APIs: api/profile.mjs, api/match.mjs, api/jobs.mjs, api/cover-letter.mjs, api/alerts.mjs, api/models.mjs, api/_lib/ats.mjs. RIS JobSearch domain agent exists for create/get/list tenant-isolated. No current HTTP bridge from RIS to Jobsearch APIs; intended encapsulation via RIS agent adapter. CV processing remains browser-local per architecture doc.

## SECTION 7: AGENT ECOSYSTEM
Registered agents:
reference_agent capability reference.echo
dummy-a capability dummy-a DEV
dummy-b capability dummy-b DEV
ats-agent capability analyze.job
jobsearch-agent capabilities jobsearch.create/get/list
orders_function capabilities orders.create/status/cancel
All REGISTERED, DISCOVERABLE, INVOKABLE. Tested via unit/contract tests. Live verified via pipeline execution tests. Selection first_match. Eligibility fail-closed.

## SECTION 8: MULTI-AGENT ORCHESTRATION
Existing runtime orchestration:
Semantic intent analysis NOT IMPLEMENTED
Task decomposition PARTIAL
Capability-based discovery IMPLEMENTED
Dependency graph NOT IMPLEMENTED
Parallel execution PARTIAL
Result aggregation PARTIAL
Iterative expansion NOT IMPLEMENTED
Failure recovery IMPLEMENTED
Idempotency IMPLEMENTED
No-back-jump IMPLEMENTED
Current model is single-agent selection per WorkItem with duplicate handling and retry. Extension points exist via ProcessingChain and ChainExecutor.

## SECTION 9: END-TO-END EXAMPLES
A. Orders request: API POST creates WorkItem → SQS → Worker → orders_function → RealMaysOrdersAdapter → external Orders API → result persisted → status updated.
B. ATS analysis: WorkItem capability analyze.job → ats-agent → external ATS API → result persisted.
C. JobSearch: WorkItem capability jobsearch.create → jobsearch-agent → DynamoDB JobSearch table.

## SECTION 10: IMPLEMENTATION STATUS MATRIX
Orders integration IMPLEMENTED, INTEGRATED, E2E TESTED, LIVE VERIFIED partially.
ATS domain agent IMPLEMENTED, TESTED, LIVE VERIFIED.
JobSearch agent IMPLEMENTED, TESTED.
Health sink IMPLEMENTED, LIVE VERIFIED.
Privacy erasure IMPLEMENTED, LIVE VERIFIED.
Timestamp contract IMPLEMENTED, LIVE VERIFIED.
Multi-agent decomposition NOT IMPLEMENTED.
Jobsearch API bridge NOT IMPLEMENTED.

## SECTION 11: DOCUMENTATION CONTRADICTIONS
CURRENT-ARCHITECTURE.md superseded by SYSTEM-ARCHITECTURE.md. Future extensions doc overruled by ROADMAP.md. OpenAPI coverage incomplete for platform routes.

## SECTION 12: ACTUAL OPEN ARCHITECTURE QUESTIONS
POST timeout reconciliation with Orders, server-side MO idempotency key, API error envelope unification OPEN-2, Terraform ownership of document routes OPEN-3, Google federation UX linking.

## SECTION 13: EXISTING EXTENSION POINTS
AgentRegistry registration, ProcessingChain, EventHook, HealthTracker, OrdersPort interface, adapter pattern for Jobsearch APIs.

## SECTION 14: RECOMMENDED NEXT STEPS
Evidence-based: implement RIS-side adapters for Jobsearch prepared APIs, complete API error envelope unification, address Terraform document routes ownership, implement server-side MO idempotency key if approved.

## SECTION 15: CHATGPT UNDERSTANDING HANDOFF
RIS is serverless agent runtime with WorkItem SQS pipeline, agent discovery/eligibility/selection, domain agents for ATS, JobSearch, Orders. Orders integration exists via OrdersPort adapter. Jobsearch APIs exist externally in canonical checkout, not yet bridged to RIS. Agent ecosystem fully operational. Orchestration currently single-agent selection with idempotency/retry/health. Multi-agent decomposition missing. Architecture decisions binding per SYSTEM-ARCHITECTURE.md and RUNTIME-PATH.md.
