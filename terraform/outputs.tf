output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "api_endpoint" {
  description = "API Gateway endpoint"
  value       = module.api.api_endpoint
}

output "sqs_queues" {
  description = "SQS queue URLs"
  value       = module.sqs.queue_urls
}

output "dynamodb_tables" {
  description = "DynamoDB table names"
  value = {
    work_items = module.dynamodb.work_items_table_name
  }
}

output "lambda_functions" {
  description = "Lambda function names"
  value = {
    agent = module.lambda.function_name
  }
}