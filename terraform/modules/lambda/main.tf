# Lambda Module - Ground Zero Agent Runtime

locals {
  lambda_name = "${var.project_name}-${var.environment}-agent"
}

resource "aws_iam_role" "lambda_execution" {
  name = local.lambda_name

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

resource "aws_iam_role_policy" "lambda_dynamodb_platform" {
  name = "${var.project_name}-${var.environment}-lambda-dynamodb-platform"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:BatchGetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          var.user_profile_table_arn,
          "${var.user_profile_table_arn}/index/*"
        ]
      },
      {
        # Gate P18: der produktive Catalog-Pfad liest per Scan
        # (catalog_adapter.py scan_all_agent_ids/get_all_agents und
        # handler._get_agent_catalog). Ohne Scan degradierte GET /agents
        # still auf 200 mit leerer Liste (AccessDeniedException).
        # Scan trifft nur den Basis-Tabellen-ARN -> keine Index-ARNs noetig.
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:BatchGetItem",
          "dynamodb:Scan"
        ]
        Resource = [
          var.agent_catalog_table_arn,
          "${var.agent_catalog_table_arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:BatchGetItem"
        ]
        Resource = [
          var.entitlements_table_arn,
          "${var.entitlements_table_arn}/index/*"
        ]
      }
    ]
  })
}

# P23-01: entitlements become writable, and only for the operations the
# Product Admin grant actually reaches.
#
# Belegt durch Code -> Route -> Handler -> Domain Store (Auftrag §12):
#   POST /v1/offers/{id}/grant
#     -> _handle_offer_grant -> offers.grant_offer
#     -> DynamoDBEntitlementStore.put_entitlements_batch
#        -> transact_write_items        (atomic all-or-nothing grant)
#     -> find_by_user  -> query (gsi-user)     [already allowed]
#     -> find_by_key   -> scan (idempotency)   [NOT yet allowed]
#     -> get_entitlement -> get_item            [already allowed]
#   POST /v1/offers/{id}/withdraw
#     -> withdraw_entitlement -> delete_item    [NOT yet allowed]
#
# So exactly three additions are justified: TransactWriteItems (grant),
# Scan (grant idempotency lookup) and DeleteItem (withdraw). No dynamodb:*,
# no extra tables, no unused writes. This stays product authorization only:
# `admins` is a Cognito group and confers no AWS rights.
resource "aws_iam_role_policy" "lambda_dynamodb_entitlements_admin" {
  name = "${var.project_name}-${var.environment}-lambda-dynamodb-entitlements-admin"
  role = aws_iam_role.lambda_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:TransactWriteItems",
          "dynamodb:PutItem",
          "dynamodb:Scan",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          var.entitlements_table_arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_dynamodb_work" {
  name = "${var.project_name}-${var.environment}-lambda-dynamodb-work"
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
          "dynamodb:Query",
          "dynamodb:DeleteItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/table/${var.dynamodb_table_arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_sqs_send" {
  name = "${var.project_name}-${var.environment}-lambda-sqs-send"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          var.sqs_queue_arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "${var.project_name}-${var.environment}-lambda-s3"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${var.s3_bucket_arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_dynamodb_jobsearch" {
  name = "${var.project_name}-${var.environment}-lambda-dynamodb-jobsearch"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          var.jobsearch_table_arn,
          "${var.jobsearch_table_arn}/index/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_documents" {
  name = "${var.project_name}-${var.environment}-lambda-documents"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${var.documents_bucket_arn}/tenant/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [var.documents_bucket_arn]
      }
    ]
  })
}

# P18: platform product tables (APIProfile/Offer/Credential, P10/P11/P09
# domains). Least privilege per ACTUAL code use (adapters):
# api-profiles: GetItem (get), Query (list_by_owner via gsi-owner),
#   PutItem (create/conditional + full update).
# offers: GetItem (get), Scan (list_offers), PutItem (create/update).
# credentials: GetItem (get), Query (get_by_digest via gsi-digest),
#   PutItem (issue/rotate), UpdateItem (status/mark_used), Scan
#   (management list/find_by_key — rare admin/support reads).
# NO DeleteItem (no delete path: REVOKED persists for audit),
# NO Batch*, NO Transact* (grant writes target the EXISTING
# entitlements table — separate follow-up, NOT this gate),
# NO dynamodb:*, scoped to the three table ARNs + their indexes.
resource "aws_iam_role_policy" "lambda_dynamodb_product" {
  name = "${var.project_name}-${var.environment}-lambda-dynamodb-product"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          var.api_profiles_table_arn,
          "${var.api_profiles_table_arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          var.offers_table_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          var.credentials_table_arn,
          "${var.credentials_table_arn}/index/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_logs" {
  name = "${var.project_name}-${var.environment}-lambda-logs"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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

resource "aws_lambda_function" "agent" {
  function_name = local.lambda_name
  role          = aws_iam_role.lambda_execution.arn
  handler       = var.lambda_config.handler
  runtime       = var.lambda_config.runtime
  timeout       = var.lambda_config.timeout
  memory_size   = var.lambda_config.memory_size

  filename         = var.lambda_config.filename
  source_code_hash = filebase64sha256(var.lambda_config.filename)

  environment {
    variables = {
      WORK_ITEMS_TABLE    = var.dynamodb_table_name
      USER_PROFILE_TABLE  = var.user_profile_table_name
      AGENT_CATALOG_TABLE = var.agent_catalog_table_name
      ENTITLEMENTS_TABLE  = var.entitlements_table_name
      WORK_QUEUE_URL      = var.work_queue_url
      JOBSEARCH_TABLE     = var.jobsearch_table_name
      DOCUMENTS_BUCKET    = var.documents_bucket_name
      API_PROFILES_TABLE  = var.api_profiles_table_name
      OFFERS_TABLE        = var.offers_table_name
      CREDENTIALS_TABLE   = var.credentials_table_name
      LOG_LEVEL           = var.log_level
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_dynamodb_platform,
    aws_iam_role_policy.lambda_dynamodb_work,
    aws_iam_role_policy.lambda_dynamodb_jobsearch,
    aws_iam_role_policy.lambda_dynamodb_product,
    aws_iam_role_policy.lambda_documents,
    aws_iam_role_policy.lambda_s3,
    aws_iam_role_policy.lambda_logs,
    aws_cloudwatch_log_group.lambda_logs
  ]

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = var.lambda_config.log_retention_days

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_lambda_event_source_mapping" "sqs_mapping" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.agent.arn
  batch_size       = 5
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

output "lambda_role_arn" {
  value = aws_iam_role.lambda_execution.arn
}