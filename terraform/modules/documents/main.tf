# Documents Module — privater Dokumenten-Storage (Gate 14).

# Muster: Root-Data-Bucket (Versioning + PAB + SSE), als eigenes Modul mit
# project_name-Namen (Isolation). KEINE Bucket-Policy (default-privat + PAB
# genuegt; kein CloudTrail-/Cross-Account-Zugriff noetig). KEIN Lifecycle
# (Versionen bleiben bis Delete-Regelung in separatem Backup-Gate).
# Key-Schema (Code): tenant/{tenantId}/users/{userId}/documents/{docId}
# (kein PII im Key; Tenant strukturell).

resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-${var.environment}-documents"

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
