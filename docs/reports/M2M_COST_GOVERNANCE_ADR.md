# ADR: Cognito M2M Cost Governance

## Cognito M2M Pricing Verification (Corrected)
- Cognito User Pool MAU free tier 50,000 MAU/month.
- Client Credentials token requests are NOT billed as MAU.
- Token requests have no direct charge; they are included in user pool service.
- No assumption of 10,000 free M2M token requests.
- API Gateway, Lambda, DynamoDB, SQS costs dominate RIS cost.

## Per-partner cost attribution design
- Primary cost drivers: API Gateway requests, Lambda invocations, DynamoDB reads/writes, SQS.
- Cognito M2M token cost negligible.
- Use CloudWatch metrics tagged by tenant_id / applicationId.
- Partner Application Registry maps client_id to partner.

## Usage thresholds
Configurable per partner application:
- 70% INFORMATION
- 85% WARNING
- 95% CRITICAL
- 100% APPROVAL REQUIRED

Thresholds apply to API Gateway request count per month.

## Administrator notifications
- SNS topic per tenant.
- Email + Slack notifications at thresholds.
- Dashboard in Partner Portal.

## Partner portal popup
"Ihre Anwendung nähert sich dem vereinbarten Nutzungslimit.
Eine kostenpflichtige Erweiterung erfolgt ausschließlich nach Freigabe."

## Approval workflow
No automatic paid-tier activation.
Approval requires explicit admin action.

## Enforceable quotas
API Gateway throttling per usage plan, server-side monthly counters, fail closed at limit.

## Shared costs
AWS costs not attributable per partner e.g., baseline infrastructure allocated via internal tags.

## Token caching & rate limiting
Recommend client-side token caching 55 min of 60 min lifetime.

## Integration with Partner Application Registry
Registry stores usageLimit and currentUsage.

## AWS Budgets & cost alerts
AWS Budgets for account-level spend, alerts only informational, not a technical cap.

## Implementation roadmap
1. Tag resources
2. Build usage metering
3. Threshold notifications
4. Partner portal UI
5. Approval workflow

No AWS mutations.
