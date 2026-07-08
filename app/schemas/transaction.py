"""Transaction schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import TransactionType
from app.domain.money import (
    quantize_money,
    quantize_price,
    quantize_quantity,
)


class TransactionCreate(BaseModel):
    """Payload accepted by the transaction engine."""

    asset_id: uuid.UUID | None = None
    symbol: str | None = Field(default=None, min_length=1, max_length=32)
    transaction_type: TransactionType
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    taxes: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(min_length=3, max_length=3)
    trade_date: datetime
    settlement_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_asset_id_or_symbol(self) -> TransactionCreate:
        if (self.asset_id is None) == (self.symbol is None):
            raise ValueError("provide exactly one of asset_id or symbol")
        return self

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized

    @field_validator("transaction_type")
    @classmethod
    def only_buy_and_sell(cls, value: TransactionType) -> TransactionType:
        if value not in {TransactionType.BUY, TransactionType.SELL}:
            raise ValueError("only buy and sell transactions are currently supported")
        return value

    @field_validator("quantity")
    @classmethod
    def normalize_quantity(cls, value: Decimal) -> Decimal:
        normalized = quantize_quantity(value)
        if normalized <= 0:
            raise ValueError("quantity is below the supported precision")
        return normalized

    @field_validator("unit_price")
    @classmethod
    def normalize_unit_price(cls, value: Decimal) -> Decimal:
        return quantize_price(value)

    @field_validator("fees", "taxes")
    @classmethod
    def normalize_money(cls, value: Decimal) -> Decimal:
        return quantize_money(value)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a 3-letter code")
        return normalized

    @field_validator("trade_date")
    @classmethod
    def require_aware_trade_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("trade_date must include a timezone")
        return value.astimezone(UTC)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TransactionRead(BaseModel):
    """Public immutable ledger entry."""

    id: uuid.UUID
    portfolio_id: uuid.UUID
    asset_id: uuid.UUID
    transaction_type: TransactionType
    quantity: Decimal
    unit_price: Decimal
    fees: Decimal
    taxes: Decimal
    realized_pnl: Decimal
    currency: str
    trade_date: datetime
    settlement_date: date | None
    notes: str | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
