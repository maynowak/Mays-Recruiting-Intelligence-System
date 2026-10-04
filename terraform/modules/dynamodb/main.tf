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
# P18: APIProfile Table - platform API usage contexts (P10 domain).
# NO TTL (expired profiles stay EXPIRED records for audit; deletion only
# via explicit admin cleanup). Queries: Get by id, Query gsi-owner.
resource "aws_dynamodb_table" "api_profiles" {
  name         = "${var.project_name}-${var.environment}-api-profiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "apiProfileId"

  attribute {
    name = "apiProfileId"
    type = "S"
  }

  attribute {
    name = "ownerUserId"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi-owner"
    hash_key        = "ownerUserId"
    projection_type = "ALL"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# P18: Offer Table - grantable agent-right packages (P11 domain).
# No GSI (reads: Get by id + full list scan; name uniqueness enforced
# in service). No TTL (offers live until admin act).
resource "aws_dynamodb_table" "offers" {
  name         = "${var.project_name}-${var.environment}-offers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "offerId"

  attribute {
    name = "offerId"
    type = "S"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

# P18: Credential Table - opaque bearer metadata (P09/P14 domain).
# Digest-only storage (NEVER raw secrets — enforced in code, not schema).
# Lookup by digest requires gsi-digest (per-request verify path).
# No TTL (expiresAt is an ISO string for contract checks, not epoch).
resource "aws_dynamodb_table" "credentials" {
  name         = "${var.project_name}-${var.environment}-credentials"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "credentialId"

  attribute {
    name = "credentialId"
    type = "S"
  }

  attribute {
    name = "digest"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi-digest"
    hash_key        = "digest"
    projection_type = "ALL"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

output "api_profiles_table_name" {
  value = aws_dynamodb_table.api_profiles.name
}

output "api_profiles_table_arn" {
  value = aws_dynamodb_table.api_profiles.arn
}

output "offers_table_name" {
  value = aws_dynamodb_table.offers.name
}

output "offers_table_arn" {
  value = aws_dynamodb_table.offers.arn
}

output "credentials_table_name" {
  value = aws_dynamodb_table.credentials.name
}

output "credentials_table_arn" {
  value = aws_dynamodb_table.credentials.arn
}
