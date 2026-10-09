output "bucket_name" {
  value = aws_s3_bucket.public_presentation.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.public_presentation.arn
}
