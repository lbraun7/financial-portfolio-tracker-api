"""Portfolio schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PortfolioBase(BaseModel):
    """Shared portfolio payload fields."""

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    base_currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Trim names and reject blank values."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        """Trim optional descriptions and store blanks as null."""

        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("base_currency")
    @classmethod
    def normalize_base_currency(cls, value: str) -> str:
        """Normalize ISO-like currency codes."""

        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("base_currency must be a 3-letter code")
        return normalized


class PortfolioCreate(PortfolioBase):
    """Payload used to create a portfolio."""


class PortfolioUpdate(BaseModel):
    """Payload used to partially update a portfolio."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("base_currency")
    @classmethod
    def normalize_base_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("base_currency must be a 3-letter code")
        return normalized


class PortfolioRead(BaseModel):
    """Public portfolio representation."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    base_currency: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
