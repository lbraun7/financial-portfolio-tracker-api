"""Asset ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import AssetType

if TYPE_CHECKING:
    from app.models.position import Position
    from app.models.transaction import Transaction


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tradable asset tracked by the platform."""

    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", "currency"),
        CheckConstraint("length(symbol) > 0", name="symbol_not_empty"),
        CheckConstraint("length(name) > 0", name="name_not_empty"),
        CheckConstraint("length(currency) = 3", name="currency_length"),
        CheckConstraint("currency = upper(currency)", name="currency_uppercase"),
        CheckConstraint(
            "exchange IS NULL OR length(exchange) > 0",
            name="exchange_not_empty_when_set",
        ),
        CheckConstraint(
            "isin IS NULL OR length(isin) = 12",
            name="isin_length_when_set",
        ),
        CheckConstraint(
            "isin IS NULL OR isin = upper(isin)",
            name="isin_uppercase_when_set",
        ),
    )

    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(
            AssetType,
            name="asset_type",
            values_callable=lambda enum_: [member.value for member in enum_],
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, unique=True)

    transactions: Mapped[list[Transaction]] = relationship("Transaction", back_populates="asset")
    positions: Mapped[list[Position]] = relationship("Position", back_populates="asset")
