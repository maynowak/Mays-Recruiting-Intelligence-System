# G7-HEALTH-EVENT-SINK-CONSUMER-01

STATUS: GREEN

## Sink selection
Selected: CloudWatch Logs structured emission via existing Lambda logging infrastructure.

Reason: HealthPlane events already produced in-process. Reusing CloudWatch Logs requires no new AWS service, zero recurring cost, and is operationally queryable via CloudWatch Logs Insights. Minimal change, maximal observability.

No new platform introduced.

## Event contract
Fields emitted: eventId, eventType, occurredAt, component, state, tenantId, workId, agentId, attemptId, reason, consecutiveFailures

Privacy: payload/body/result/credential/secret/token/password/email/userid never emitted. Reason codes from closed vocabulary; unknown reasons coerced to INFRASTRUCTURE.

## Failure isolation
Sink emission wrapped in try/except, errors swallowed with warning. Health instrumentation failure cannot propagate to work processing.

## Implementation
* `agents/ecosystem/health_sink.py` – fail-safe structured logger
* `agents/runtime/pipeline.py` – capture HealthTracker events, emit via sink

State machine unchanged.

## Tests
* sink logs structured JSON
* empty list no log
* sink failure swallow
* tracker events reach sink
* privacy / sanitization preserved
* unknown reason coerced

All targeted health sink tests green.

## AWS deployment
Canonical build: `python3 lambda/build_zip.py --bundle agent`
Artifact sha256: dd2f4f4ea6a603497def3e90a6c95744de840a47e1f8cb65706d849d3ad5ed9c
CodeSha256: 3S9PTqamA0l97z6QpslXRN6ECkfh+MtlcG2EnTrV7Zw=
Terraform plan: 0 add, 1 change, 0 destroy – module.lambda.aws_lambda_function.agent source_code_hash update
Apply successful, live CodeSha256 matches.

## Regression
1204 passed, 0 failed, 8 skipped, 15 warnings (external + intentional negative control)
G5 erasure infrastructure preserved
G6 timestamp behavior preserved

Post-apply Terraform plan: no changes.

Evidence Verifier: VERIFIED

## Commits
See git log.

## Next
Core roadmap complete.
Follow-up tech debt: OPEN-2 error-envelope unification, OPEN-3 document routes Terraform ownership
