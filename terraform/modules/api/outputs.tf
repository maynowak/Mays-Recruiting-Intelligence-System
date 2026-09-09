# API outputs

output "api_id" {
  value = aws_apigatewayv2_api.ris_api.id
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.ris_api.api_endpoint
}

output "api_stage_name" {
  value = aws_apigatewayv2_stage.default.name
}

output "authorizer_id" {
  value = aws_apigatewayv2_authorizer.jwt.id
}