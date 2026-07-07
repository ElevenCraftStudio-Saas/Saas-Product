# One JSON blob, same model as the EC2 stack. Terraform seeds connection
# values; sensitive keys (SECRET_KEY, Firebase SA, Sentry) are placeholders you
# fill in the console — ignore_changes keeps manual edits out of TF diffs.

resource "aws_secretsmanager_secret" "app" {
  name                    = local.app_secret_name
  recovery_window_in_days = 0
  tags                    = { Name = local.app_secret_name }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id

  secret_string = jsonencode({
    DATABASE_URL                 = "postgresql+psycopg://${var.db_username}:${var.db_password}@${aws_rds_cluster.main.endpoint}:5432/${var.db_name}"
    REDIS_URL                    = local.redis_url
    S3_BUCKET                    = aws_s3_bucket.photos.bucket
    AWS_REGION                   = var.region
    FIREBASE_PROJECT_ID          = "saas-139a7"
    FIREBASE_SERVICE_ACCOUNT_B64 = "REPLACE_ME_base64_service_account_json"
    SECRET_KEY                   = "REPLACE_ME_openssl_rand_hex_32"
    SENTRY_DSN                   = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
