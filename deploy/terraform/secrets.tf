# Single JSON secret holding the app's sensitive config. The EC2 instance role
# reads it at boot (see user_data) and renders the runtime .env.
#
# Terraform SEEDS the values it owns (DB/Redis URLs, project id). Values that
# must never live in state — the Firebase service-account key and Sentry DSN —
# are placeholders here and are injected out-of-band via the rotation runbook
# (scripts/rotate-firebase-key.sh). lifecycle.ignore_changes keeps Terraform
# from clobbering those manual updates on subsequent applies.
resource "aws_secretsmanager_secret" "app" {
  name                    = local.app_secret_name
  description             = "WedFind ${var.environment} app config + credentials"
  recovery_window_in_days = var.environment == "production" ? 30 : 0
  tags                    = { Name = local.app_secret_name }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    # --- Terraform-owned (safe to seed) ---
    DATABASE_URL        = "postgresql+psycopg://${var.db_username}:${random_password.db.result}@${aws_db_instance.main.address}:5432/${var.db_name}"
    REDIS_URL           = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
    AWS_REGION          = var.region
    S3_BUCKET           = aws_s3_bucket.photos.bucket
    # s3_service reads AWS_BUCKET_NAME directly; config also accepts S3_BUCKET.
    # Provide both so every code path finds the bucket.
    AWS_BUCKET_NAME     = aws_s3_bucket.photos.bucket
    FIREBASE_PROJECT_ID = var.firebase_project_id
    FRONTEND_URL        = var.frontend_url
    ENV                 = "production" # enables HTTPS redirect + strict CORS in-app

    # --- Injected out-of-band by runbooks (placeholders) ---
    FIREBASE_SERVICE_ACCOUNT_B64 = ""
    SENTRY_DSN                   = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
