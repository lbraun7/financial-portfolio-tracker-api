# Financial Portfolio Tracker API

REST API for tracking investment portfolios, with JWT authentication, idempotent
transaction recording, average cost/FIFO calculations, and realized/unrealized
P&L views.

The project was built as a backend portfolio API focused on financial domain
modeling, transactional consistency, automated testing, and a container-ready
deployment foundation.

## Engineering Highlights

- Idempotent transaction writes to make client retries safe.
- FIFO cost basis with realized P&L persisted on sell transactions.
- Decimal-based money, price, and quantity handling.
- Async FastAPI and SQLAlchemy stack with explicit transaction boundaries.
- Redis-backed price caching for portfolio valuation.
- JWT authentication with refresh token flow and owner-scoped resources.
- Unit and integration test coverage focused on domain and service behavior.
- Docker and Terraform assets for local development and cloud deployment.

## What The API Does

- Registers and authenticates users with access and refresh tokens.
- Manages user-owned portfolios with owner isolation.
- Records buy and sell transactions with idempotency keys.
- Validates currency, chronological order, and sufficient position quantity.
- Materializes positions and open lots for efficient reads.
- Calculates realized P&L using FIFO.
- Lists current positions by portfolio.
- Builds portfolio summaries with market prices from Alpha Vantage and Redis cache.
- Exposes application, database, and Redis health checks.

## Stack

| Layer | Technology |
| --- | --- |
| API | FastAPI, Pydantic v2, Uvicorn |
| Database | PostgreSQL 16, SQLAlchemy 2 async |
| Migrations | Alembic |
| Cache | Redis |
| Auth | PyJWT, bcrypt |
| Tests | Pytest, pytest-asyncio, HTTPX, pytest-cov |
| Quality | Ruff, mypy, pre-commit |
| Infrastructure | Docker Compose, Dockerfile, Terraform for AWS |

## Why This Stack

**FastAPI and Pydantic**
provide a compact async API layer with strong request/response validation,
automatic OpenAPI docs, and type-friendly development.

**PostgreSQL and SQLAlchemy async**
fit the transactional core of the project: portfolio writes must atomically
update the ledger, positions, and FIFO lots without sacrificing clean Python
domain modeling.

**Redis**
is used where the data is naturally temporary: cached market prices and optional
rate-limit counters. The source of truth stays in PostgreSQL.

**Alembic**
keeps schema evolution explicit and reviewable, which matters for financial
data where migrations need to be predictable.

**Docker Compose**
makes the full local environment reproducible: API, PostgreSQL, test database,
and Redis can be started with one command.

**Ruff, mypy, and pytest**
keep the codebase honest across style, typing, and behavior. The coverage gate
focuses on the domain and service layers because that is where most financial
risk lives.

## Architecture

```text
app/
├── api/v1/              # HTTP routes and FastAPI dependencies
├── core/                # Settings, security, logging, errors, rate limiting
├── db/                  # Async SQLAlchemy engine/session setup
├── domain/              # Pure money, enum, and P&L rules
├── integrations/        # External providers, such as market prices
├── models/              # SQLAlchemy models
├── repositories/        # Data access layer
├── schemas/             # Pydantic contracts
├── services/            # Use cases and transactional orchestration
└── main.py              # Application factory
```

The boundaries are intentional: domain rules stay out of the routes, services
coordinate use cases, and repositories own persistence. Critical writes run
inside database transactions so the ledger, positions, and lots stay consistent.

## Endpoints

All versioned endpoints use the `/api/v1` prefix.

### Health

```text
GET /health
GET /ready
```

### Authentication

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
GET  /api/v1/auth/me
```

### Portfolios

```text
GET    /api/v1/portfolios
POST   /api/v1/portfolios
GET    /api/v1/portfolios/{portfolio_id}
PATCH  /api/v1/portfolios/{portfolio_id}
DELETE /api/v1/portfolios/{portfolio_id}
GET    /api/v1/portfolios/{portfolio_id}/summary
```

### Transactions And Positions

```text
GET  /api/v1/portfolios/{portfolio_id}/transactions
POST /api/v1/portfolios/{portfolio_id}/transactions
GET  /api/v1/portfolios/{portfolio_id}/positions
```

The transaction creation endpoint requires an `Idempotency-Key` header with 1 to
128 characters. Reusing the same key with the same payload returns the existing
ledger entry; reusing it with a different payload returns `409 Conflict`.

The schema currently defines `buy`, `sell`, `dividend`, and `split`, but the
transaction engine only processes `buy` and `sell`.

## Transaction Example

```http
POST /api/v1/portfolios/{portfolio_id}/transactions
Authorization: Bearer <access_token>
Idempotency-Key: buy-aapl-2026-01-15-001
Content-Type: application/json
```

```json
{
  "asset_id": "00000000-0000-0000-0000-000000000000",
  "transaction_type": "buy",
  "quantity": "10",
  "unit_price": "150.25",
  "fees": "1.50",
  "taxes": "0",
  "currency": "USD",
  "trade_date": "2026-01-15T14:30:00Z",
  "settlement_date": "2026-01-17",
  "notes": "Initial AAPL position"
}
```

Buy transactions incorporate fees and taxes into acquisition cost. Sell
transactions consume open lots using FIFO and reduce realized P&L by fees and
taxes. The API rejects sells with insufficient quantity and transactions that
pre-date the latest transaction for the same asset.

## Portfolio Summary

```json
{
  "portfolio_id": "00000000-0000-0000-0000-000000000000",
  "base_currency": "USD",
  "total_invested": "1503.50",
  "current_value": "1785.00",
  "unrealized_pnl": "281.50",
  "unrealized_pnl_pct": "18.72",
  "realized_pnl": "0.00",
  "positions": [
    {
      "asset_id": "00000000-0000-0000-0000-000000000000",
      "ticker": "AAPL",
      "currency": "USD",
      "quantity": "10.000000",
      "avg_cost": "150.350000",
      "current_price": "178.500000",
      "invested": "1503.50",
      "current_value": "1785.00",
      "unrealized_pnl": "281.50",
      "unrealized_pnl_pct": "18.72",
      "realized_pnl": "0.00"
    }
  ]
}
```

The summary endpoint fetches prices from the configured provider and caches them
in Redis. If the provider is not configured or is unavailable, the endpoint may
return `503 Service Unavailable`.

## Run With Docker

Prerequisites:

- Docker and Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

The API is available at:

- `http://localhost:8000`
- `http://localhost:8000/docs`
- `http://localhost:8000/health`
- `http://localhost:8000/ready`

The `api` service runs `alembic upgrade head` before starting Uvicorn.

## Run Locally

Prerequisites:

- Python 3.12
- Poetry
- PostgreSQL
- Redis

```bash
cp .env.example .env
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

You can also use the project script:

```bash
poetry run api
```

## Environment Variables

The main settings are listed in `.env.example`.

```env
APP_NAME="Financial Portfolio Tracker API"
ENVIRONMENT=local
DEBUG=true
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://portfolio:portfolio@localhost:5432/portfolio_db
TEST_DATABASE_URL=postgresql+asyncpg://portfolio:portfolio@localhost:5433/portfolio_test_db
DATABASE_ECHO=false

REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_ENABLED=false
RATE_LIMIT_AUTH_REQUESTS=10
RATE_LIMIT_AUTH_WINDOW_SECONDS=60

SECRET_KEY=change-me-before-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

PRICE_API_KEY=
PRICE_API_BASE_URL=https://www.alphavantage.co/query
PRICE_REQUEST_TIMEOUT_SECONDS=10
PRICE_CACHE_TTL_SECONDS=300
```

For real usage, set a strong `SECRET_KEY` and configure `PRICE_API_KEY` for the
price provider.

## Tests And Quality

```bash
poetry run pytest
poetry run pytest tests/unit
poetry run pytest tests/integration
poetry run ruff check app tests
poetry run mypy app tests
poetry run pre-commit run --all-files
```

Integration tests use PostgreSQL. In `docker-compose.yml`, the test database is
available at `localhost:5433`, with username and password `portfolio` and
database name `portfolio_test_db`.

`pyproject.toml` requires at least 85% coverage for `app.domain` and
`app.services`.

## Migrations

```bash
poetry run alembic upgrade head
poetry run alembic downgrade -1
poetry run alembic revision --autogenerate -m "describe change"
```

Migration revisions live in `alembic/versions`.

## Infrastructure And Deployment

The repository includes:

- `infra/docker/Dockerfile` for the API image.
- `docker-compose.yml` for the API, PostgreSQL, test database, and Redis.
- `infra/terraform` with an AWS infrastructure foundation.
- `docs/architecture.md` with application layers, request flows, and consistency boundaries.
- `docs/domain.md` with FIFO, money precision, transaction, and P&L rules.
- `docs/deployment.md` with build, migration, health check, and deployment notes.

## Domain Decisions

**Decimal instead of float**
Financial values use `Decimal` in Python and numeric types in the database. This
avoids precision loss for money, prices, and quantities.

**Ledger as the source of truth**
Transactions are immutable history records. Positions and lots are derived and
materialized for efficient reads and P&L calculation.

**FIFO for sells**
When selling, the API consumes the oldest lots first. Realized P&L is saved on
the sell transaction itself.

**Idempotent writes**
Creating transactions is a sensitive operation. The idempotency key protects
against duplicate client or queue retries.

**Async end to end**
FastAPI, SQLAlchemy, Redis, and price integrations use async APIs to preserve
throughput under concurrent load.
