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

# ---------------------------------------------------------------------------
# Agent Catalog entries (Terraform = Source of Truth, Gate B4-TERRAFORM-01)
# ---------------------------------------------------------------------------
# Architecture rule: persistent agent-catalog items are declared HERE and
# nowhere else. Runtime code reads the catalog but must never provision it
# (no runtime writer, no API writer, no manual DynamoDB write).
#
# Item shape is NOT invented: it is exactly the attribute set the existing
# read path already consumes.
#   lambda/handler.py:42-88  _init_catalog           (live cold start)
#   agents/ecosystem/catalog_adapter.py:_convert_to_descriptor
# Union verified = agentId, capabilities, description, metadata, name,
# risk_level, status, supported_bodies, supported_runtimes, version
#
# Seed agent: `reference_agent` — the canonical reference agent that
# already exists in the runtime definition (agents/runtime/pipeline.py:
# REFERENCE_AGENT_ID / REFERENCE_CAPABILITY / BODY_VERSION / RUNTIME_LAMBDA).
# It is a technical proof agent with no domain logic, so seeding it creates
# no false expectation of a domain integration. No new agent type invented.
#
# `expiresAt` is deliberately NOT set: the table TTL is enabled on it, so a
# populated value would silently expire this entry. Retention is a separate
# gate; this module does not invent a retention policy.
#
# No secret, token, credential or personal data may be added here.
# ---------------------------------------------------------------------------
locals {
  agent_catalog_seed = {
    reference_agent = {
      agentId            = "reference_agent"
      name               = "reference_agent"
      version            = "1.0.0"
      status             = "ACTIVE"
      description        = "Technischer Nachweis-Agent (Echo, keine Domain-Logik)"
      capabilities       = ["reference.echo"]
      supported_bodies   = ["1.0.0"]
      supported_runtimes = ["python3.14"]
      risk_level         = "low"
      metadata           = {}
    }
  }
}

resource "aws_dynamodb_table_item" "agent_catalog_seed" {
  for_each = local.agent_catalog_seed

  table_name = aws_dynamodb_table.agent_catalog.name
  hash_key   = aws_dynamodb_table.agent_catalog.hash_key

  # aws_dynamodb_table_item takes exactly two kinds of input: the table
  # key names and `item` — the WHOLE item as DynamoDB AttributeValue JSON
  # ({"S":"..."}, {"L":[...]}, {"M":{...}}). Free attributes are not valid
  # arguments; `item` is the only correct vehicle, so the AttributeValue
  # wrapping is built explicitly here from the readable local above, which
  # stays the single source of truth for the values.
  #
  # No range_key: agent_catalog has a hash key only (verified live —
  # KeySchema = [{agentId, HASH}]). Declaring one would write a sort-key
  # attribute the table does not have.
  item = jsonencode({
    agentId     = { S = each.value.agentId }
    name        = { S = each.value.name }
    version     = { S = each.value.version }
    status      = { S = each.value.status }
    description = { S = each.value.description }
    risk_level  = { S = each.value.risk_level }

    capabilities       = { L = [for c in each.value.capabilities : { S = c }] }
    supported_bodies   = { L = [for b in each.value.supported_bodies : { S = b }] }
    supported_runtimes = { L = [for r in each.value.supported_runtimes : { S = r }] }

    # metadata stays empty on purpose. Terraform cannot convert a native
    # map into AttributeValue M recursively, so a non-empty metadata map
    # would have to be written in AttributeValue nesting here. Nothing in
    # the current read path needs metadata; inventing content for it would
    # be schema invention, so it is declared empty.
    metadata = { M = {} }
  })

  depends_on = [aws_dynamodb_table.agent_catalog]
}

# ---------------------------------------------------------------------------
# Foundation entitlements (B5, Gate RIS-ENTITLEMENT-...-09)
# ---------------------------------------------------------------------------
# Option B of the provisioning decision: Terraform is the provisioning plane,
# the Lambda runtime stays read-only. Same pattern as the agent catalog seed
# above, and deliberately NOT the offer grant path: grant_offer
# (agents/ecosystem/offers.py:480) exists but has no productive caller, needs
# an ACTIVE offer (offers table is empty and has no provisioning path either)
# and would require dynamodb:TransactWriteItems on the Lambda role, which the
# runtime must not have.
#
# Nothing is provisioned unless var.foundation_entitlements is set.
#
# Cleanup follows the IaC lifecycle: removing an entry from the variable and
# applying removes exactly that row. There is no manual DynamoDB delete.
resource "aws_dynamodb_table_item" "foundation_entitlement" {
  for_each = var.foundation_entitlements

  table_name = aws_dynamodb_table.entitlements.name
  hash_key   = aws_dynamodb_table.entitlements.hash_key

  # No range_key: the entitlements table has a hash key only (verified live —
  # KeySchema = [{entitlementId, HASH}]).
  # `item` is DynamoDB AttributeValue JSON; free attributes are not valid
  # arguments for this resource type.
  item = jsonencode({
    entitlementId = { S = each.key }
    userId        = { S = each.value.userId }
    tenantId      = { S = each.value.tenantId }
    agentId       = { S = each.value.agentId }
    validFrom     = { S = each.value.validFrom }
    validUntil    = { S = each.value.validUntil }
    # expiresAt is the TTL attribute of this table (verified live: TTL
    # ENABLED) and the grant path writes _epoch(validUntil) there. It is
    # deliberately NOT written here: Terraform has no epoch conversion, and
    # hand-rolled arithmetic would be invention. A populated expiresAt would
    # also silently delete the fixture, whereas its removal is an explicit IaC
    # act (see the cleanup note above). Same reasoning as the catalog seed.
    createdBy = { M = { actor = { S = "terraform" }, role = { S = "provisioning" } } }
  })

  depends_on = [aws_dynamodb_table.entitlements]
}
