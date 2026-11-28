locals {
  name = "${var.project_name}-${var.environment}-analysis"
}

# Dedicated analysis runtime identity. It is deliberately NOT attached to the
# shared worker role and replaces/deletes no shared transport policy.
resource "aws_iam_role" "analysis" {
  name = local.name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role_policy" "analysis" {
  name = "${local.name}-policy"
  role = aws_iam_role.analysis.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Sid      = "ReadOwnedCvDocuments"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${var.documents_bucket_arn}/tenant/*"
      },
      {
        Sid    = "TemporaryJobObjects"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
        ]
        Resource = "${aws_s3_bucket.jobs.arn}/jobs/*"
      },
    ]
  })
}

resource "aws_s3_bucket" "jobs" {
  bucket = "${local.name}-jobs"

  tags = merge({ "Project" = var.project_name, "Purpose" = "temporary" }, var.tags)
}

resource "aws_s3_bucket_public_access_block" "jobs" {
  bucket = aws_s3_bucket.jobs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "jobs" {
  bucket = aws_s3_bucket.jobs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Backup only. The application refuses access after 2h (default) / 4h (max).
resource "aws_s3_bucket_lifecycle_configuration" "jobs" {
  bucket = aws_s3_bucket.jobs.id

  rule {
    id     = "expire-temporary-jobs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.job_retention_days
    }
  }
}

resource "aws_cloudwatch_log_group" "analysis" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# --- Dedicated Node parser Lambda (internal invoke only) --------------------
#
# Gated by ``enable_analysis_runtime`` (default false) so the reviewed shared
# plan stays 11/2/0. There is no API Gateway route, function URL or public
# endpoint: the analysis runtime invokes it synchronously with the same
# envelope as the CLI. No shared transport policy is referenced or replaced.

resource "aws_iam_role" "parser" {
  count = var.enable_analysis_runtime ? 1 : 0
  name  = "${local.name}-parser"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_iam_role_policy" "parser_logs" {
  count = var.enable_analysis_runtime ? 1 : 0
  name  = "${local.name}-parser-logs"
  role  = aws_iam_role.parser[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
      ]
      Resource = "${aws_cloudwatch_log_group.parser[0].arn}:*"
    }]
  })
}

resource "aws_cloudwatch_log_group" "parser" {
  count             = var.enable_analysis_runtime ? 1 : 0
  name              = "/aws/lambda/${local.name}-parser"
  retention_in_days = var.log_retention_days

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_lambda_function" "parser" {
  count = var.enable_analysis_runtime ? 1 : 0

  function_name = "${local.name}-parser"
  role          = aws_iam_role.parser[0].arn
  runtime       = var.parser_runtime
  handler       = "lambda/ris_parser_handler.handler"
  filename      = var.parser_artifact_path

  source_code_hash = filebase64sha256(var.parser_artifact_path)
  timeout          = var.parser_timeout_seconds
  memory_size      = var.parser_memory_size
  architectures    = ["arm64"]

  environment {
    variables = {
      NODE_OPTIONS = "--enable-source-maps"
    }
  }

  depends_on = [aws_cloudwatch_log_group.parser]

  tags = merge({ "Project" = var.project_name,
  "Purpose" = "internal-parser" }, var.tags)
}

resource "aws_iam_role_policy" "analysis_invoke_parser" {
  count = var.enable_analysis_runtime ? 1 : 0
  name  = "${local.name}-invoke-parser"
  role  = aws_iam_role.analysis.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.parser[0].arn
    }]
  })
}

resource "aws_lambda_permission" "parser_invoke_analysis" {
  count = var.enable_analysis_runtime ? 1 : 0

  statement_id  = "AllowAnalysisRuntimeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.parser[0].function_name
  principal     = aws_iam_role.analysis.arn
}

# --- Dedicated analysis compute (internal partner) --------------------------
#
# Separate function identity from the shared worker. Reuses the existing
# WorkItem/entitlement/result contracts through agents.runtime.pipeline and the
# dedicated analysis role. No public endpoint and no shared transport change.

resource "aws_iam_role_policy" "analysis_runtime_data" {
  count = var.enable_analysis_runtime ? 1 : 0
  name  = "${local.name}-runtime-data"
  role  = aws_iam_role.analysis.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "OwnedPartnerProfiles"
        # The analysis runtime resolves one CV/profile by id through
        # PartnerProfileRepository.get() -> GetItem on the base table. It
        # never queries the table or a secondary index, so Query and any
        # index grant stay unset (least privilege; see
        # RIS-DEV2-IAM-AUTHORIZATION-01).
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = var.partner_profiles_table_arn
      },
      {
        Sid      = "SyntheticWorkItemReadback"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = var.work_items_table_arn
      },
    ]
  })
}

resource "aws_lambda_function" "analysis" {
  count = var.enable_analysis_runtime ? 1 : 0

  function_name = local.name
  role          = aws_iam_role.analysis.arn
  runtime       = "python3.14"
  handler       = "analysis_runner.handler"
  filename      = var.analysis_zip_path

  source_code_hash = filebase64sha256(var.analysis_zip_path)
  timeout          = var.analysis_timeout_seconds
  memory_size      = var.analysis_memory_size

  environment {
    variables = {
      RIS_PARSER_MODE            = "lambda"
      RIS_PARSER_FUNCTION        = aws_lambda_function.parser[0].function_name
      RIS_PARSER_TIMEOUT_SECONDS = "15"
      DOCUMENTS_BUCKET           = var.documents_bucket_name
      ANALYSIS_JOBS_BUCKET       = aws_s3_bucket.jobs.bucket
      WORK_ITEMS_TABLE           = var.work_items_table_name
      PROJECT_NAME               = var.project_name
      PARTNER_PROFILE_TABLE      = var.partner_profiles_table_name
      # Approval-gated: defaults deny until the operator sets these explicitly.
      ANALYSIS_ENTITLEMENTS      = ""
      ANALYSIS_CONSENT           = "false"
      ANALYSIS_NOTICE_APPROVED   = "false"
      ANALYSIS_CALLER_PARTNER_ID = "ris-internal"
      # Synthetic canary profile: off unless a reviewed var-file enables it.
      # Empty/incomplete values are rejected by the Lambda (fail closed).
      ANALYSIS_SYNTHETIC_MODE                   = var.analysis_synthetic_mode ? "true" : "false"
      ANALYSIS_SYNTHETIC_INSTALLATION           = var.analysis_synthetic_installation
      ANALYSIS_SYNTHETIC_TENANT_ID              = var.analysis_synthetic_tenant_id
      ANALYSIS_SYNTHETIC_USER_ID                = var.analysis_synthetic_user_id
      ANALYSIS_SYNTHETIC_PARTNER_APPLICATION_ID = var.analysis_synthetic_partner_application_id
      ANALYSIS_SYNTHETIC_ISSUER                 = var.analysis_synthetic_issuer
      ANALYSIS_SYNTHETIC_ENTITLEMENTS           = var.analysis_synthetic_entitlements
      ANALYSIS_SYNTHETIC_EXPIRES_AT             = var.analysis_synthetic_expires_at
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.analysis,
    aws_iam_role_policy.analysis_runtime_data,
  ]

  tags = merge({ "Project" = var.project_name,
  "Purpose" = "internal-analysis" }, var.tags)
}
