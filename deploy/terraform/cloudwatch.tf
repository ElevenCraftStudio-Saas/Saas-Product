resource "aws_cloudwatch_log_group" "app" {
  name              = "/wedfind/${var.environment}/app"
  retention_in_days = 30
  tags              = { Name = "${local.name}-logs" }
}

# Optional SNS topic for alarm notifications. Subscribe an email/Slack webhook
# out-of-band (kept out of TF to avoid storing endpoints in state).
resource "aws_sns_topic" "alarms" {
  name = "${local.name}-alarms"
}

# --- App host CPU (face matching is CPU-bound — watch for saturation) ---
resource "aws_cloudwatch_metric_alarm" "app_cpu_high" {
  alarm_name          = "${local.name}-app-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "App host CPU > 85% for 15m"
  dimensions          = { InstanceId = aws_instance.app.id }
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

# --- App host status check ---
resource "aws_cloudwatch_metric_alarm" "app_status" {
  alarm_name          = "${local.name}-app-status-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "App host status check failing"
  dimensions          = { InstanceId = aws_instance.app.id }
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

# --- RDS free storage ---
resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  alarm_name          = "${local.name}-rds-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 2147483648 # 2 GB
  alarm_description   = "RDS free storage < 2GB"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.main.identifier }
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

# --- RDS CPU ---
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${local.name}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "RDS CPU > 85% for 15m"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.main.identifier }
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

# --- Redis memory ---
resource "aws_cloudwatch_metric_alarm" "redis_mem_high" {
  alarm_name          = "${local.name}-redis-mem-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Redis memory > 80%"
  dimensions          = { CacheClusterId = aws_elasticache_cluster.redis.cluster_id }
  alarm_actions       = [aws_sns_topic.alarms.arn]
}
