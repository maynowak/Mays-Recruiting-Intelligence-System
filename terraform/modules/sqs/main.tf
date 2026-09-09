# SQS Module

resource "aws_sqs_queue" "work_queue" {
  name                       = "${var.project_name}-${var.environment}-work-queue"
  visibility_timeout_seconds = var.queue_config.visibility_timeout_seconds
  message_retention_seconds  = var.queue_config.message_retention_seconds
  max_message_size           = 256000
  delay_seconds              = 0
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.queue_config.dlq_max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue" "dlq" {
  name                        = "${var.project_name}-${var.environment}-dlq"
  message_retention_seconds   = 1209600
  tags                        = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_sqs_queue" "agent_cv_queue" {
  name                       = "${var.project_name}-${var.environment}-cv-queue"
  visibility_timeout_seconds = var.queue_config.visibility_timeout_seconds
  message_retention_seconds  = var.queue_config.message_retention_seconds

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

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.queue_config.dlq_max_receive_count
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

output "work_queue_url" {
  value = aws_sqs_queue.work_queue.id
}

output "work_queue_arn" {
  value = aws_sqs_queue.work_queue.arn
}

output "cv_queue_url" {
  value = aws_sqs_queue.agent_cv_queue.id
}

output "ats_queue_url" {
  value = aws_sqs_queue.agent_ats_queue.id
}

output "match_queue_url" {
  value = aws_sqs_queue.agent_match_queue.id
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.id
}

output "queue_urls" {
  value = {
    work = aws_sqs_queue.work_queue.id
    cv   = aws_sqs_queue.agent_cv_queue.id
    ats  = aws_sqs_queue.agent_ats_queue.id
    match = aws_sqs_queue.agent_match_queue.id
  }
}