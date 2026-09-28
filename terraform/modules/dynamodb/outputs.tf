# DynamoDB Outputs
# NOTE: work_items_table_name/work_items_table_arn/agent_state_table_name
# live inline in main.tf (G0.1 originals); their c83e3a2 copies were removed.
# The outputs below exist ONLY here (no inline twin) and are consumed by
# root outputs and the lambda module — restored after an over-broad removal;
# see TERRAFORM-BACKEND-CONFIG-IMPLEMENTATION-01 (regression correction).

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
