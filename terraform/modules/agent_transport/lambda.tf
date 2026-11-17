# L07 / W01 — Dispatch ingress Lambda (module gate keeps it default-off).
# Handler lives in the existing agent bundle: dispatch_ingress.handler.

variable "lambda_zip_path" {
  description = "Path to the agent bundle (contains dispatch_ingress.py)."
  type        = string
  default     = ""
}

variable "lambda_runtime" {
  type    = string
  default = "python3.14"
}

variable "work_items_table_name" {
  type = string
}

variable "work_items_table_arn" {
  type = string
}

variable "api_profiles_table_name" {
  type = string
}

variable "api_profiles_table_arn" {
  type = string
}

variable "entitlements_table_name" {
  type = string
}

variable "entitlements_table_arn" {
  type = string
}

variable "dispatch_batch_size" {
  type    = number
  default = 5
}

variable "dispatch_batch_window_seconds" {
  type    = number
  default = 0
}

variable "result_transport_enabled" {
  description = "Wire the existing result queue/secret into the dispatch ingress so ORDER_RESULT can be forwarded."
  type        = bool
  default     = false
}

variable "order_result_queue_url" {
  type    = string
  default = ""
}

variable "order_result_queue_arn" {
  type    = string
  default = ""
}

variable "order_result_secret_arn" {
  type    = string
  default = ""
}

locals {
  ingress_name = "${var.project_name}-${var.environment}-agent-dispatch-ingress"
}

resource "aws_cloudwatch_log_group" "dispatch_ingress" {
  name              = "/aws/lambda/${local.ingress_name}"
  retention_in_days = 14
  tags              = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role" "dispatch_ingress" {
  name = local.ingress_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role_policy" "dispatch_ingress" {
  name = "${local.ingress_name}-policy"
  role = aws_iam_role.dispatch_ingress.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.dispatch_ingress.arn}:*"
      },
      {
        Sid      = "ReadProfiles"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = var.api_profiles_table_arn
      },
      {
        Sid    = "WorkItems"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:PutItem",
        "dynamodb:UpdateItem", "dynamodb:Query"]
        Resource = var.work_items_table_arn
      },
      {
        Sid      = "Entitlements"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:Query"]
        Resource = var.entitlements_table_arn
      },
      {
        Sid    = "ConsumeDispatchQueue"
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.dispatch.arn
      },
    ]
  })
}

resource "aws_iam_role_policy" "dispatch_result_send" {
  count = var.result_transport_enabled ? 1 : 0
  name  = "${local.ingress_name}-result-send"
  role  = aws_iam_role.dispatch_ingress.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = [var.order_result_queue_arn]
    }]
  })
}

resource "aws_iam_role_policy" "dispatch_result_secret" {
  count = var.result_transport_enabled ? 1 : 0
  name  = "${local.ingress_name}-result-secret"
  role  = aws_iam_role.dispatch_ingress.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.order_result_secret_arn]
    }]
  })
}

resource "aws_lambda_function" "dispatch_ingress" {
  function_name = local.ingress_name
  role          = aws_iam_role.dispatch_ingress.arn
  handler       = "dispatch_ingress.handler"
  runtime       = var.lambda_runtime
  filename      = var.lambda_zip_path

  source_code_hash = (
    var.lambda_zip_path != "" ? filebase64sha256(var.lambda_zip_path) : null
  )

  timeout     = 30
  memory_size = 256

  environment {
    variables = {
      WORK_ITEMS_TABLE   = var.work_items_table_name
      API_PROFILES_TABLE = var.api_profiles_table_name
      ENTITLEMENTS_TABLE = var.entitlements_table_name
      DISPATCH_QUEUE_ARN = aws_sqs_queue.dispatch.arn
      # Result transport for the inline pipeline execution.
      ORDER_RESULT_QUEUE_URL  = var.order_result_queue_url
      ORDER_RESULT_SECRET_ARN = var.order_result_secret_arn
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.dispatch_ingress,
    aws_iam_role_policy.dispatch_result_send,
    aws_iam_role_policy.dispatch_result_secret,
  ]
  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_lambda_event_source_mapping" "dispatch" {
  event_source_arn                   = aws_sqs_queue.dispatch.arn
  function_name                      = aws_lambda_function.dispatch_ingress.arn
  batch_size                         = var.dispatch_batch_size
  maximum_batching_window_in_seconds = var.dispatch_batch_window_seconds
  function_response_types            = ["ReportBatchItemFailures"]
  enabled                            = true
}

output "ingress_function_name" {
  value = aws_lambda_function.dispatch_ingress.function_name
}
