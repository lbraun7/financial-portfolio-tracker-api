"""Position lot ORM model used for FIFO cost basis."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.money import price_numeric, quantity_numeric

if TYPE_CHECKING:
    from app.models.position import Position
    from app.models.transaction import Transaction


class PositionLot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Open FIFO lot created by a buy transaction."""

    __tablename__ = "position_lots"
    __table_args__ = (
        UniqueConstraint("source_transaction_id"),
        CheckConstraint("quantity_initial > 0", name="quantity_initial_positive"),
        CheckConstraint("quantity_open >= 0", name="quantity_open_non_negative"),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        CheckConstraint("quantity_open <= quantity_initial", name="quantity_open_lte_initial"),
    )

    position_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("positions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity_initial: Mapped[Decimal] = mapped_column(quantity_numeric(), nullable=False)
    quantity_open: Mapped[Decimal] = mapped_column(quantity_numeric(), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(price_numeric(), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    position: Mapped[Position] = relationship("Position", back_populates="lots")
    source_transaction: Mapped[Transaction] = relationship("Transaction", back_populates="lots")
