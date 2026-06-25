resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name}-redis-subnets"
  subnet_ids = aws_subnet.private[*].id
}

# Single-node Redis (Celery broker + result backend). Staging keeps it cheap;
# bump to a replication group with automatic failover for production.
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${local.name}-redis"
  engine               = "redis"
  engine_version       = var.redis_engine_version
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  port                 = 6379
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  snapshot_retention_limit = var.environment == "production" ? 5 : 0
  apply_immediately        = var.environment != "production"

  tags = { Name = "${local.name}-redis" }
}
