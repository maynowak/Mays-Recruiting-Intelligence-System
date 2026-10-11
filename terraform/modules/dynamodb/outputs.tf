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

output "jobsearches_table_name" {
  value = aws_dynamodb_table.jobsearches.name
}

output "jobsearches_table_arn" {
  value = aws_dynamodb_table.jobsearches.arn
}

# Partner Application Registry. The runtime Lambda resolves this table on every
# authorized agent execution (agents/ecosystem/partner_registry.py reads
# RIS_PARTNER_APPLICATIONS_TABLE); without it the registry lookup returns None
# and BOTH partner routes fail closed with 403. Not optional.
output "partner_applications_table_name" {
  value = aws_dynamodb_table.partner_applications.name
}

output "partner_applications_table_arn" {
  value = aws_dynamodb_table.partner_applications.arn
}

# gsi-client is a separate index ARN and DynamoDB does NOT honour a table ARN
# for index access. resolve_partner_application queries this index, so the
# runtime role must be granted on the index ARN explicitly.
output "partner_applications_gsi_client_arn" {
  value = "${aws_dynamodb_table.partner_applications.arn}/index/gsi-client"
}
