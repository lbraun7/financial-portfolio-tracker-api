output "load_balancer_url" {
  description = "Public URL for the API load balancer."
  value       = var.certificate_arn == null ? "http://${aws_lb.application.dns_name}" : "https://${aws_lb.application.dns_name}"
}

output "aws_region" {
  description = "AWS region used by this deployment."
  value       = var.aws_region
}

output "ecr_repository_url" {
  description = "Repository URL used to push application images."
  value       = aws_ecr_repository.application.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster used by the application and migration tasks."
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.application.name
}

output "ecs_task_definition_arn" {
  description = "Task definition used by the API service."
  value       = aws_ecs_task_definition.application.arn
}

output "migration_task_definition_arn" {
  description = "One-off ECS task definition that runs Alembic migrations."
  value       = aws_ecs_task_definition.migration.arn
}

output "private_subnet_ids" {
  description = "Private subnets used for ECS migration tasks."
  value       = aws_subnet.private[*].id
}

output "application_security_group_id" {
  description = "Security group used by ECS tasks."
  value       = aws_security_group.application.id
}

output "application_secret_arn" {
  description = "Secrets Manager ARN consumed by ECS."
  value       = aws_secretsmanager_secret.application.arn
}
