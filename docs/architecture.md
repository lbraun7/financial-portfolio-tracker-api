# Architecture

This document explains how the API is organized, how requests move through the
system, and where the main consistency boundaries live.

## System Overview

The application is a stateless FastAPI service backed by PostgreSQL and Redis.
PostgreSQL stores users, portfolios, assets, transactions, positions, and FIFO
lots. Redis is used for temporary data such as market price cache entries and
optional authentication rate-limit counters.

```text
Client
  |
  v
FastAPI routes
  |
  v
Services
  |
  +--> Domain rules
  |
  +--> Repositories
         |
         v
      PostgreSQL

Price summary flow:

Services -> PriceService -> Redis cache -> Price provider
```

The API process does not keep portfolio state in memory. Application state lives
in PostgreSQL, while Redis remains disposable cache/supporting infrastructure.

## Application Layers

### API Layer

`app/api/v1` contains FastAPI routers and HTTP concerns:

- request parsing and response models
- dependency injection
- authentication dependencies
- HTTP error mapping
- idempotency header validation

The route handlers stay thin. They convert transport concerns into service calls
and translate domain/service exceptions into HTTP responses.

### Service Layer

`app/services` contains use cases:

- `AuthService` handles registration, login, refresh tokens, and current-user lookup.
- `PortfolioService` handles portfolio ownership and CRUD operations.
- `TransactionService` records buy/sell transactions and updates positions/lots.
- `PortfolioSummaryService` builds current valuation and P&L summaries.
- `PriceService` fetches and caches market prices.

Services are the main orchestration layer. They coordinate repositories, domain
functions, external integrations, and transaction boundaries.

### Domain Layer

`app/domain` contains rules that do not depend on FastAPI or SQLAlchemy:

- asset and transaction enums
- money, price, and quantity precision helpers
- FIFO lot consumption
- realized and unrealized P&L calculations
- average cost calculation

Keeping these functions isolated makes the financial behavior easier to test and
reason about.

### Repository Layer

`app/repositories` owns persistence operations. Repositories hide SQLAlchemy
queries from services and provide explicit methods such as:

- fetch a portfolio for a user
- lock a portfolio or position for update
- list open lots
- find transactions by idempotency key
- list positions for a portfolio

### Model Layer

`app/models` contains SQLAlchemy ORM models. Important tables include:

- `users`
- `portfolios`
- `assets`
- `transactions`
- `positions`
- `position_lots`

`transactions` are immutable ledger entries. `positions` and `position_lots` are
derived/materialized state used for efficient reads and FIFO calculations.

## Transaction Write Flow

Recording a transaction is the most important write path in the system.

```text
POST /api/v1/portfolios/{portfolio_id}/transactions
  |
  v
Validate bearer token and Idempotency-Key
  |
  v
Lock portfolio for current user
  |
  v
Check idempotency key
  |
  v
Validate asset, currency, and trade_date ordering
  |
  v
Lock or create position
  |
  +--> BUY: create transaction, create lot, update quantity/average cost
  |
  +--> SELL: consume lots FIFO, calculate realized P&L, update position
  |
  v
Commit database transaction
```

The service uses row-level locking for the portfolio and position involved in
the write. That keeps concurrent writes for the same portfolio/asset from
silently corrupting materialized position state.

## Idempotency

The transaction creation endpoint requires an `Idempotency-Key` header. The
database enforces uniqueness per portfolio through the transaction ledger.

If a request retries with the same key and identical payload, the API returns
the existing transaction. If the same key is reused with a different payload,
the API returns `409 Conflict`.

This protects clients and background workers from accidentally duplicating
financial events during retry scenarios.

## Position And Lot Model

The API keeps three related concepts:

- `transactions`: immutable history of user activity.
- `positions`: current materialized quantity, average cost, and realized P&L per asset.
- `position_lots`: open quantities created by buys and consumed by sells.

The ledger is the audit trail. Positions and lots are operational projections
that make common reads and FIFO calculations fast.

## Portfolio Summary Flow

Portfolio summaries are computed on demand:

1. Verify that the portfolio belongs to the current user.
2. Load all positions for the portfolio.
3. Keep only open positions for market valuation.
4. Reject summaries when an open position currency differs from the portfolio base currency.
5. Fetch current market prices through `PriceService`.
6. Calculate invested value, current value, unrealized P&L, and realized P&L.

`PriceService` first checks Redis using a normalized symbol cache key. Cache
failures are treated as misses, so temporary Redis issues do not break price
fetching. Provider failures can still surface as `503 Service Unavailable` from
the summary endpoint.

## Consistency Boundaries

### Database Transactions

Portfolio writes that affect ledger and position state run inside one database
transaction. A failure rolls back all related changes.

### Row Locks

The transaction engine locks the portfolio and position rows that are being
modified. This keeps concurrent writes serialized around the affected state.

### Immutable Ledger

Transactions are append-only from the business perspective. Adjustments should
be represented as new ledger entries instead of rewriting historical entries.

### Derived State

Positions and lots are derived from transactions, but are stored because they
are needed for efficient reads and deterministic FIFO processing.

## Operational Shape

The service is designed to run as a stateless container:

- Scale API replicas horizontally.
- Run migrations as a one-off release task.
- Store state in managed PostgreSQL and Redis.
- Use `/health` for liveness and `/ready` for dependency readiness.
- Emit structured logs with request IDs.

See [`deployment.md`](deployment.md) for deployment-specific details.

## Current Constraints

- The transaction engine currently processes only `buy` and `sell`.
- Dividend and split transaction types exist in the enum but are not implemented by the engine.
- Portfolio summaries require open positions to use the portfolio base currency.
- Market valuation depends on the configured price provider.
