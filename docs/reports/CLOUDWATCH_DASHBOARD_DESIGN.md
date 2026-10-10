# RIS CloudWatch Dashboard Design

## Global Operational Dashboard
Metrics:
- Total API requests
- Successful requests
- Failed requests
- Agent executions
- Lambda invocations / errors / duration
- DynamoDB consumption
- SQS processing
- Authentication failures
- Credential verification failures
- Estimated M2M token requests

Cost reference: existing 20 USD AWS Budget displayed as reference only.

## Partner Consumption Dashboard
Dimensions: environment, applicationId, tenantId

Metrics:
- API requests
- Successful executions
- Failed executions
- Agent execution count & duration
- Credential failures
- Throttled requests
- Monthly usage vs quota

No secrets in metrics.

## Cost Attribution
- API Gateway request count
- Lambda request + duration
- DynamoDB reads/writes
- SQS operations
- Cognito token requests
Shared infrastructure not attributed.

## Quotas
Thresholds 70/85/95/100% with alerts.
At 100%: block chargeable operations, preserve account management, privacy, deletion.

Monthly reset on calendar month.

## Security
Tenant isolation, application-level access control, minimal personal data, GDPR retention.
