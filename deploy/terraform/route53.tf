# Optional DNS — only created when app_domain + route53_zone_id are set.
# TLS itself is terminated on the host (Caddy/nginx in the staging compose) or
# you can front the instance with an ALB+ACM later. This just points the name
# at the EIP.
resource "aws_route53_record" "app" {
  count   = local.enable_dns ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.app_domain
  type    = "A"
  ttl     = 300
  records = [aws_eip.app.public_ip]
}
