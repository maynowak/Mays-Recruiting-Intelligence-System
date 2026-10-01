# Orders-Reader outputs

output "function_name" {
  value = aws_lambda_function.reader.function_name
}

output "function_arn" {
  value = aws_lambda_function.reader.arn
}

output "role_arn" {
  value = aws_iam_role.reader.arn
}
