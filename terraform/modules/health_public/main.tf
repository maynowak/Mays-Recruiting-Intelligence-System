resource "aws_s3_bucket" "public_presentation" {
  bucket = "${var.project_name}-${var.environment}-health-public"
  tags   = var.tags
}

resource "aws_s3_object" "health_html" {
  bucket        = aws_s3_bucket.public_presentation.id
  key           = "health.html"
  source        = "${path.module}/health.html"
  content_type  = "text/html"
  cache_control = "no-cache"
}

resource "aws_s3_bucket_public_access_block" "public_presentation" {
  bucket                  = aws_s3_bucket.public_presentation.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "public_presentation" {
  bucket = aws_s3_bucket.public_presentation.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "public_presentation" {
  bucket = aws_s3_bucket.public_presentation.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "cloudfront.amazonaws.com"
      }
      Action   = ["s3:GetObject"]
      Resource = "${aws_s3_bucket.public_presentation.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.health_public.arn
        }
      }
    }]
  })
}

resource "aws_cloudfront_origin_access_control" "health_public" {
  name                              = "${var.project_name}-${var.environment}-health-oac"
  description                       = "OAC for public health presentation"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "health_public" {
  enabled             = true
  default_root_object = "health.html"

  origin {
    domain_name              = aws_s3_bucket.public_presentation.bucket_regional_domain_name
    origin_id                = "S3-health-public"
    origin_access_control_id = aws_cloudfront_origin_access_control.health_public.id
  }

  default_cache_behavior {
    target_origin_id       = "S3-health-public"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = var.tags
}
