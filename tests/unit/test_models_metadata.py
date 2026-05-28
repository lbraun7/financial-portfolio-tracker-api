"""ORM model metadata tests."""

from app.db.base import Base
from app.domain.enums import AssetType, TransactionType
from app.models import Asset, Transaction
from sqlalchemy import Enum
from sqlalchemy.orm import configure_mappers


def test_domain_models_are_registered_in_metadata() -> None:
    configure_mappers()

    assert set(Base.metadata.tables) >= {
        "users",
        "portfolios",
        "assets",
        "transactions",
        "positions",
        "position_lots",
    }


def test_asset_and_transaction_enums_store_domain_values() -> None:
    asset_type = Asset.__table__.c.asset_type.type
    transaction_type = Transaction.__table__.c.transaction_type.type

    assert isinstance(asset_type, Enum)
    assert isinstance(transaction_type, Enum)
    assert set(asset_type.enums) == {member.value for member in AssetType}
    assert set(transaction_type.enums) == {
        member.value for member in TransactionType
    }
