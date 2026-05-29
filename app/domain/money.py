"""Money and decimal precision helpers."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Final

from sqlalchemy import Numeric

DecimalInput = Decimal | float | int | str

MONEY_PRECISION: Final[int] = 19
MONEY_SCALE: Final[int] = 4
MONEY_QUANT: Final[Decimal] = Decimal("0.0001")

PRICE_PRECISION: Final[int] = 28
PRICE_SCALE: Final[int] = 10
PRICE_QUANT: Final[Decimal] = Decimal("0.0000000001")

QUANTITY_PRECISION: Final[int] = 28
QUANTITY_SCALE: Final[int] = 10
QUANTITY_QUANT: Final[Decimal] = Decimal("0.0000000001")

ZERO_DECIMAL: Final[Decimal] = Decimal("0")


def money_numeric() -> Numeric[Decimal]:
    """Return the database type for monetary amounts."""

    return Numeric(MONEY_PRECISION, MONEY_SCALE)


def price_numeric() -> Numeric[Decimal]:
    """Return the database type for unit prices and cost basis values."""

    return Numeric(PRICE_PRECISION, PRICE_SCALE)


def quantity_numeric() -> Numeric[Decimal]:
    """Return the database type for asset quantities."""

    return Numeric(QUANTITY_PRECISION, QUANTITY_SCALE)


def to_decimal(value: DecimalInput) -> Decimal:
    """Convert supported input values to Decimal without accepting floats."""

    if isinstance(value, bool):
        raise TypeError("Boolean values are not valid decimal inputs")
    if isinstance(value, float):
        raise TypeError("Float values are not valid decimal inputs")

    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value}") from exc


def quantize_decimal(value: DecimalInput, quantum: Decimal) -> Decimal:
    """Round a decimal value using the domain rounding mode."""

    return to_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)


def quantize_money(value: DecimalInput) -> Decimal:
    """Round monetary amounts to the configured money scale."""

    return quantize_decimal(value, MONEY_QUANT)


def quantize_price(value: DecimalInput) -> Decimal:
    """Round unit prices to the configured price scale."""

    return quantize_decimal(value, PRICE_QUANT)


def quantize_quantity(value: DecimalInput) -> Decimal:
    """Round asset quantities to the configured quantity scale."""

    return quantize_decimal(value, QUANTITY_QUANT)
