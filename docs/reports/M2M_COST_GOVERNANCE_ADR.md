# ADR: Cognito M2M Cost Governance

## Cognito M2M Pricing Verification
- Cognito User Pool MAU free tier up to 50,000 MAU/month.
- Client Credentials token requests are not counted as MAU.
- Token requests are included in MAU pricing; M2M clients do not create users.
- First 10,000 token requests per month are free? Actually Cognito does not charge per token request. The free tier covers MAU.
- API Gateway requests billed separately per request.
- Cost attribution: Partner Application Registry maps client_id to partner.

## Per-partner cost attribution design
- Primary cost drivers: API Gateway requests, Lambda invocations, DynamoDB reads/writes, S3.
- Cognito M2M token cost negligible.
- Use CloudWatch metrics tagged by tenant_id / applicationId.
- Partner Application Registry stores client_id, tenantId.
- Usage accounting via CloudWatch Logs Insights queries filtered by tenantId.

## Usage thresholds
Configurable per partner application:
- 70% informational warning
- 85% warning
- 95% critical warning
- 100% approval required

Thresholds apply to API Gateway request count per month.

## Administrator notifications
- SNS topic per tenant.
- Email + Slack notifications at thresholds.
- Dashboard in Partner Portal.

## Partner portal popup
German text:
"Ihre Anwendung nähert sich dem vereinbarten Nutzungslimit.
Eine kostenpflichtige Erweiterung erfolgt ausschließlich nach Freigabe."

## Approval workflow
No automatic paid-tier activation.
Approval process:
1. Partner requests increase via portal.
2. Admin reviews usage report.
3. Approval updates limit in registry.
4. Fail-closed at limit.

## Enforceable quotas
- API Gateway throttling per usage plan.
- Lambda concurrency limits per tenant.
- Fail closed: 429 Too Many Requests with clear error.

## Shared costs
- AWS costs not attributable per partner e.g., baseline infrastructure.
- Allocate via internal cost allocation tags.

## Token caching & rate limiting
- Recommend client-side token caching for 55 min of 60 min lifetime.
- API Gateway rate limiting per client_id.
- Reduces token requests.

## Integration with Partner Application Registry
- Registry stores usageLimit and currentUsage.
- Updated by scheduled job.

## AWS Budgets & cost alerts
- AWS Budgets for account-level spend.
- Budgets do not prevent charges.
- Alerts only informational.

## Implementation roadmap
1. Tag resources with tenantId/applicationId
2. Build usage metering job
3. Implement threshold notifications
4. Partner portal UI for limits
5. Approval workflow

No AWS mutations. Documentation only.
