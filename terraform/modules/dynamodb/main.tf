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
    name             = "gsi-status"
    hash_key         = "tenantId"
    range_key        = "status"
    projection_type  = "ALL"
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

output "work_items_table_name" {
  value = aws_dynamodb_table.work_items.name
}

output "work_items_table_arn" {
  value = aws_dynamodb_table.work_items.arn
}

output "agent_state_table_name" {
  value = aws_dynamodb_table.agent_state.name
}