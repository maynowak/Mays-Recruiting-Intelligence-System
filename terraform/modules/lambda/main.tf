# Lambda Module

resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-${var.environment}-lambda-role"

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

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "${var.project_name}-${var.environment}-lambda-dynamodb"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/table/${var.dynamodb_table_name}/*"
        ]
      }
    ]
  })
}

resource "aws_lambda_function" "agent" {
  function_name = "${var.project_name}-${var.environment}-agent"
  role          = aws_iam_role.lambda_execution.arn
  handler       = var.lambda_config.handler
  runtime       = var.lambda_config.runtime
  timeout       = var.lambda_config.timeout
  memory_size   = var.lambda_config.memory_size

  filename = var.lambda_config.filename

  source_code_hash = filebase64sha256(var.lambda_config.filename)

  environment {
    variables = {
      WORK_ITEMS_TABLE = var.dynamodb_table_name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_dynamodb,
    aws_cloudwatch_log_group.lambda_logs
  ]

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.agent.function_name}"
  retention_in_days = var.lambda_config.log_retention_days

  tags = merge({ "Project" = var.project_name }, var.tags)
}

output "function_name" {
  value = aws_lambda_function.agent.function_name
}

output "function_arn" {
  value = aws_lambda_function.agent.arn
}

output "invoke_arn" {
  value = aws_lambda_function.agent.invoke_arn
}