# Photos bucket for this stack. During migration you can instead point the
# secret's S3_BUCKET at the existing EC2-stack bucket and skip the data copy —
# see the runbook. This resource exists so a fresh environment is complete.

resource "aws_s3_bucket" "photos" {
  bucket = "${local.name}-fg-photos"
  tags   = { Name = "${local.name}-fg-photos" }
}

resource "aws_s3_bucket_public_access_block" "photos" {
  bucket                  = aws_s3_bucket.photos.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "photos" {
  bucket = aws_s3_bucket.photos.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "HEAD"]
    allowed_origins = [var.frontend_url]
    max_age_seconds = 3600
  }
}
