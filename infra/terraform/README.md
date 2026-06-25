# AWS Terraform

This configuration provisions a small production-oriented AWS environment for the API:

- VPC across two availability zones
- Public subnets for an Application Load Balancer
- Private subnets and one NAT Gateway for ECS, RDS, and ElastiCache
- ECR repository with immutable tags and image scanning
- ECS Fargate service and reusable task definition for Alembic migrations
- RDS PostgreSQL with encryption, backups, and deletion protection
- ElastiCache Redis with encryption in transit and at rest
- Secrets Manager for the database URL, JWT secret, and price provider key
- CloudWatch Logs and ECS Container Insights

The defaults favor a portfolio/demo deployment rather than high availability. In particular,
RDS Multi-AZ is disabled and Redis uses one node. Enable stronger redundancy before serving a
production workload with availability requirements.

## Prerequisites

- Terraform 1.7+
- AWS CLI authenticated to the target account
- Docker
- Permissions to create the resources listed above

## Remote state

Production state should live in an encrypted S3 backend with locking. Create the state bucket and
lock table separately, then initialize using the example:

```bash
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
```

Backend infrastructure is intentionally not created by this configuration because Terraform
cannot reliably use a backend that it creates in the same initialization.

The generated database password and application secret are stored in Terraform state. Restrict
access to the state bucket, enable versioning, encryption, public-access blocking, and audit logs.

## First deployment

Copy and review the variables:

```bash
cp terraform.tfvars.example terraform.tfvars
export TF_VAR_price_api_key="provider-key"

terraform fmt -check
terraform validate
terraform plan
terraform apply
```

The service starts with zero tasks so the first apply succeeds before an image exists in ECR.

Authenticate Docker and push an immutable image:

```bash
AWS_REGION="$(terraform output -raw aws_region 2>/dev/null || echo us-east-1)"
ECR_REPOSITORY="$(terraform output -raw ecr_repository_url)"
ECR_REGISTRY="${ECR_REPOSITORY%/*}"
IMAGE_TAG="$(git rev-parse --short HEAD)"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker build --platform linux/amd64 \
  -f ../docker/Dockerfile \
  -t "$ECR_REPOSITORY:$IMAGE_TAG" \
  ../..

docker push "$ECR_REPOSITORY:$IMAGE_TAG"
```

Set `container_image_tag` to the pushed tag in `terraform.tfvars`, but keep
`service_desired_count = 0`. Apply once to register the API and migration task definitions:

```bash
terraform apply
```

## Run database migrations

Run the dedicated migration task definition. It uses the same image and secrets as the API but
does not have the API's HTTP health check:

```bash
CLUSTER="$(terraform output -raw ecs_cluster_name)"
TASK_DEFINITION="$(terraform output -raw migration_task_definition_arn)"
SUBNETS="$(terraform output -json private_subnet_ids | jq -r 'join(",")')"
SECURITY_GROUP="$(terraform output -raw application_security_group_id)"

aws ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEFINITION" \
  --launch-type FARGATE \
  --network-configuration \
    "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}"
```

Wait for the migration task to finish successfully before starting application replicas. Its logs
appear in the same CloudWatch log group as the API.

Finally set `service_desired_count = 1` or higher and apply:

```bash
terraform apply
terraform output -raw load_balancer_url
```

## HTTPS

Set `certificate_arn` to an ACM certificate in the same region. Terraform will create an HTTPS
listener and redirect HTTP to HTTPS. DNS records and certificate validation are deliberately left
outside this configuration because hosted zones and domain ownership vary by environment.

The ECS task trusts proxy headers because its security group only accepts application traffic from
the ALB security group. This allows request logging and IP-based rate limiting to see the original
client address without exposing the container directly to untrusted callers.

## Cost notes

The NAT Gateway, Application Load Balancer, RDS, and ElastiCache incur charges even when traffic
is low. Destroy non-production environments when unused. Production deletion protection must be
disabled explicitly before RDS or the load balancer can be destroyed.

## Production hardening options

- Enable RDS Multi-AZ and use at least two Redis nodes with automatic failover.
- Add AWS WAF to the load balancer.
- Add VPC endpoints for ECR, CloudWatch Logs, Secrets Manager, and S3 to reduce NAT dependence.
- Add Route 53 records and ACM certificate validation.
- Add ECS autoscaling based on CPU, memory, or request count.
- Send alerts for unhealthy targets, task failures, database capacity, and Redis memory.
