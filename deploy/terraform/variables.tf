variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment (staging|production). Drives naming + sizing."
  type        = string
  default     = "staging"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "vpc_cidr" {
  description = "CIDR for the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "az_count" {
  description = "Number of AZs to spread subnets across (RDS multi-AZ needs >=2)."
  type        = number
  default     = 2
}

# --- Access control ---
variable "ssh_allowed_cidrs" {
  description = "CIDRs allowed to SSH to the Docker host. Lock to your office/VPN."
  type        = list(string)
  default     = [] # empty = no SSH ingress (use SSM Session Manager instead)
}

variable "ssh_public_key" {
  description = "Optional SSH public key material. Empty = SSM-only access."
  type        = string
  default     = ""
}

# --- Compute ---
variable "app_instance_type" {
  description = "EC2 type for the Docker host. Face matching is CPU-bound."
  type        = string
  default     = "t3.large" # 2 vCPU / 8 GB — fits API + worker + InsightFace
}

variable "app_root_volume_gb" {
  description = "Root EBS size (image + InsightFace model + uploads buffer)."
  type        = number
  default     = 40
}

# --- RDS ---
variable "db_instance_class" {
  type    = string
  default = "db.t3.small"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "db_max_allocated_storage_gb" {
  description = "Storage autoscaling ceiling."
  type        = number
  default     = 100
}

variable "db_name" {
  type    = string
  default = "wedfind"
}

variable "db_username" {
  type    = string
  default = "wedfind"
}

variable "db_multi_az" {
  description = "Multi-AZ failover. false for staging cost savings, true for prod."
  type        = bool
  default     = false
}

variable "db_backup_retention_days" {
  description = "Automated PostgreSQL backup retention."
  type        = number
  default     = 7
}

variable "db_engine_version" {
  description = "Postgres version (must support the pgvector extension)."
  type        = string
  default     = "16.4"
}

# --- ElastiCache ---
variable "redis_node_type" {
  type    = string
  default = "cache.t3.micro"
}

variable "redis_engine_version" {
  type    = string
  default = "7.1"
}

# --- DNS / app ---
variable "app_domain" {
  description = "FQDN for the API (e.g. staging-api.wedfind.ai). Empty = skip Route53/ACM."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Existing hosted zone id. Empty = skip Route53 record."
  type        = string
  default     = ""
}

variable "frontend_url" {
  description = "Allowed CORS origin for the API (passed to the app as FRONTEND_URL)."
  type        = string
  default     = "http://localhost:3000"
}

variable "firebase_project_id" {
  description = "Firebase project id (non-secret; injected as env)."
  type        = string
}

variable "backend_image" {
  description = "Container image ref for the backend (ECR or registry)."
  type        = string
  default     = "wedfind-backend:staging"
}
