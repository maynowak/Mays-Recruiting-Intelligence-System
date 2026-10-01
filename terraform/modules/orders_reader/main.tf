# Orders-Reader Module — eigene Order-Fassade in unserem Bereich (Gate 4).
#
# Eigene Lambda (lambda/orders_reader.py) hinter eigenem Pfad auf UNSERER
# API (mays-ris-dev-api). Liest/schreibt die Mays-Orders-Tabelle im gleichen
# Konto ueber eigene IAM-Rolle. Das fremde Projekt (Code, API, Funktionen)
# wird nicht veraendert.

data "aws_caller_identity" "current" {}

locals {
  reader_name = "${var.project_name}-${var.environment}-orders-reader"
}

resource "aws_iam_role" "reader" {
  name = local.reader_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role_policy" "reader_orders_table" {
  name = "${local.reader_name}-table"
  role = aws_iam_role.reader.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          var.orders_table_arn,
          "${var.orders_table_arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "reader" {
  function_name = local.reader_name
  role          = aws_iam_role.reader.arn
  handler       = "orders_reader.handler"
  runtime       = var.runtime
  timeout       = var.timeout
  memory_size   = var.memory_size

  filename         = var.filename
  source_code_hash = filebase64sha256(var.filename)

  environment {
    variables = {
      ORDERS_TABLE = var.orders_table_name
    }
  }

  depends_on = [
    aws_iam_role_policy.reader_orders_table,
    aws_cloudwatch_log_group.reader
  ]

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_cloudwatch_log_group" "reader" {
  name              = "/aws/lambda/${local.reader_name}"
  retention_in_days = var.log_retention_days

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_apigatewayv2_integration" "reader" {
  api_id                 = var.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.reader.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "list_orders" {
  api_id             = var.api_id
  route_key          = "GET /orders"
  target             = "integrations/${aws_apigatewayv2_integration.reader.id}"
  authorization_type = "JWT"
  authorizer_id      = var.authorizer_id
}

resource "aws_apigatewayv2_route" "get_order" {
  api_id             = var.api_id
  route_key          = "GET /orders/{orderId}"
  target             = "integrations/${aws_apigatewayv2_integration.reader.id}"
  authorization_type = "JWT"
  authorizer_id      = var.authorizer_id
}

resource "aws_apigatewayv2_route" "patch_status" {
  api_id             = var.api_id
  route_key          = "PATCH /orders/{orderId}/status"
  target             = "integrations/${aws_apigatewayv2_integration.reader.id}"
  authorization_type = "JWT"
  authorizer_id      = var.authorizer_id
}

resource "aws_lambda_permission" "api_gateway" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reader.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.api_id}/*/*/*"
}
