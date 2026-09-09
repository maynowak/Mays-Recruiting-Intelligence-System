output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_user_pool_client_id" {
  description = "Cognito User Pool Client ID"
  value       = module.cognito.user_pool_client_id
}

output "api_endpoint" {
  description = "API Gateway endpoint"
  value       = module.api.api_endpoint
}

output "api_id" {
  description = "API Gateway ID"
  value       = module.api.api_id
}

output "sqs_queues" {
  description = "SQS queue URLs"
  value       = module.sqs.queue_urls
}

output "sqs_queue_arns" {
  description = "SQS queue ARNs"
  value       = module.sqs.queue_arns
}

output "dynamodb_tables" {
  description = "DynamoDB table names"
  value = {
    work_items = module.dynamodb.work_items_table_name
    agent_state = module.dynamodb.agent_state_table_name
  }
}

output "dynamodb_table_arns" {
  description = "DynamoDB table ARNs"
  value = {
    work_items = module.dynamodb.work_items_table_arn
    agent_state = module.dynamodb.agent_state_arn
  }
}

output "lambda_functions" {
  description = "Lambda function names"
  value = {
    agent = module.lambda.function_name
  }
}

output "lambda_role_arn" {
  description = "Lambda execution role ARN"
  value       = module.lambda.lambda_role_arn
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs"
  value = [
    module.vpc.private_subnet_1_id,
    module.vpc.private_subnet_2_id
  ]
}