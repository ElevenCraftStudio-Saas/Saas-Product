# Aurora Serverless v2 (Postgres 16 + pgvector) and Redis.

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-fg-db-subnets"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${local.name}-fg-db-subnets" }
}

resource "aws_rds_cluster" "main" {
  cluster_identifier = "${local.name}-fg-aurora"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned" # Serverless v2 uses provisioned mode + serverless instances
  engine_version     = "16.4"

  database_name   = var.db_name
  master_username = var.db_username
  master_password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  storage_encrypted      = true

  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_acu
    max_capacity = var.aurora_max_acu
  }

  backup_retention_period      = var.environment == "production" ? 14 : 3
  preferred_backup_window      = "02:00-03:00"
  deletion_protection          = var.environment == "production"
  skip_final_snapshot          = var.environment != "production"
  final_snapshot_identifier    = var.environment == "production" ? "${local.name}-fg-final" : null
  copy_tags_to_snapshot        = true

  tags = { Name = "${local.name}-fg-aurora" }
}

resource "aws_rds_cluster_instance" "main" {
  identifier         = "${local.name}-fg-aurora-1"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
  tags               = { Name = "${local.name}-fg-aurora-1" }
}

# --- Redis ---

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name}-fg-redis-subnets"
  subnet_ids = aws_subnet.private[*].id
}

# Default: single node — Celery/kombu require the non-cluster Redis protocol.
resource "aws_elasticache_cluster" "redis" {
  count                = var.redis_mode == "node" ? 1 : 0
  cluster_id           = "${local.name}-fg-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
  tags                 = { Name = "${local.name}-fg-redis" }
}

# Opt-in: true serverless Redis. ONLY after Celery moves to SQS (cluster
# protocol) — see deploy/runbooks/fargate-migration.md.
resource "aws_elasticache_serverless_cache" "redis" {
  count  = var.redis_mode == "serverless" ? 1 : 0
  engine = "redis"
  name   = "${local.name}-fg-redis-sl"

  cache_usage_limits {
    data_storage {
      maximum = 5
      unit    = "GB"
    }
    ecpu_per_second {
      maximum = 5000
    }
  }

  security_group_ids = [aws_security_group.redis.id]
  subnet_ids         = aws_subnet.private[*].id
  tags               = { Name = "${local.name}-fg-redis-sl" }
}
