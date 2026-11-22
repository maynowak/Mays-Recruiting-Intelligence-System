output "role_arn" {
  value = aws_iam_role.analysis.arn
}

output "role_name" {
  value = aws_iam_role.analysis.name
}

output "jobs_bucket_name" {
  value = aws_s3_bucket.jobs.bucket
}

output "jobs_bucket_arn" {
  value = aws_s3_bucket.jobs.arn
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.analysis.name
}

output "analysis_function_name" {
  value = var.enable_analysis_runtime ? aws_lambda_function.analysis[0].function_name : ""
}

output "analysis_function_arn" {
  value = var.enable_analysis_runtime ? aws_lambda_function.analysis[0].arn : ""
}
