"""Asset schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import AssetType


class AssetBase(BaseModel):
    """Shared asset payload fields."""

    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    asset_type: AssetType
    currency: str = Field(min_length=3, max_length=3)
    exchange: str | None = Field(default=None, max_length=32)
    isin: str | None = Field(default=None, min_length=12, max_length=12)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a 3-letter code")
        return normalized

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("isin")
    @classmethod
    def normalize_isin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            return None
        if len(normalized) != 12:
            raise ValueError("isin must contain 12 characters")
        return normalized


class AssetCreate(AssetBase):
    """Payload used to create an asset."""


class AssetLookup(BaseModel):
    """Payload used to look up and create an asset by symbol."""

    symbol: str = Field(min_length=1, max_length=32)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        return normalized


class AssetRead(BaseModel):
    """Public asset representation."""

    id: uuid.UUID
    symbol: str
    name: str
    asset_type: AssetType
    currency: str
    exchange: str | None
    isin: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
