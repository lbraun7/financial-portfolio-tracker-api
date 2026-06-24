"""Position schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PositionRead(BaseModel):
    """Materialized current holding."""

    id: uuid.UUID
    portfolio_id: uuid.UUID
    asset_id: uuid.UUID
    quantity: Decimal
    average_cost: Decimal
    realized_pnl: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
