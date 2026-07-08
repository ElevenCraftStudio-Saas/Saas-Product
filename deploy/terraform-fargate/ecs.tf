# One image, three services: api (behind ALB), worker (Celery queues), beat
# (schedule). Same model as docker-compose.staging.yml, minus the host.

resource "aws_ecs_cluster" "main" {
  name = "${local.name}-fg"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

locals {
  image = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"

  # Non-secret env shared by all containers.
  common_env = [
    { name = "ENV", value = var.environment == "production" ? "production" : "staging" },
    { name = "USE_CELERY", value = "true" },
    { name = "LOG_JSON", value = "true" },
    { name = "ENABLE_METRICS", value = "true" },
    { name = "FRONTEND_URL", value = var.frontend_url },
    { name = "UPLOAD_DIR", value = "/app/uploads" },
    # Gunicorn/uvicorn must trust ALB X-Forwarded-* (TLS terminates there).
    { name = "FORWARDED_ALLOW_IPS", value = "*" },
  ]

  # Pulled per-key from the Secrets Manager JSON blob.
  common_secrets = [
    for key in [
      "DATABASE_URL", "REDIS_URL", "S3_BUCKET", "AWS_REGION",
      # s3_service.py reads the legacy AWS_BUCKET_NAME env name directly.
      "AWS_BUCKET_NAME",
      "FIREBASE_PROJECT_ID", "FIREBASE_SERVICE_ACCOUNT_B64",
      "SECRET_KEY", "SENTRY_DSN",
    ] : { name = key, valueFrom = "${aws_secretsmanager_secret.app.arn}:${key}::" }
  ]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-fg-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = local.image
    essential = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = local.common_env
    secrets     = local.common_secrets
    command = [
      "gunicorn", "app.main:app",
      "-k", "uvicorn.workers.UvicornWorker",
      "-w", "2", "-b", "0.0.0.0:8000", "--timeout", "120",
    ]
    healthCheck = {
      command  = ["CMD-SHELL", "curl -sf http://localhost:8000/livez || exit 1"]
      interval = 30
      timeout  = 5
      retries  = 3
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-fg-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name        = "worker"
    image       = local.image
    essential   = true
    environment = local.common_env
    secrets     = local.common_secrets
    command = [
      "celery", "-A", "app.workers.celery_app", "worker",
      "-Q", "default,face,thumbs,maintenance", "-c", "2", "--loglevel=INFO",
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "beat" {
  family                   = "${local.name}-fg-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name        = "beat"
    image       = local.image
    essential   = true
    environment = local.common_env
    secrets     = local.common_secrets
    command     = ["celery", "-A", "app.workers.celery_app", "beat", "--loglevel=INFO"]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "beat"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.app.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 120 # InsightFace model load on cold start

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.https]
}

resource "aws_ecs_service" "worker" {
  name            = "worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.app.id]
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}

resource "aws_ecs_service" "beat" {
  name            = "beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = 1 # never scale beat: duplicate schedulers double-fire jobs
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.app.id]
  }
}

# Queue-depth-free autoscaling: scale the API on CPU. Worker scaling stays
# manual until a queue-depth metric exists (see monitoring runbook).
resource "aws_appautoscaling_target" "api" {
  max_capacity       = 6
  min_capacity       = var.api_desired_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${local.name}-fg-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 65
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
