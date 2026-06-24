"""Decimal and Numeric policy tests."""

from decimal import Decimal

import pytest
from app.domain.money import (
    MONEY_PRECISION,
    MONEY_SCALE,
    PRICE_PRECISION,
    PRICE_SCALE,
    QUANTITY_PRECISION,
    QUANTITY_SCALE,
    money_numeric,
    price_numeric,
    quantity_numeric,
    quantize_money,
    quantize_price,
    quantize_quantity,
    to_decimal,
)
from app.models import Position, PositionLot, Transaction
from sqlalchemy import Numeric


def numeric_scale(column_type: object) -> int:
    assert isinstance(column_type, Numeric)
    assert column_type.scale is not None
    return column_type.scale


def test_numeric_helpers_expose_expected_precision_and_scale() -> None:
    money = money_numeric()
    price = price_numeric()
    quantity = quantity_numeric()

    assert (money.precision, money.scale) == (MONEY_PRECISION, MONEY_SCALE)
    assert (price.precision, price.scale) == (PRICE_PRECISION, PRICE_SCALE)
    assert (quantity.precision, quantity.scale) == (QUANTITY_PRECISION, QUANTITY_SCALE)


def test_decimal_quantization_policy_uses_half_up_rounding() -> None:
    assert quantize_money("10.55555") == Decimal("10.5556")
    assert quantize_price("10.12345678905") == Decimal("10.1234567891")
    assert quantize_quantity("0.12345678905") == Decimal("0.1234567891")


def test_decimal_inputs_reject_bool_and_float_values() -> None:
    with pytest.raises(TypeError):
        to_decimal(True)

    with pytest.raises(TypeError):
        to_decimal(1.1)


def test_models_use_domain_numeric_policy() -> None:
    assert numeric_scale(Transaction.__table__.c.quantity.type) == QUANTITY_SCALE
    assert numeric_scale(Transaction.__table__.c.unit_price.type) == PRICE_SCALE
    assert numeric_scale(Transaction.__table__.c.fees.type) == MONEY_SCALE
    assert numeric_scale(Transaction.__table__.c.taxes.type) == MONEY_SCALE
    assert numeric_scale(Transaction.__table__.c.realized_pnl.type) == MONEY_SCALE

    assert numeric_scale(Position.__table__.c.quantity.type) == QUANTITY_SCALE
    assert numeric_scale(Position.__table__.c.average_cost.type) == PRICE_SCALE
    assert numeric_scale(Position.__table__.c.realized_pnl.type) == MONEY_SCALE

    assert numeric_scale(PositionLot.__table__.c.quantity_initial.type) == QUANTITY_SCALE
    assert numeric_scale(PositionLot.__table__.c.quantity_open.type) == QUANTITY_SCALE
    assert numeric_scale(PositionLot.__table__.c.unit_cost.type) == PRICE_SCALE
