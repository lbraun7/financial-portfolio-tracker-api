"""FIFO and realized P&L domain tests."""

from decimal import Decimal

import pytest
from app.domain.enums import TransactionType
from app.domain.pnl import (
    FifoLot,
    calculate_average_cost,
    calculate_buy_unit_cost,
    calculate_realized_pnl,
    calculate_unrealized_pnl,
    consume_fifo,
)
from app.schemas.transaction import TransactionCreate
from pydantic import ValidationError


def test_calculate_unrealized_pnl() -> None:
    result = calculate_unrealized_pnl(
        quantity=Decimal("10"),
        average_cost=Decimal("150"),
        current_price=Decimal("178.50"),
    )

    assert result.cost_basis == Decimal("1500.0000")
    assert result.current_value == Decimal("1785.0000")
    assert result.amount == Decimal("285.0000")
    assert result.percentage == Decimal("19.0000")


def test_buy_unit_cost_includes_fees_and_taxes() -> None:
    assert calculate_buy_unit_cost(
        quantity=Decimal("10"),
        unit_price=Decimal("100"),
        fees=Decimal("5"),
        taxes=Decimal("2"),
    ) == Decimal("100.7000000000")


def test_fifo_consumes_oldest_lots_and_calculates_cost_basis() -> None:
    result = consume_fifo(
        lots=[
            FifoLot(quantity=Decimal("10"), unit_cost=Decimal("100")),
            FifoLot(quantity=Decimal("8"), unit_cost=Decimal("120")),
        ],
        quantity=Decimal("12"),
    )

    assert result.consumed_quantities == (
        Decimal("10.0000000000"),
        Decimal("2.0000000000"),
    )
    assert result.cost_basis == Decimal("1240.0000")


def test_fifo_rejects_quantity_above_open_lots() -> None:
    with pytest.raises(ValueError, match="insufficient open quantity"):
        consume_fifo(
            lots=[FifoLot(quantity=Decimal("1"), unit_cost=Decimal("100"))],
            quantity=Decimal("2"),
        )


def test_realized_pnl_deducts_sell_expenses() -> None:
    assert calculate_realized_pnl(
        quantity=Decimal("12"),
        unit_price=Decimal("150"),
        fees=Decimal("5"),
        taxes=Decimal("3"),
        cost_basis=Decimal("1240"),
    ) == Decimal("552.0000")


def test_average_cost_uses_only_open_lot_quantities() -> None:
    assert calculate_average_cost(
        lots=[
            FifoLot(quantity=Decimal("2"), unit_cost=Decimal("100")),
            FifoLot(quantity=Decimal("3"), unit_cost=Decimal("120")),
        ]
    ) == Decimal("112.0000000000")
    assert calculate_average_cost(lots=[]) == Decimal("0")


def test_transaction_rejects_quantity_that_rounds_to_zero() -> None:
    with pytest.raises(ValidationError, match="below the supported precision"):
        TransactionCreate(
            asset_id="de305d54-75b4-431b-adb2-eb6b9e546014",
            transaction_type=TransactionType.BUY,
            quantity=Decimal("0.00000000001"),
            unit_price=Decimal("1"),
            currency="USD",
            trade_date="2026-06-23T12:00:00Z",
        )
