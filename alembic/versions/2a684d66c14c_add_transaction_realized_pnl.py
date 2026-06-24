"""add transaction realized pnl

Revision ID: 2a684d66c14c
Revises: faeb6b93d053
Create Date: 2026-06-23 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2a684d66c14c"
down_revision: str | None = "faeb6b93d053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "realized_pnl",
            sa.Numeric(precision=19, scale=4),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.alter_column("transactions", "realized_pnl", server_default=None)


def downgrade() -> None:
    op.drop_column("transactions", "realized_pnl")
