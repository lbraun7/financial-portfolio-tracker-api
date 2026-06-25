# Financial Portfolio Tracker API

A REST API for managing investment portfolios, built with **FastAPI**, **PostgreSQL**, **Redis**, and **Docker**. It tracks transactions, derives positions, calculates realized/unrealized P&L, and keeps a full audit trail of portfolio activity.

> Built as a portfolio project to demonstrate senior-level backend engineering: async API design, financial domain modeling, transactional consistency, testing strategy, and production-minded infrastructure.

---

## Planned Capabilities

- **Portfolio management** — create and manage multiple portfolios per user
- **Multi-asset support** — stocks, ETFs, REITs, crypto, fixed income
- **Transaction ledger** — buy, sell, dividend, and split events with full audit trail
- **FIFO cost basis** — realized P&L calculated from tax lots when sell orders are recorded
- **Position tracking** — current holdings derived from transaction history and materialized for fast reads
- **P&L calculation** — realized and unrealized gains/losses per position and portfolio
- **Price integration** — async price fetching with caching layer
- **Authentication** — JWT-based auth with refresh token rotation
- **Idempotent writes** — safe transaction recording with idempotency keys
- **Rate limiting** — per-user request throttling via Redis
- **Async throughout** — fully async request handling with SQLAlchemy async sessions

---

## Tech Stack

| Layer            | Technology                           |
| ---------------- | ------------------------------------ |
| Framework        | FastAPI + Pydantic v2                |
| Database         | PostgreSQL 15 + SQLAlchemy 2 (async) |
| Migrations       | Alembic                              |
| Auth             | JWT (PyJWT) + bcrypt                 |
| Cache            | Redis                                |
| Testing          | Pytest + pytest-asyncio + HTTPX      |
| Tooling          | Ruff + mypy + pre-commit             |
| Containerization | Docker + Docker Compose              |
| CI               | GitHub Actions                       |

---

## Architecture

```
app/
├── api/
│   └── v1/
│       ├── auth.py                 # Auth endpoints
│       ├── portfolios.py           # Portfolio CRUD endpoints
│       ├── positions.py            # Position queries
│       └── transactions.py         # Transaction recording
├── core/
│   ├── config.py                   # Settings via pydantic-settings
│   ├── security.py                 # JWT, password hashing
│   ├── logging.py                  # Structured logging
│   └── exceptions.py               # Custom exception hierarchy
├── db/
│   ├── base.py                     # SQLAlchemy metadata
│   └── session.py                  # Async DB session factory
├── domain/
│   ├── enums.py                    # Asset and transaction types
│   ├── money.py                    # Decimal helpers and rounding policy
│   ├── pnl.py                      # P&L and FIFO calculation rules
│   └── validators.py               # Domain invariants
├── models/
│   ├── user.py
│   ├── portfolio.py
│   ├── asset.py
│   ├── transaction.py
│   ├── position.py
│   └── position_lot.py             # Open lots used for FIFO cost basis
├── schemas/                        # Pydantic request/response schemas
├── services/
│   ├── portfolio.py                # Portfolio use cases
│   ├── transaction.py              # Transaction engine and position updates
│   ├── pnl.py                      # Portfolio summary calculations
│   └── price.py                    # Async price fetching + Redis caching
├── repositories/                   # Data access layer
├── integrations/
│   └── prices/                     # External market data providers
└── main.py
```

The project follows a pragmatic Clean Architecture style: domain rules stay independent from FastAPI and SQLAlchemy, repositories isolate persistence, and services orchestrate use cases inside explicit database transactions.

---

## API Overview

### Authentication

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
```

### Portfolios

```
GET    /api/v1/portfolios              # List user portfolios
POST   /api/v1/portfolios              # Create portfolio
GET    /api/v1/portfolios/{id}         # Get portfolio + summary
DELETE /api/v1/portfolios/{id}         # Delete portfolio
```

### Positions & Transactions

```
GET    /api/v1/portfolios/{id}/positions               # All positions with current P&L
POST   /api/v1/portfolios/{id}/transactions            # Record buy/sell
GET    /api/v1/portfolios/{id}/transactions            # Transaction history
GET    /api/v1/portfolios/{id}/summary                 # Portfolio P&L summary
```

Transaction writes require an `Idempotency-Key` header (1–128 characters). Reusing the
same key and payload returns the original ledger entry; reusing it with a different payload
returns `409 Conflict`. BUY fees and taxes are incorporated into acquisition cost, while SELL
fees and taxes reduce realized P&L. Transactions for an asset must be recorded in chronological
order so the materialized FIFO lots remain deterministic.

### P&L Response Example

```json
{
  "portfolio_id": "uuid",
  "base_currency": "USD",
  "total_invested": "10000.00",
  "current_value": "11350.00",
  "unrealized_pnl": "1350.00",
  "unrealized_pnl_pct": "13.50",
  "realized_pnl": "420.00",
  "positions": [
    {
      "ticker": "AAPL",
      "quantity": "10.000000",
      "avg_cost": "150.00",
      "current_price": "178.50",
      "unrealized_pnl": "285.00",
      "unrealized_pnl_pct": "19.00"
    }
  ]
}
```

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Poetry

### Run with Docker

```bash
git clone https://github.com/lucas-braun/financial-portfolio-tracker-api
cd financial-portfolio-tracker-api

cp .env.example .env        # configure your environment variables

docker compose up --build
```

API available at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

### Run locally

```bash
python -m venv .venv
source .venv/bin/activate

poetry install

alembic upgrade head

uvicorn app.main:app --reload
```

---

## Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/portfolio_db
TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/portfolio_test_db
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
REDIS_URL=redis://localhost:6379
PRICE_API_KEY=your-price-api-key       # e.g. Alpha Vantage or Yahoo Finance
PRICE_API_BASE_URL=https://www.alphavantage.co/query
PRICE_REQUEST_TIMEOUT_SECONDS=10
PRICE_CACHE_TTL_SECONDS=300
```

---

## Running Tests

```bash
pytest                          # run all tests
pytest tests/unit               # unit tests only
pytest tests/integration        # integration tests (requires DB)
pytest --cov=app --cov-report=html  # coverage report
pre-commit run --all-files      # Ruff, formatting, mypy, and unit tests
```

Tests use a dedicated test database spun up via Docker. All async tests run with `pytest-asyncio`. Coverage target: **>85%** on domain and service layers.

---

## Key Design Decisions

**Why async SQLAlchemy?**
Portfolio operations involve multiple DB round-trips (fetch positions, fetch prices, calculate P&L). Async sessions allow these to be non-blocking, keeping throughput high under concurrent load.

**P&L calculation approach**
Unrealized P&L is calculated on-the-fly using the current price fetched from the price service and cached in Redis with a configurable TTL. Realized P&L is stored when sell transactions are recorded, using FIFO lots as the cost basis.

**Money precision**
Financial values are represented with `Decimal` in Python and `NUMERIC` in PostgreSQL. API responses serialize monetary values as strings to avoid floating-point ambiguity across clients.

**Transaction consistency**
Transaction writes run inside a single database transaction. The service validates portfolio ownership, applies domain invariants, updates open lots, updates materialized positions, and records realized P&L atomically.

**Repository pattern**
All database access goes through repositories, keeping SQLAlchemy out of the service layer. This makes unit testing services trivial — repositories are mocked, no DB required.

---

## Implementation Roadmap

- [ ] **Foundation** — project structure, `pyproject.toml`, FastAPI app, settings, Docker Compose with PostgreSQL and Redis, async DB sessions, Alembic, healthcheck
- [ ] **Domain & persistence** — users, portfolios, assets, transactions, positions, FIFO lots, migrations, decimal precision policy
- [ ] **Authentication** — register, login, password hashing, JWT access tokens, refresh token rotation
- [ ] **Portfolio management** — CRUD endpoints, repositories, service layer, ownership checks
- [x] **Transaction engine** — BUY/SELL flows, FIFO cost basis, realized P&L, idempotency keys, atomic position updates
- [x] **Pricing & summary** — price provider interface, Redis cache, unrealized P&L, portfolio summary endpoint
- [ ] **Quality** — unit tests, integration tests, coverage target, Ruff, mypy, pre-commit, GitHub Actions
- [ ] **Production extras** — rate limiting, structured logging, Docker image, deployment docs

### Future Enhancements

- [ ] WebSocket endpoint for live P&L updates
- [ ] Portfolio benchmarking vs IBOV, S&P 500, CDI
- [ ] CSV import for transaction history
- [ ] Dividend yield and income tracking
- [ ] AWS deployment with ECS + RDS + ElastiCache using Terraform
- [ ] Optional Kubernetes manifests for local or cloud deployment

---

## Author

**Lucas Braun** — Senior Backend Python Developer  
[linkedin.com/in/lucas-braun-20235395](https://linkedin.com/in/lucas-braun-20235395) · lucasbraun96@gmail.com
