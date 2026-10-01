# DynamoDB Module

resource "aws_dynamodb_table" "work_items" {
  name         = "${var.project_name}-${var.environment}-work-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "workId"

  attribute {
    name = "workId"
    type = "S"
  }

  attribute {
    name = "tenantId"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  ttl {
    attribute_name = var.table_config.ttl_attribute
    enabled        = var.table_config.ttl_enabled
  }

  global_secondary_index {
    name            = "gsi-status"
    hash_key        = "tenantId"
    range_key       = "status"
    projection_type = "ALL"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_dynamodb_table" "agent_state" {
  name         = "${var.project_name}-${var.environment}-agent-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "key"

  attribute {
    name = "key"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# User Profile Table - stores application-level user data
resource "aws_dynamodb_table" "user_profile" {
  name         = "${var.project_name}-${var.environment}-user-profile"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "userId"

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "tenantId"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  global_secondary_index {
    name            = "gsi-tenant"
    hash_key        = "tenantId"
    projection_type = "ALL"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# Agent Catalog Table - stores available agent metadata
resource "aws_dynamodb_table" "agent_catalog" {
  name         = "${var.project_name}-${var.environment}-agent-catalog"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "agentId"

  attribute {
    name = "agentId"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  global_secondary_index {
    name            = "gsi-status"
    hash_key        = "status"
    projection_type = "ALL"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# Entitlements Table - stores user-agent access permissions
resource "aws_dynamodb_table" "entitlements" {
  name         = "${var.project_name}-${var.environment}-entitlements"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "entitlementId"

  attribute {
    name = "entitlementId"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "agentId"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  global_secondary_index {
    name            = "gsi-user"
    hash_key        = "userId"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "gsi-agent"
    hash_key        = "agentId"
    projection_type = "ALL"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# JobSearch Table (Gate 9) — Schema nach
# jobsearch.repository.create_jobsearch_table_definitions().
resource "aws_dynamodb_table" "jobsearches" {
  name         = "${var.project_name}-${var.environment}-jobsearches"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "jobSearchId"

  attribute {
    name = "jobSearchId"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "tenantId"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  global_secondary_index {
    name            = "gsi-user"
    hash_key        = "userId"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "gsi-status"
    hash_key        = "tenantId"
    range_key       = "status"
    projection_type = "ALL"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

output "work_items_table_name" {
  value = aws_dynamodb_table.work_items.name
}

output "work_items_table_arn" {
  value = aws_dynamodb_table.work_items.arn
}

output "agent_state_table_name" {
  value = aws_dynamodb_table.agent_state.name
}