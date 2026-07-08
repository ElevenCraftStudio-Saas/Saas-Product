variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  description = "staging | production — drives naming and sizing"
  type        = string
  default     = "staging"
}

variable "app_domain" {
  description = "Public API domain (e.g. api.wedfind.elevencraftstudio.com). Required: the ALB serves HTTPS via an ACM cert for this name."
  type        = string
}

variable "frontend_url" {
  description = "Frontend origin for CORS"
  type        = string
  default     = "https://wedfind.elevencraftstudio.com"
}

variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16" # distinct from the EC2 stack's 10.20/16 so both can coexist
}

variable "az_count" {
  type    = number
  default = 2
}

# --- Container sizing ---

variable "api_cpu" {
  description = "Fargate CPU units for the API task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  # 2 gunicorn workers each load InsightFace at import — 1024 OOM-loops
  # (SIGKILL) on task start. 4096 verified stable.
  type    = number
  default = 4096
}

variable "api_desired_count" {
  description = ">=2 for HA; SSE state is Redis-backed so replicas are safe"
  type        = number
  default     = 2
}

variable "worker_cpu" {
  description = "Face matching is CPU-bound; 2 vCPU keeps InsightFace responsive"
  type        = number
  default     = 2048
}

variable "worker_memory" {
  type    = number
  default = 6144 # InsightFace + OpenCV need headroom
}

variable "worker_desired_count" {
  type    = number
  default = 1
}

# --- Data tier ---

variable "aurora_min_acu" {
  type    = number
  default = 0.5
}

variable "aurora_max_acu" {
  type    = number
  default = 4
}

variable "db_name" {
  type    = string
  default = "wedfind"
}

variable "db_username" {
  type    = string
  default = "wedfind"
}

variable "db_password" {
  description = "Master password (move to Secrets Manager rotation later)"
  type        = string
  sensitive   = true
}

variable "redis_mode" {
  description = <<-EOT
    node       = single ElastiCache node (default). Celery broker works unchanged.
    serverless = ElastiCache Serverless. NOTE: serverless Redis speaks the
                 cluster protocol, which Celery/kombu does NOT support — pick
                 this only after migrating the Celery broker to SQS. The SSE
                 state store would also need a cluster-aware client.
  EOT
  type        = string
  default     = "node"
  validation {
    condition     = contains(["node", "serverless"], var.redis_mode)
    error_message = "redis_mode must be node or serverless"
  }
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "backend_image_tag" {
  description = "Image tag in the ECR repo to deploy (e.g. 2026-07-05-abc1234)"
  type        = string
  default     = "latest"
}

variable "alarm_email" {
  description = "Optional email for SNS alarm subscription (confirm by hand)"
  type        = string
  default     = ""
}
