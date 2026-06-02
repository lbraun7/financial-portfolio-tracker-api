"""ORM model metadata tests."""

from typing import Any

from app.db.base import Base
from app.domain.enums import AssetType, TransactionType
from app.models import Asset, Portfolio, Position, PositionLot, Transaction
from sqlalchemy import CheckConstraint, Enum, UniqueConstraint
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
    assert asset_type.native_enum is False
    assert asset_type.create_constraint is True
    assert asset_type.validate_strings is True
    assert transaction_type.native_enum is False
    assert transaction_type.create_constraint is True
    assert transaction_type.validate_strings is True
    assert set(asset_type.enums) == {member.value for member in AssetType}
    assert set(transaction_type.enums) == {member.value for member in TransactionType}


def constraint_names(model: Any, constraint_type: type[Any]) -> set[str | None]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, constraint_type)
    }


def test_models_expose_expected_check_constraints() -> None:
    assert constraint_names(Portfolio, CheckConstraint) >= {
        "ck_portfolios_base_currency_length",
        "ck_portfolios_base_currency_uppercase",
        "ck_portfolios_name_not_empty",
    }
    assert constraint_names(Asset, CheckConstraint) >= {
        "ck_assets_asset_type",
        "ck_assets_currency_length",
        "ck_assets_currency_uppercase",
        "ck_assets_exchange_not_empty_when_set",
        "ck_assets_isin_length_when_set",
        "ck_assets_isin_uppercase_when_set",
        "ck_assets_name_not_empty",
        "ck_assets_symbol_not_empty",
    }
    assert constraint_names(Transaction, CheckConstraint) >= {
        "ck_transactions_currency_length",
        "ck_transactions_currency_uppercase",
        "ck_transactions_fees_non_negative",
        "ck_transactions_idempotency_key_not_empty_when_set",
        "ck_transactions_quantity_positive",
        "ck_transactions_taxes_non_negative",
        "ck_transactions_transaction_type",
        "ck_transactions_unit_price_non_negative",
    }
    assert constraint_names(Position, CheckConstraint) >= {
        "ck_positions_average_cost_non_negative",
        "ck_positions_quantity_non_negative",
    }
    assert constraint_names(PositionLot, CheckConstraint) >= {
        "ck_position_lots_quantity_initial_positive",
        "ck_position_lots_quantity_open_lte_initial",
        "ck_position_lots_quantity_open_non_negative",
        "ck_position_lots_unit_cost_non_negative",
    }


def test_models_expose_expected_unique_constraints() -> None:
    assert constraint_names(Portfolio, UniqueConstraint) >= {"uq_portfolios_user_id"}
    assert constraint_names(Asset, UniqueConstraint) >= {
        "uq_assets_isin",
        "uq_assets_symbol",
    }
    assert constraint_names(Transaction, UniqueConstraint) >= {
        "uq_transactions_portfolio_id",
    }
    assert constraint_names(Position, UniqueConstraint) >= {"uq_positions_portfolio_id"}
    assert constraint_names(PositionLot, UniqueConstraint) >= {
        "uq_position_lots_source_transaction_id",
    }
