# ALB + ACM. SSE works through the ALB; idle timeout is raised past the 60s
# stream cap so processing streams aren't cut mid-flight.

resource "aws_lb" "app" {
  name               = "${local.name}-fg-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 120
  tags               = { Name = "${local.name}-fg-alb" }
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-fg-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip" # Fargate awsvpc mode

  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30
  tags                 = { Name = "${local.name}-fg-api-tg" }
}

resource "aws_acm_certificate" "app" {
  domain_name       = var.app_domain
  validation_method = "DNS"
  tags              = { Name = "${local.name}-fg-cert" }

  lifecycle {
    create_before_destroy = true
  }
}

# DNS is managed outside AWS (Hostinger et al.) — create the CNAMEs from the
# `acm_validation_records` output by hand, then validation completes on its own.

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.app.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
