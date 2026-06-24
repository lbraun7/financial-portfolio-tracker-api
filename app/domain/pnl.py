"""P&L and FIFO cost basis calculation rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.money import (
    ZERO_DECIMAL,
    quantize_money,
    quantize_price,
    quantize_quantity,
)


@dataclass(frozen=True, slots=True)
class FifoLot:
    """An open quantity and its acquisition unit cost."""

    quantity: Decimal
    unit_cost: Decimal


@dataclass(frozen=True, slots=True)
class FifoConsumption:
    """The result of consuming open lots in FIFO order."""

    consumed_quantities: tuple[Decimal, ...]
    cost_basis: Decimal


@dataclass(frozen=True, slots=True)
class UnrealizedPnl:
    """Current valuation and unrealized return for an open position."""

    cost_basis: Decimal
    current_value: Decimal
    amount: Decimal
    percentage: Decimal


def calculate_buy_unit_cost(
    *,
    quantity: Decimal,
    unit_price: Decimal,
    fees: Decimal,
    taxes: Decimal,
) -> Decimal:
    """Return acquisition unit cost including buy-side expenses."""

    total_cost = quantity * unit_price + fees + taxes
    return quantize_price(total_cost / quantity)


def consume_fifo(*, lots: list[FifoLot], quantity: Decimal) -> FifoConsumption:
    """Consume a quantity from ordered lots and return its cost basis."""

    remaining = quantize_quantity(quantity)
    consumed: list[Decimal] = []
    cost_basis = ZERO_DECIMAL

    for lot in lots:
        consumed_quantity = min(remaining, lot.quantity)
        consumed.append(quantize_quantity(consumed_quantity))
        cost_basis += consumed_quantity * lot.unit_cost
        remaining = quantize_quantity(remaining - consumed_quantity)
        if remaining == ZERO_DECIMAL:
            break

    if remaining > ZERO_DECIMAL:
        raise ValueError("insufficient open quantity")

    return FifoConsumption(
        consumed_quantities=tuple(consumed),
        cost_basis=quantize_money(cost_basis),
    )


def calculate_realized_pnl(
    *,
    quantity: Decimal,
    unit_price: Decimal,
    fees: Decimal,
    taxes: Decimal,
    cost_basis: Decimal,
) -> Decimal:
    """Return net realized P&L for a sell transaction."""

    net_proceeds = quantity * unit_price - fees - taxes
    return quantize_money(net_proceeds - cost_basis)


def calculate_average_cost(*, lots: list[FifoLot]) -> Decimal:
    """Return the weighted average unit cost of all open lots."""

    total_quantity = sum((lot.quantity for lot in lots), start=ZERO_DECIMAL)
    if total_quantity == ZERO_DECIMAL:
        return ZERO_DECIMAL
    total_cost = sum(
        (lot.quantity * lot.unit_cost for lot in lots),
        start=ZERO_DECIMAL,
    )
    return quantize_price(total_cost / total_quantity)


def calculate_unrealized_pnl(
    *,
    quantity: Decimal,
    average_cost: Decimal,
    current_price: Decimal,
) -> UnrealizedPnl:
    """Return the on-the-fly valuation of an open position."""

    cost_basis = quantize_money(quantity * average_cost)
    current_value = quantize_money(quantity * current_price)
    amount = quantize_money(current_value - cost_basis)
    percentage = (
        ZERO_DECIMAL
        if cost_basis == ZERO_DECIMAL
        else quantize_money((amount / cost_basis) * Decimal("100"))
    )
    return UnrealizedPnl(
        cost_basis=cost_basis,
        current_value=current_value,
        amount=amount,
        percentage=percentage,
    )
