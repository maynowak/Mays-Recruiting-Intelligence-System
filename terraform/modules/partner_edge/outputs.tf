output "api_id" {
  value = aws_apigatewayv2_api.partner.id
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.partner.api_endpoint
}

output "stage_name" {
  value = aws_apigatewayv2_stage.default.name
}
