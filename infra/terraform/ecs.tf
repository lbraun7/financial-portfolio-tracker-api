resource "aws_cloudwatch_log_group" "application" {
  name              = "/ecs/${local.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "application" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.task_cpu)
  memory                   = tostring(var.task_memory)
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.application.repository_url}:${var.container_image_tag}"
      essential = true
      command = [
        "poetry",
        "run",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        tostring(var.container_port),
        "--proxy-headers",
        "--forwarded-allow-ips",
        "*"
      ]

      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = local.application_environment
      secrets     = local.application_secrets

      healthCheck = {
        command = [
          "CMD-SHELL",
          "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${var.container_port}/health', timeout=3)\" || exit 1"
        ]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 15
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.application.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])

  depends_on = [
    aws_iam_role_policy_attachment.ecs_execution,
    aws_iam_role_policy.ecs_secrets,
    aws_secretsmanager_secret_version.application
  ]
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${local.name}-migration"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.task_cpu)
  memory                   = tostring(var.task_memory)
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "migration"
      image     = "${aws_ecr_repository.application.repository_url}:${var.container_image_tag}"
      essential = true
      command = [
        "poetry",
        "run",
        "alembic",
        "upgrade",
        "head"
      ]

      environment = local.application_environment
      secrets     = local.application_secrets

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.application.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "migration"
        }
      }
    }
  ])

  depends_on = [
    aws_iam_role_policy_attachment.ecs_execution,
    aws_iam_role_policy.ecs_secrets,
    aws_secretsmanager_secret_version.application
  ]
}

resource "aws_ecs_service" "application" {
  name            = local.name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.application.arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = var.service_desired_count == 1 ? 0 : 50
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 60
  enable_execute_command             = false

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.application.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.application.arn
    container_name   = "api"
    container_port   = var.container_port
  }

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener.https
  ]
}
