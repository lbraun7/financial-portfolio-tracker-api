"""Portfolio ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.position import Position
    from app.models.transaction import Transaction
    from app.models.user import User


class Portfolio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Investment portfolio owned by a user."""

    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint("length(base_currency) = 3", name="base_currency_length"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    user: Mapped[User] = relationship("User", back_populates="portfolios")
    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    positions: Mapped[list[Position]] = relationship(
        "Position",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
