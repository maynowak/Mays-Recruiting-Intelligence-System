# SQS Module - Ground Zero Work System

resource "aws_sqs_queue" "work_queue" {
  name                       = "${var.project_name}-${var.environment}-work-queue"
  visibility_timeout_seconds = var.queue_config.visibility_timeout_seconds
  message_retention_seconds  = var.queue_config.message_retention_seconds
  max_message_size           = 256000
  delay_seconds              = 0
  receive_wait_time_seconds  = 20

  kms_master_key_id = "alias/aws/sqs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.queue_config.dlq_max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project_name}-${var.environment}-dlq"
  message_retention_seconds = 1209600

  kms_master_key_id = "alias/aws/sqs"

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue" "agent_cv_queue" {
  name                       = "${var.project_name}-${var.environment}-cv-queue"
  visibility_timeout_seconds = var.queue_config.visibility_timeout_seconds
  message_retention_seconds  = var.queue_config.message_retention_seconds

  kms_master_key_id = "alias/aws/sqs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.queue_config.dlq_max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue" "agent_ats_queue" {
  name                       = "${var.project_name}-${var.environment}-ats-queue"
  visibility_timeout_seconds = var.queue_config.visibility_timeout_seconds
  message_retention_seconds  = var.queue_config.message_retention_seconds

  kms_master_key_id = "alias/aws/sqs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.queue_config.dlq_max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue" "agent_match_queue" {
  name                       = "${var.project_name}-${var.environment}-match-queue"
  visibility_timeout_seconds = var.queue_config.visibility_timeout_seconds
  message_retention_seconds  = var.queue_config.message_retention_seconds

  kms_master_key_id = "alias/aws/sqs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.queue_config.dlq_max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

output "work_queue_url" {
  description = "Work queue URL"
  value       = aws_sqs_queue.work_queue.id
}

output "work_queue_arn" {
  description = "Work queue ARN"
  value       = aws_sqs_queue.work_queue.arn
}

output "work_queue_name" {
  description = "Work queue name (fuer CloudWatch-Dimensionen)"
  value       = aws_sqs_queue.work_queue.name
}

output "cv_queue_url" {
  description = "CV agent queue URL"
  value       = aws_sqs_queue.agent_cv_queue.id
}

output "ats_queue_url" {
  description = "ATS agent queue URL"
  value       = aws_sqs_queue.agent_ats_queue.id
}

output "match_queue_url" {
  description = "Match agent queue URL"
  value       = aws_sqs_queue.agent_match_queue.id
}

output "dlq_url" {
  description = "Dead letter queue URL"
  value       = aws_sqs_queue.dlq.id
}

output "dlq_arn" {
  description = "Dead letter queue ARN"
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_name" {
  description = "Dead letter queue name (fuer CloudWatch-Dimensionen)"
  value       = aws_sqs_queue.dlq.name
}

output "queue_urls" {
  description = "All queue URLs"
  value = {
    work  = aws_sqs_queue.work_queue.id
    cv    = aws_sqs_queue.agent_cv_queue.id
    ats   = aws_sqs_queue.agent_ats_queue.id
    match = aws_sqs_queue.agent_match_queue.id
  }
}

output "queue_arns" {
  description = "All queue ARNs"
  value = {
    work  = aws_sqs_queue.work_queue.arn
    cv    = aws_sqs_queue.agent_cv_queue.arn
    ats   = aws_sqs_queue.agent_ats_queue.arn
    match = aws_sqs_queue.agent_match_queue.arn
    dlq   = aws_sqs_queue.dlq.arn
  }
}