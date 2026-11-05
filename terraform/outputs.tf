# ============================================================
# Root Outputs — public export layer (canonical)
# ============================================================
# Pattern reference: mays-order-aws terraform/outputs.tf @ 9c61237
# (application-level public exports, flat explicit names, descriptions;
#  monitoring/cloudtrail intentionally not re-exported — no consumers).
# Decision basis: TERRAFORM-SOURCE-OF-TRUTH-DECISION-01 (9d5b603):
# outputs.tf (G0.1) is authoritative; main.tf inline copies were stale.
# NOTE on roles: `iam_role_arn` exposes module.iam.role_arn (exists, G0.1
# contract). Which role is authoritative for the Lambda runtime
# is explicitly UNDECIDED here — IAM repair scope, see reports
# TERRAFORM-ROOT-OUTPUTS-CONSOLIDATION-01 and
# TERRAFORM-IAM-CONTRACT-REPAIR-01 (dead input + broken wiring removed).

# ============================================================
# DynamoDB Outputs (explicit RIS table names)
# ============================================================
output "dynamodb_work_items_table_name" {
  description = "Name of the DynamoDB work items table."
  value       = module.dynamodb.work_items_table_name
}

output "dynamodb_privacy_receipts_table_name" {
  description = "Name of the privacy receipt journal table (R08-A1)."
  value       = module.dynamodb.privacy_receipts_table_name
}

output "dynamodb_privacy_receipts_table_arn" {
  description = "ARN of the privacy receipt journal table (R08-A1)."
  value       = module.dynamodb.privacy_receipts_table_arn
}

output "dynamodb_deletion_ledger_table_name" {
  description = "Name of the durable R08 deletion evidence table."
  value       = module.dynamodb.deletion_ledger_table_name
}

output "dynamodb_deletion_ledger_table_arn" {
  description = "ARN of the durable R08 deletion evidence table."
  value       = module.dynamodb.deletion_ledger_table_arn
}

output "dynamodb_work_items_table_arn" {
  description = "ARN of the DynamoDB work items table."
  value       = module.dynamodb.work_items_table_arn
}

output "dynamodb_agent_state_table_name" {
  description = "Name of the DynamoDB agent state table."
  value       = module.dynamodb.agent_state_table_name
}

output "dynamodb_agent_state_table_arn" {
  description = "ARN of the DynamoDB agent state table."
  value       = module.dynamodb.agent_state_table_arn
}

output "dynamodb_user_profile_table_name" {
  description = "Name of the DynamoDB user profile table."
  value       = module.dynamodb.user_profile_table_name
}

output "dynamodb_user_profile_table_arn" {
  description = "ARN of the DynamoDB user profile table."
  value       = module.dynamodb.user_profile_table_arn
}

output "dynamodb_agent_catalog_table_name" {
  description = "Name of the DynamoDB agent catalog table."
  value       = module.dynamodb.agent_catalog_table_name
}

output "dynamodb_agent_catalog_table_arn" {
  description = "ARN of the DynamoDB agent catalog table."
  value       = module.dynamodb.agent_catalog_table_arn
}

output "dynamodb_entitlements_table_name" {
  description = "Name of the DynamoDB entitlements table."
  value       = module.dynamodb.entitlements_table_name
}

output "dynamodb_entitlements_table_arn" {
  description = "ARN of the DynamoDB entitlements table."
  value       = module.dynamodb.entitlements_table_arn
}

# ============================================================
# IAM Outputs
# ============================================================
output "iam_role_name" {
  description = "Name of the IAM Lambda role (iam module)."
  value       = module.iam.role_name
}

output "iam_role_arn" {
  description = "ARN of the IAM Lambda role (iam module)."
  value       = module.iam.role_arn
}

# ============================================================
# Lambda Outputs
# ============================================================
output "lambda_function_name" {
  description = "Name of the agent Lambda function."
  value       = module.lambda.function_name
}

output "lambda_function_arn" {
  description = "ARN of the agent Lambda function."
  value       = module.lambda.function_arn
}

output "lambda_invoke_arn" {
  description = "Invoke ARN of the agent Lambda function."
  value       = module.lambda.invoke_arn
}

# ============================================================
# Cognito Outputs
# ============================================================
output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool."
  value       = local.identity_managed ? module.cognito[0].user_pool_id : var.external_cognito_user_pool_id
}

output "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool."
  value       = local.identity_managed ? module.cognito[0].user_pool_arn : var.external_cognito_user_pool_arn
}

output "cognito_user_pool_endpoint" {
  description = "Endpoint of the Cognito User Pool (JWT issuer)."
  value       = local.identity_managed ? module.cognito[0].user_pool_endpoint : replace(var.external_cognito_issuer, "https://", "")
}

output "cognito_user_pool_client_id" {
  description = "ID of the Cognito User Pool app client."
  value       = local.identity_managed ? module.cognito[0].user_pool_client_id : var.external_cognito_human_client_id
}

output "identity_mode" {
  description = "Identity ownership mode used by this stack."
  value       = var.identity_mode
}

output "cognito_issuer" {
  description = "JWT issuer used by the API authorizers."
  value       = local.identity_managed ? "https://${module.cognito[0].user_pool_endpoint}" : var.external_cognito_issuer
}

# ============================================================
# API Gateway Outputs
# ============================================================
output "api_endpoint" {
  description = "Invoke URL of the platform HTTP API."
  value       = module.api.api_endpoint
}

output "api_id" {
  description = "ID of the platform HTTP API."
  value       = module.api.api_id
}

output "api_stage_name" {
  description = "Name of the platform HTTP API stage."
  value       = module.api.api_stage_name
}

output "api_authorizer_id" {
  description = "ID of the JWT authorizer of the platform HTTP API."
  value       = module.api.authorizer_id
}

# ============================================================
# JobSearch Outputs (Gate 9)
# ============================================================
output "jobsearch_table_name" {
  description = "Name of the DynamoDB job searches table."
  value       = module.dynamodb.jobsearches_table_name
}

output "jobsearch_table_arn" {
  description = "ARN of the DynamoDB job searches table."
  value       = module.dynamodb.jobsearches_table_arn
}

# ============================================================
# SQS Outputs
# ============================================================
output "sqs_queues" {
  description = "URLs of the platform SQS queues."
  value       = module.sqs.queue_urls
}

# ============================================================
# Orders-Reader Outputs (Gate 4, eigene Order-Fassade)
# ============================================================
output "orders_reader_function_name" {
  description = "Name of the orders-reader Lambda (own order facade)."
  value       = local.orders_enabled ? module.orders_reader[0].function_name : null
}

output "orders_reader_function_arn" {
  description = "ARN of the orders-reader Lambda."
  value       = local.orders_enabled ? module.orders_reader[0].function_arn : null
}

output "orders_lifecycle" {
  description = "Orders lifecycle mode used by this stack."
  value       = var.orders_lifecycle
}

# ============================================================
# Monitoring Outputs
# ============================================================
# Intentionally not re-exported: internal alarms/dashboard, no external
# consumers (same rule as the Mays-Orders-AWS reference pattern).
