data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = "wedfind-${var.environment}"

  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  # /20 public + /20 private per AZ, carved from the VPC CIDR.
  public_subnets  = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnets = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 4, i + 8)]

  # Single Secrets Manager secret holds the app's sensitive config as JSON.
  app_secret_name = "${local.name}/app"

  enable_dns = var.app_domain != "" && var.route53_zone_id != ""
}
