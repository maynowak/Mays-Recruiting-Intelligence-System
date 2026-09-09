# Lambda outputs

output "function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.agent.function_name
}

output "function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.agent.arn
}

output "invoke_arn" {
  description = "Lambda invoke ARN"
  value       = aws_lambda_function.agent.invoke_arn
}

output "lambda_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_execution.arn
}