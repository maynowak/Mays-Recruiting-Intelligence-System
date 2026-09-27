# T011-05 — Cognito-Outputs
# NOTE: user_pool_id/endpoint/client_id live inline in main.tf (G0.1 originals).
# The duplicate copy blocks and the broken `.app`/`.staff` references were
# removed (targets never existed in RIS); see TERRAFORM-COGNITO-CONTRACT-REPAIR-01.

output "user_pool_arn" {
  description = "ARN des Cognito User Pools fuer May's Orders."
  value       = aws_cognito_user_pool.users.arn
}
