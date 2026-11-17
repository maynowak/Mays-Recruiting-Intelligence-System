# Orders-Reader Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}

variable "api_id" {
  description = "ID unserer API (mays-ris-dev-api) fuer Integration und Routen"
  type        = string
}

variable "authorizer_id" {
  description = "JWT-Authorizer unserer API"
  type        = string
}

# THIS is where the Orders binding is actually enforced.
#
# The root variables (../../variables.tf) carry a condition that can never
# be false, so they do not reject anything. These four conditions are the
# mirror image: `x != "" || can(regex(...))` rejects the empty value with
# "Invalid value for variable". An install without an Orders binding
# therefore fails HERE, not at the root.
#
# Read as a pair, the layering is:
#   root    empty tolerated on purpose ("empty default = fail-closed binding")
#   module  empty refused                    -> the fail-closed actually bites
#
# Consequence: the regex arms only rescue the standalone name "mays-orders".
# Any other non-empty value passes, so identity is not checked here either --
# same gap as installer/ris.py:validate_orders_binding, mirrored down to this
# layer. Format yes, identity no.
variable "orders_table_name" {
  description = "Name der Mays-Orders-Tabelle (lesend/schreibend, gleiches Konto)"
  type        = string

  validation {
    condition     = var.orders_table_name != "" || can(regex("^mays-orders$", var.orders_table_name))
    error_message = "orders_table_name must be explicitly configured or match mays-orders for standalone mode"
  }
}

variable "orders_table_arn" {
  description = "ARN der Mays-Orders-Tabelle"
  type        = string

  validation {
    condition     = var.orders_table_arn != "" || can(regex("^arn:aws:dynamodb:", var.orders_table_arn))
    error_message = "orders_table_arn must be explicitly configured or be a valid ARN"
  }
}

variable "orders_queue_url" {
  description = "URL der Mays-Orders-Queue fuer Worker-Anstoss (nur SendMessage)"
  type        = string

  validation {
    condition     = var.orders_queue_url != "" || can(regex("^https://sqs\\..*\\.amazonaws\\.com/", var.orders_queue_url))
    error_message = "orders_queue_url must be explicitly configured or be a valid SQS URL"
  }
}

variable "orders_queue_arn" {
  description = "ARN der Mays-Orders-Queue (nur SendMessage-Recht)"
  type        = string

  validation {
    condition     = var.orders_queue_arn != "" || can(regex("^arn:aws:sqs:", var.orders_queue_arn))
    error_message = "orders_queue_arn must be explicitly configured or be a valid ARN"
  }
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.14"
}

variable "cognito_issuer" {
  description = "Cognito issuer expected in the verified JWT"
  type        = string
}

variable "cognito_client_id" {
  description = "Cognito app client id expected in the verified JWT"
  type        = string
}

variable "timeout" {
  description = "Lambda timeout in Sekunden"
  type        = number
  default     = 10
}

variable "memory_size" {
  description = "Lambda memory in MB"
  type        = number
  default     = 128
}

variable "filename" {
  description = "Deployment-Zip mit orders_reader.py am Root"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch-Log-Retention in Tagen"
  type        = number
  default     = 7
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "dispatch_enabled" {
  description = "Enable agent-order dispatch from the reader (requires the RIS dispatch queue)."
  type        = bool
  default     = false
}

variable "dispatch_queue_url" {
  description = "URL of the RIS agent dispatch queue (ORDER_DISPATCH ingress)."
  type        = string
  default     = ""
}

variable "dispatch_queue_arn" {
  description = "ARN of the RIS agent dispatch queue (SendMessage scope)."
  type        = string
  default     = ""
}

variable "api_profiles_table_name" {
  description = "API profile table read to validate the agent-order owner/profile binding."
  type        = string
  default     = ""
}

variable "api_profiles_table_arn" {
  description = "API profile table ARN (GetItem scope)."
  type        = string
  default     = ""
}
