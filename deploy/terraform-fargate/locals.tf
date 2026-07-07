locals {
  name            = "wedfind-${var.environment}"
  app_secret_name = "${local.name}-fargate/app"

  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  # Redis endpoint differs by mode; both render a rediss/redis URL for the app.
  redis_url = var.redis_mode == "serverless" ? "rediss://${aws_elasticache_serverless_cache.redis[0].endpoint[0].address}:6379/0" : "redis://${aws_elasticache_cluster.redis[0].cache_nodes[0].address}:6379/0"
}

data "aws_availability_zones" "available" {
  state = "available"
}
