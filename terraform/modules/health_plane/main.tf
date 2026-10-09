# Health Plane Module
# CloudWatch -> EventBridge -> Health State Writer -> Private S3

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "health_state" {
  bucket = "${var.project_name}-${var.environment}-health-state"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "health_state" {
  bucket                  = aws_s3_bucket.health_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "health_state" {
  bucket = aws_s3_bucket.health_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "health_state" {
  bucket = aws_s3_bucket.health_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_lambda_function" "health_writer" {
  function_name = "${var.project_name}-${var.environment}-health-writer"
  role          = var.writer_role_arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.14"
  filename      = var.writer_zip_path
  timeout       = 30
}

resource "aws_cloudwatch_event_rule" "health_alarms" {
  name        = "${var.project_name}-${var.environment}-health-alarms"
  description = "CloudWatch alarm state changes for health plane"
  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
  })
}

resource "aws_cloudwatch_event_target" "health_writer" {
  rule      = aws_cloudwatch_event_rule.health_alarms.name
  target_id = "health_writer"
  arn       = aws_lambda_function.health_writer.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health_writer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.health_alarms.arn
}

resource "aws_lambda_function" "health_publisher" {
  function_name = "${var.project_name}-${var.environment}-health-publisher"
  role          = aws_iam_role.health_publisher.arn
  handler       = "publisher.lambda_handler"
  runtime       = "python3.14"
  filename      = var.publisher_zip_path
  timeout       = 30
  environment {
    variables = {
      HEALTH_PRIVATE_BUCKET = aws_s3_bucket.health_state.bucket
      HEALTH_PUBLIC_BUCKET  = var.public_bucket_name
      HEALTH_ALLOWLIST      = "api,lambda,dynamodb"
    }
  }
}

resource "aws_iam_role" "health_publisher" {
  name = "${var.project_name}-${var.environment}-health-publisher"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "health_publisher" {
  name = "${var.project_name}-${var.environment}-health-publisher-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.health_state.arn,
          "${aws_s3_bucket.health_state.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = "${var.public_bucket_arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "health_publisher" {
  role       = aws_iam_role.health_publisher.name
  policy_arn = aws_iam_policy.health_publisher.arn
}

resource "aws_cloudwatch_event_rule" "health_publisher_schedule" {
  name                = "${var.project_name}-${var.environment}-health-publisher-schedule"
  description         = "Scheduled health publisher run"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "health_publisher" {
  rule      = aws_cloudwatch_event_rule.health_publisher_schedule.name
  target_id = "health_publisher"
  arn       = aws_lambda_function.health_publisher.arn
}

resource "aws_lambda_permission" "eventbridge_publisher" {
  statement_id  = "AllowEventBridgePublisher"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health_publisher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.health_publisher_schedule.arn
}
