data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = "${var.project_name}-${var.environment}"

  availability_zones = slice(
    data.aws_availability_zones.available.names,
    0,
    var.availability_zone_count
  )

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.tags
  )

  application_environment = [
    {
      name  = "APP_NAME"
      value = "Financial Portfolio Tracker API"
    },
    {
      name  = "ENVIRONMENT"
      value = var.environment
    },
    {
      name  = "DEBUG"
      value = "false"
    },
    {
      name  = "REDIS_URL"
      value = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
    },
    {
      name  = "RATE_LIMIT_ENABLED"
      value = "true"
    },
    {
      name  = "RATE_LIMIT_AUTH_REQUESTS"
      value = tostring(var.rate_limit_auth_requests)
    },
    {
      name  = "RATE_LIMIT_AUTH_WINDOW_SECONDS"
      value = tostring(var.rate_limit_auth_window_seconds)
    },
    {
      name  = "LOG_LEVEL"
      value = "INFO"
    },
    {
      name  = "LOG_JSON"
      value = "true"
    },
    {
      name  = "PRICE_API_BASE_URL"
      value = var.price_api_base_url
    }
  ]

  application_secrets = [
    {
      name      = "DATABASE_URL"
      valueFrom = "${aws_secretsmanager_secret.application.arn}:database_url::"
    },
    {
      name      = "SECRET_KEY"
      valueFrom = "${aws_secretsmanager_secret.application.arn}:secret_key::"
    },
    {
      name      = "PRICE_API_KEY"
      valueFrom = "${aws_secretsmanager_secret.application.arn}:price_api_key::"
    }
  ]
}
