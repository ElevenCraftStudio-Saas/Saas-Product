output "app_public_ip" {
  description = "Elastic IP of the Docker host"
  value       = aws_eip.app.public_ip
}

output "app_instance_id" {
  description = "EC2 instance id (use with: aws ssm start-session)"
  value       = aws_instance.app.id
}

output "rds_endpoint" {
  description = "Postgres endpoint (private)"
  value       = aws_db_instance.main.address
}

output "redis_endpoint" {
  description = "Redis endpoint (private)"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "s3_bucket" {
  description = "Photo bucket name"
  value       = aws_s3_bucket.photos.bucket
}

output "app_secret_name" {
  description = "Secrets Manager secret holding app config"
  value       = aws_secretsmanager_secret.app.name
}

output "alarms_sns_topic_arn" {
  description = "Subscribe an endpoint here to receive CloudWatch alarms"
  value       = aws_sns_topic.alarms.arn
}

output "db_password_secret_hint" {
  description = "DB password is embedded in DATABASE_URL inside the app secret"
  value       = "aws secretsmanager get-secret-value --secret-id ${aws_secretsmanager_secret.app.name} --query SecretString --output text | jq -r .DATABASE_URL"
}

output "app_url" {
  description = "Resolved app URL"
  value       = local.enable_dns ? "https://${var.app_domain}" : "http://${aws_eip.app.public_ip}"
}
