# Deployment Guide

The API is designed to run as a stateless container with PostgreSQL and Redis managed
separately. A small production deployment can use one API service, one migration task,
a managed PostgreSQL database, and a managed Redis instance.

## Build and run the image

```bash
docker build -f infra/docker/Dockerfile -t portfolio-api:latest .

docker run --rm -p 8000:8000 \
  --env-file .env.production \
  portfolio-api:latest
```

Run database migrations as a one-off release task before starting a new application version:

```bash
docker run --rm --env-file .env.production \
  portfolio-api:latest poetry run alembic upgrade head
```

Do not run migrations independently in every replica. Concurrent migration attempts can make
deployments unreliable.

## Required production configuration

```env
ENVIRONMENT=production
DEBUG=false

DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@DB_HOST:5432/portfolio_db
REDIS_URL=redis://REDIS_HOST:6379/0

SECRET_KEY=replace-with-a-random-secret-of-at-least-32-bytes
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

RATE_LIMIT_ENABLED=true
RATE_LIMIT_AUTH_REQUESTS=10
RATE_LIMIT_AUTH_WINDOW_SECONDS=60

LOG_LEVEL=INFO
LOG_JSON=true

PRICE_API_KEY=replace-with-provider-key
PRICE_API_BASE_URL=https://www.alphavantage.co/query
PRICE_REQUEST_TIMEOUT_SECONDS=10
PRICE_CACHE_TTL_SECONDS=300
```

Store secrets in the platform secret manager rather than in an image, repository, or committed
environment file. PostgreSQL and Redis connections should use private networking and encryption
when supported by the provider.

## Health checks

- `GET /health` is a liveness check. It only verifies that the HTTP process is responsive.
- `GET /ready` is a readiness check. It verifies PostgreSQL and Redis connectivity.

Configure the load balancer to use `/health`. Use `/ready` to decide whether a replica should
receive traffic during startup or dependency outages.

Every response includes an `X-Request-ID`. A caller-provided request ID is preserved, otherwise
the API creates one. Production logs are JSON when `LOG_JSON=true`, making them suitable for
CloudWatch, Datadog, Grafana Loki, or another centralized log system.

## Reverse proxy and scaling

Terminate TLS at the cloud load balancer or reverse proxy and forward traffic to port `8000`.
Scale horizontally by running additional API containers. Application state remains in PostgreSQL
and Redis.

The rate limiter currently keys authentication limits by client IP and endpoint. Ensure the
runtime receives the real client address from a trusted proxy configuration. Never trust forwarded
headers from arbitrary internet clients without a trusted proxy boundary.

## AWS deployment

The repository includes a deployable Terraform configuration in
[`infra/terraform`](../infra/terraform/README.md). It provisions:

- ECS Fargate service for the API
- Application Load Balancer with TLS
- ECR image repository
- RDS PostgreSQL
- ElastiCache Redis
- CloudWatch Logs
- Secrets Manager
- An ECS one-off task for Alembic migrations

The first apply intentionally creates the ECS service with zero tasks. The documented release
flow then pushes an immutable image, runs migrations, and enables application replicas. Kubernetes
remains unnecessary for this application's current operational footprint.

## Release checklist

1. Run Ruff, mypy, and the full test suite.
2. Build the container image and scan it for known vulnerabilities.
3. Push the image with an immutable version or commit tag.
4. Back up the database before destructive migrations.
5. Run `alembic upgrade head` as the release task.
6. Deploy the API and wait for readiness checks.
7. Verify authentication, a representative portfolio read, logs, and request IDs.
8. Roll back the application image if checks fail; handle database rollback according to the
   migration's compatibility plan.
