# Financial Domain Model

This document explains the financial rules implemented by the API: money
precision, transaction semantics, FIFO cost basis, and P&L calculation.

## Core Concepts

### Portfolio

A portfolio belongs to one user and has a base currency. Portfolio reads and
writes are scoped to the authenticated owner.

### Asset

An asset represents an instrument such as a stock, ETF, REIT, crypto asset, or
fixed-income asset. Each asset has a symbol and currency.

### Transaction

A transaction is an immutable ledger entry. The current engine processes:

- `buy`
- `sell`

The enum also defines `dividend` and `split`, but those flows are not currently
implemented by the transaction engine.

### Position

A position is the current materialized state for one asset in one portfolio. It
stores current quantity, average cost, and accumulated realized P&L.

### Position Lot

A lot is created by a buy transaction and represents an open quantity with an
acquisition unit cost. Sell transactions consume open lots using FIFO.

## Decimal Policy

The API avoids floats for financial values. Domain helpers accept integer,
string, or `Decimal` inputs and reject floats.

Current precision policy:

| Value type | Precision | Scale | Quantum |
| --- | ---: | ---: | --- |
| Money | 19 | 4 | `0.0001` |
| Price | 28 | 10 | `0.0000000001` |
| Quantity | 28 | 10 | `0.0000000001` |

Values are rounded with `ROUND_HALF_UP`.

Money is used for totals and P&L. Price is used for unit prices and unit costs.
Quantity is used for asset amounts, including fractional quantities.

## Buy Transactions

A buy increases the position quantity and creates a new FIFO lot.

Input values:

- `quantity`
- `unit_price`
- `fees`
- `taxes`
- `currency`
- `trade_date`

The buy-side unit cost includes fees and taxes:

```text
total_cost = quantity * unit_price + fees + taxes
unit_cost = total_cost / quantity
```

After a buy:

1. A transaction ledger entry is created.
2. A position lot is created with the calculated unit cost.
3. Position quantity increases.
4. Position average cost is recalculated from all open lots.

## Sell Transactions

A sell decreases the position quantity and consumes open lots in FIFO order.

Before recording a sell, the service verifies:

- the portfolio belongs to the current user
- the asset exists
- the transaction currency matches the asset currency
- the position has enough quantity
- the trade date is not earlier than the latest transaction for that asset

Sell-side fees and taxes reduce net proceeds:

```text
net_proceeds = quantity * unit_price - fees - taxes
realized_pnl = net_proceeds - fifo_cost_basis
```

After a sell:

1. Open lots are consumed from oldest to newest.
2. The realized P&L is calculated and stored on the sell transaction.
3. Position quantity decreases.
4. Position accumulated realized P&L increases by the sell P&L.
5. Position average cost is recalculated from remaining open lots.

## FIFO Cost Basis

FIFO means "first in, first out". The oldest open lots are consumed first when a
sell transaction is recorded.

Example:

```text
Buy 10 @ 100.00
Buy 5  @ 120.00
Sell 12 @ 150.00
```

FIFO consumption:

```text
10 units from first lot  -> 10 * 100.00 = 1000.00
2 units from second lot  ->  2 * 120.00 =  240.00
cost_basis                             = 1240.00
```

If there are no fees or taxes:

```text
net_proceeds = 12 * 150.00 = 1800.00
realized_pnl = 1800.00 - 1240.00 = 560.00
```

The second lot remains open with 3 units at 120.00 unit cost.

## Average Cost

Average cost is calculated from open lots, not from historical transactions that
have already been fully consumed.

```text
average_cost = total_open_lot_cost / total_open_quantity
```

If there is no open quantity, average cost becomes zero.

This value is useful for position reads and unrealized P&L. Realized P&L still
uses FIFO lot consumption, not average cost.

## Unrealized P&L

Unrealized P&L is calculated on demand for open positions using the current
market price:

```text
cost_basis = quantity * average_cost
current_value = quantity * current_price
unrealized_pnl = current_value - cost_basis
unrealized_pnl_pct = unrealized_pnl / cost_basis * 100
```

When cost basis is zero, the percentage is reported as zero to avoid division by
zero.

## Realized P&L

Realized P&L is calculated at sell time and stored on the sell transaction. The
position also keeps accumulated realized P&L for the asset in that portfolio.

This makes historical realized results stable even if market prices change later.

## Idempotency Rules

Transaction creation requires an `Idempotency-Key`.

The same portfolio cannot have two transaction rows with the same idempotency
key. When a duplicate key is received:

- same payload: return the existing transaction
- different payload: return `409 Conflict`

This is important because transaction writes are financial events, and duplicate
retries would otherwise change portfolio state.

## Chronological Ordering

Transactions for the same asset in a portfolio must be recorded in chronological
order. A new transaction whose `trade_date` is earlier than the latest existing
transaction for that asset is rejected.

This keeps FIFO lots and materialized position state deterministic.

## Currency Rules

Transaction currency must match asset currency. Portfolio summary currently
requires open position currencies to match the portfolio base currency.

The API does not currently perform FX conversion.

## Current Limitations

- Only buy and sell transactions are processed.
- Dividends and splits are modeled as enum values but not implemented.
- No FX conversion is performed.
- Out-of-order corrections are not supported directly; they require a future
  adjustment/rebuild workflow.
- Corporate actions are outside the current engine.
