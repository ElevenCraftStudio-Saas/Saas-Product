resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db-subnets"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${local.name}-db-subnets" }
}

# Parameter group: preload pgvector-friendly settings. The 'vector' extension is
# created by the app's Alembic migrations (CREATE EXTENSION vector).
resource "aws_db_parameter_group" "pg" {
  name   = "${local.name}-pg16"
  family = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = { Name = "${local.name}-pg16" }
}

resource "random_password" "db" {
  length  = 32
  special = false # keep it URL-safe for DATABASE_URL
}

resource "aws_db_instance" "main" {
  identifier     = "${local.name}-pg"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage_gb
  max_allocated_storage = var.db_max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.pg.name
  multi_az               = var.db_multi_az
  publicly_accessible    = false

  # --- Automated backups ---
  backup_retention_period   = var.db_backup_retention_days
  backup_window             = "18:00-19:00" # UTC (low traffic for ap-south-1)
  maintenance_window        = "Mon:19:30-Mon:20:30"
  copy_tags_to_snapshot     = true
  delete_automated_backups  = false
  deletion_protection       = var.environment == "production"
  skip_final_snapshot       = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${local.name}-final-${formatdate("YYYYMMDDhhmmss", timestamp())}" : null

  performance_insights_enabled = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  auto_minor_version_upgrade      = true

  tags = { Name = "${local.name}-pg" }

  lifecycle {
    ignore_changes = [final_snapshot_identifier]
  }
}
