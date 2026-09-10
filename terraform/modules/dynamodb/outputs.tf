# DynamoDB Outputs

output "work_items_table_name" {
  value = aws_dynamodb_table.work_items.name
}

output "work_items_table_arn" {
  value = aws_dynamodb_table.work_items.arn
}

output "agent_state_table_name" {
  value = aws_dynamodb_table.agent_state.name
}

output "agent_state_table_arn" {
  value = aws_dynamodb_table.agent_state.arn
}

output "user_profile_table_name" {
  value = aws_dynamodb_table.user_profile.name
}

output "user_profile_table_arn" {
  value = aws_dynamodb_table.user_profile.arn
}

output "agent_catalog_table_name" {
  value = aws_dynamodb_table.agent_catalog.name
}

output "agent_catalog_table_arn" {
  value = aws_dynamodb_table.agent_catalog.arn
}

output "entitlements_table_name" {
  value = aws_dynamodb_table.entitlements.name
}

output "entitlements_table_arn" {
  value = aws_dynamodb_table.entitlements.arn
}