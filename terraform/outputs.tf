output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_user_pool_client_id" {
  value = module.cognito.user_pool_client_id
}

output "api_endpoint" {
  value = module.api.api_endpoint
}

output "api_id" {
  value = module.api.api_id
}

output "sqs_queues" {
  value = module.sqs.queue_urls
}

output "dynamodb_tables" {
  value = {
    work_items   = module.dynamodb.work_items_table_name
    agent_state  = module.dynamodb.agent_state_table_name
    user_profile = module.dynamodb.user_profile_table_name
    agent_catalog = module.dynamodb.agent_catalog_table_name
    entitlements = module.dynamodb.entitlements_table_name
  }
}

output "lambda_functions" {
  value = {
    agent = module.lambda.function_name
  }
}

output "lambda_role_arn" {
  value = module.iam.lambda_role_arn
}