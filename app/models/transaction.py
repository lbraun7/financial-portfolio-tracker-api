"""Transaction ORM model."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import TransactionType
from app.domain.money import ZERO_DECIMAL, money_numeric, price_numeric, quantity_numeric

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.portfolio import Portfolio
    from app.models.position_lot import PositionLot


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable portfolio transaction ledger entry."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("fees >= 0", name="fees_non_negative"),
        CheckConstraint("taxes >= 0", name="taxes_non_negative"),
        CheckConstraint("length(currency) = 3", name="currency_length"),
    )

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            name="transaction_type",
            values_callable=lambda enum_: [member.value for member in enum_],
        ),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(quantity_numeric(), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(price_numeric(), nullable=False)
    fees: Mapped[Decimal] = mapped_column(money_numeric(), nullable=False, default=ZERO_DECIMAL)
    taxes: Mapped[Decimal] = mapped_column(money_numeric(), nullable=False, default=ZERO_DECIMAL)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    trade_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    portfolio: Mapped[Portfolio] = relationship("Portfolio", back_populates="transactions")
    asset: Mapped[Asset] = relationship("Asset", back_populates="transactions")
    lots: Mapped[list[PositionLot]] = relationship(
        "PositionLot",
        back_populates="source_transaction",
    )
