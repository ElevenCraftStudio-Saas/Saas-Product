data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    # Standard AL2023 (NOT al2023-ami-minimal-*, which ships without the SSM agent).
    values = ["al2023-ami-2023.*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Optional SSH key (omitted entirely when ssh_public_key is empty → SSM-only).
resource "aws_key_pair" "app" {
  count      = var.ssh_public_key != "" ? 1 : 0
  key_name   = "${local.name}-key"
  public_key = var.ssh_public_key
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.app_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name
  key_name               = var.ssh_public_key != "" ? aws_key_pair.app[0].key_name : null

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    app_secret_name = local.app_secret_name
    region          = var.region
    s3_bucket       = aws_s3_bucket.photos.bucket
    log_group       = aws_cloudwatch_log_group.app.name
    app_domain      = var.app_domain != "" ? var.app_domain : ":80"
  })
  user_data_replace_on_change = false

  metadata_options {
    http_tokens   = "required" # IMDSv2 only
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_size = var.app_root_volume_gb
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "${local.name}-app" }

  depends_on = [aws_db_instance.main, aws_elasticache_cluster.redis, aws_secretsmanager_secret_version.app]
}

# Static address so DNS / firewall rules survive instance replacement.
resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
  tags     = { Name = "${local.name}-app-eip" }
}
