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

output "dispatch_queue_url" {
  value = aws_sqs_queue.dispatch.id
}

output "dispatch_queue_arn" {
  value = aws_sqs_queue.dispatch.arn
}

output "dispatch_dlq_arn" {
  value = aws_sqs_queue.dispatch_dlq.arn
}
