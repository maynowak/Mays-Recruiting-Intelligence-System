variable "project_name" {
  description = "Name des Projekts; wird als Tabellenname verwendet."
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "table_config" {
  description = "DynamoDB table configuration"
  type = object({
    ttl_enabled   = bool
    ttl_attribute = string
  })
}

variable "tags" {
  description = "Zusaetzliche Tags, die der DynamoDB-Tabelle mitgegeben werden."
  type        = map(string)
  default     = {}
}
# ---------------------------------------------------------------------------
# B5: opt-in synthetic foundation entitlements
# ---------------------------------------------------------------------------
# Empty by default, so a production workspace provisions NOTHING. Only a
# workspace that explicitly passes this map gets a foundation entitlement.
#
# Why a variable and not a hardcoded local: the entitlement is USER-bound.
# check_worker_entitlement (agents/ecosystem/worker_authorization.py:91)
# reads userId from the verified credential context, which is the APIProfile
# owner, which is the Cognito `sub` of the authenticated owner. Cognito subs
# are assigned by AWS and cannot be chosen or Terraform-managed (the repo has
# no aws_cognito user resource), so the value cannot be known at authoring
# time. It is therefore an explicit input.
#
# The row shape mirrors the EXISTING grant contract
# (agents/ecosystem/offers.py grant_offer, :588-611) — no invented
# attributes, and deliberately no `status` field: the entitlement contract
# has none, `is_entitlement_valid` decides on the time window only.
#
# Deliberately NOT written: offerId / grantId. Those belong to the offer
# grant domain and there is no offer behind a foundation fixture; inventing
# plausible-looking values would misrepresent provenance. The read path does
# not read them (worker_authorization.py:40-89, introspection.py:91).
variable "foundation_entitlements" {
  description = "Opt-in synthetic foundation entitlements (B5). Map key becomes entitlementId."
  type = map(object({
    userId       = string
    tenantId     = string
    agentId      = string
    validFrom    = optional(string)
    validUntil   = optional(string)
    apiProfileId = optional(string)
  }))
  default = {}
}
