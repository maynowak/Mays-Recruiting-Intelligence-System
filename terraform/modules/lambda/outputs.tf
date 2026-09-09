# Lambda outputs

output "function_name" {
  value = aws_lambda_function.agent.function_name
}

output "function_arn" {
  value = aws_lambda_function.agent.arn
}

output "invoke_arn" {
  value = aws_lambda_function.agent.invoke_arn
}

output "lambda_role_arn" {
  value = aws_iam_role.lambda_role.arn
}