# Private photo bucket. App accesses it via the EC2 instance role (no static keys).
resource "aws_s3_bucket" "photos" {
  bucket = "${local.name}-photos-${data.aws_caller_identity.current.account_id}"
  tags   = { Name = "${local.name}-photos" }
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_public_access_block" "photos" {
  bucket                  = aws_s3_bucket.photos.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "photos" {
  bucket = aws_s3_bucket.photos.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

# Presigned guest downloads need permissive CORS for GET from the frontend.
resource "aws_s3_bucket_cors_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  cors_rule {
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = [var.frontend_url]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}

# Expire incomplete multipart uploads; keep noncurrent versions briefly.
resource "aws_s3_bucket_lifecycle_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  rule {
    id     = "abort-incomplete-mpu"
    status = "Enabled"
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}
