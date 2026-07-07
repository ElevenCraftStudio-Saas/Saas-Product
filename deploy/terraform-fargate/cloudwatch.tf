resource "aws_cloudwatch_log_group" "app" {
  name              = "/wedfind/${var.environment}-fargate/app"
  retention_in_days = 30
  tags              = { Name = "${local.name}-fg-logs" }
}

resource "aws_sns_topic" "alarms" {
  name = "${local.name}-fg-alarms"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# App is unhealthy as seen by the ALB — catches DB/Redis/S3 degradation
# because /readyz checks all three (the EC2 stack's status-check alarm never
# could).
resource "aws_cloudwatch_metric_alarm" "unhealthy_targets" {
  alarm_name          = "${local.name}-fg-unhealthy-targets"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  period              = 60
  statistic           = "Maximum"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "UnHealthyHostCount"
  threshold           = 0
  dimensions = {
    TargetGroup  = aws_lb_target_group.api.arn_suffix
    LoadBalancer = aws_lb.app.arn_suffix
  }
  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${local.name}-fg-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  period              = 300
  statistic           = "Sum"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  threshold           = 20
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.app.arn_suffix
  }
  alarm_actions = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "aurora_capacity" {
  alarm_name          = "${local.name}-fg-aurora-acu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  period              = 300
  statistic           = "Average"
  namespace           = "AWS/RDS"
  metric_name         = "ServerlessDatabaseCapacity"
  threshold           = var.aurora_max_acu * 0.9
  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.cluster_identifier
  }
  alarm_actions = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "worker_cpu" {
  alarm_name          = "${local.name}-fg-worker-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  period              = 300
  statistic           = "Average"
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  threshold           = 85
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.worker.name
  }
  alarm_actions = [aws_sns_topic.alarms.arn]
}
