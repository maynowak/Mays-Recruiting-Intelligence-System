# Agent Transport — dispatch ingress queue (RIS side).
#
# Owned by the consumer side (RIS reads it). Created only when
# `enable_agent_transport = true`; the default keeps every existing stack
# unchanged.

variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "orders_producer_role_arns" {
  description = "IAM role ARNs in Mays-Orders allowed to enqueue dispatches."
  type        = list(string)
  default     = []
}

variable "order_result_queue_url" {
  description = "Existing Mays-Orders result queue URL for the dispatch ingress result link."
  type        = string
  default     = ""
}

variable "order_result_queue_arn" {
  description = "Existing Mays-Orders result queue ARN for the dispatch ingress result link."
  type        = string
  default     = ""
}

variable "order_result_secret_arn" {
  description = "Existing Mays-Orders result HMAC secret ARN for the dispatch ingress result link."
  type        = string
  default     = ""
}

variable "visibility_timeout_seconds" {
  type    = number
  default = 300
}

variable "message_retention_seconds" {
  type    = number
  default = 345600
}

variable "dlq_message_retention_seconds" {
  type    = number
  default = 1209600
}

variable "max_receive_count" {
  type    = number
  default = 3
}

resource "aws_sqs_queue" "dispatch_dlq" {
  name                      = "${var.project_name}-${var.environment}-agent-dispatch-dlq"
  message_retention_seconds = var.dlq_message_retention_seconds
  sqs_managed_sse_enabled   = true
  tags                      = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue" "dispatch" {
  name                       = "${var.project_name}-${var.environment}-agent-dispatch"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dispatch_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# Only the listed Mays-Orders roles may enqueue. Empty list = no producer,
# which keeps the queue inert until the boundary is approved.
resource "aws_sqs_queue_policy" "dispatch" {
  queue_url = aws_sqs_queue.dispatch.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowOrdersProducerSendMessage"
        Effect    = "Allow"
        Principal = { AWS = var.orders_producer_role_arns }
        Action    = ["sqs:SendMessage"]
        Resource  = aws_sqs_queue.dispatch.arn
      },
    ]
  })
}

# Existing out-of-band result hand-off permission. Keep the resource when the
# site-specific result transport values are configured; default empty values
# create no policy on stacks without that link.
resource "aws_iam_role_policy" "order_result" {
  count = var.order_result_queue_arn != "" && var.order_result_secret_arn != "" ? 1 : 0

  name = "${var.project_name}-${var.environment}-agent-dispatch-ingress-order-result"
  role = aws_iam_role.dispatch_ingress.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SendOrderResult"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = var.order_result_queue_arn
      },
      {
        Sid      = "ReadOrderResultSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.order_result_secret_arn
      },
    ]
  })
}

output "dispatch_queue_url" {
  value = aws_sqs_queue.dispatch.id
}

output "dispatch_queue_arn" {
  value = aws_sqs_queue.dispatch.arn
}

output "dispatch_dlq_arn" {
  value = aws_sqs_queue.dispatch_dlq.arn
}
