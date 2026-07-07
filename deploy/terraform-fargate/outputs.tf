output "alb_dns_name" {
  description = "Point the api domain's CNAME here after ACM validates"
  value       = aws_lb.app.dns_name
}

output "acm_validation_records" {
  description = "Create these CNAMEs in your DNS provider to validate the cert"
  value = [
    for dvo in aws_acm_certificate.app.domain_validation_options : {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  ]
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "aurora_endpoint" {
  value = aws_rds_cluster.main.endpoint
}

output "redis_url" {
  value     = local.redis_url
  sensitive = true
}

output "app_secret_name" {
  value = local.app_secret_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}
