variable "aws_region" {
  description = "AWS region where resources will be created."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name prefix used by AWS resources."
  type        = string
  default     = "portfolio-api"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the application VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of availability zones to use."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2
    error_message = "At least two availability zones are required."
  }
}

variable "container_port" {
  description = "Port exposed by the API container."
  type        = number
  default     = 8000
}

variable "container_image_tag" {
  description = "Immutable image tag deployed from the project ECR repository."
  type        = string
  default     = "latest"
}

variable "service_desired_count" {
  description = "Number of ECS tasks. Keep at zero until the first image is pushed."
  type        = number
  default     = 0
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "certificate_arn" {
  description = "Optional ACM certificate ARN. When set, HTTP redirects to HTTPS."
  type        = string
  default     = null
}

variable "allowed_ingress_cidrs" {
  description = "CIDRs allowed to reach the public load balancer."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "database_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "portfolio_db"
}

variable "database_username" {
  description = "PostgreSQL master username."
  type        = string
  default     = "portfolio"
}

variable "database_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "database_allocated_storage" {
  description = "Initial RDS storage in GiB."
  type        = number
  default     = 20
}

variable "database_max_allocated_storage" {
  description = "Maximum RDS autoscaled storage in GiB."
  type        = number
  default     = 100
}

variable "database_multi_az" {
  description = "Whether RDS should use a Multi-AZ standby."
  type        = bool
  default     = false
}

variable "database_deletion_protection" {
  description = "Protect the production database from accidental deletion."
  type        = bool
  default     = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 30
}

variable "price_api_key" {
  description = "Market price provider API key stored in Secrets Manager."
  type        = string
  sensitive   = true
  default     = ""
}

variable "price_api_base_url" {
  description = "Market price provider URL."
  type        = string
  default     = "https://www.alphavantage.co/query"
}

variable "rate_limit_auth_requests" {
  description = "Authentication requests allowed per fixed window."
  type        = number
  default     = 10
}

variable "rate_limit_auth_window_seconds" {
  description = "Authentication rate-limit window in seconds."
  type        = number
  default     = 60
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
