resource "random_password" "database" {
  length  = 32
  special = false
}

resource "random_password" "application_secret" {
  length  = 64
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = local.name
  }
}

resource "aws_db_instance" "main" {
  identifier = local.name

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.database_instance_class

  db_name  = var.database_name
  username = var.database_username
  password = random_password.database.result
  port     = 5432

  allocated_storage     = var.database_allocated_storage
  max_allocated_storage = var.database_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = var.database_multi_az
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]

  backup_retention_period   = 7
  deletion_protection       = var.database_deletion_protection
  skip_final_snapshot       = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${local.name}-final" : null

  auto_minor_version_upgrade = true
  apply_immediately          = false
  copy_tags_to_snapshot      = true

  tags = {
    Name = local.name
  }
}

resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = local.name
  description          = "Redis cache and rate limiting for ${local.name}"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = var.redis_node_type
  port           = 6379

  num_cache_clusters         = 1
  automatic_failover_enabled = false
  multi_az_enabled           = false

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  snapshot_retention_limit = 1
  apply_immediately        = false

  tags = {
    Name = local.name
  }
}

resource "aws_secretsmanager_secret" "application" {
  name                    = "${local.name}/application"
  recovery_window_in_days = var.environment == "production" ? 7 : 0

  tags = {
    Name = "${local.name}-application"
  }
}

resource "aws_secretsmanager_secret_version" "application" {
  secret_id = aws_secretsmanager_secret.application.id
  secret_string = jsonencode({
    database_url  = "postgresql+asyncpg://${var.database_username}:${random_password.database.result}@${aws_db_instance.main.address}:5432/${var.database_name}"
    secret_key    = random_password.application_secret.result
    price_api_key = var.price_api_key
  })
}
