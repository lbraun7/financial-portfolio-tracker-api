"""Position ORM model."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.portfolio import Portfolio
    from app.models.position_lot import PositionLot


class Position(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Materialized current holding for one asset inside a portfolio."""

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "asset_id"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("average_cost >= 0", name="average_cost_non_negative"),
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
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(28, 10),
        nullable=False,
        default=Decimal("0"),
    )

    portfolio: Mapped[Portfolio] = relationship("Portfolio", back_populates="positions")
    asset: Mapped[Asset] = relationship("Asset", back_populates="positions")
    lots: Mapped[list[PositionLot]] = relationship(
        "PositionLot",
        back_populates="position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
