"""Transaction engine service tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from app.core.exceptions import IdempotencyConflictError, InsufficientPositionError
from app.domain.enums import TransactionType
from app.models.position import Position
from app.models.position_lot import PositionLot
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate
from app.services.transaction import TransactionService


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, _instance: object) -> None:
        return None


class PortfolioStub:
    async def get_for_user_for_update(self, **_kwargs: object) -> object:
        return SimpleNamespace(id=uuid.uuid4())


class AssetStub:
    def __init__(self, asset_id: uuid.UUID) -> None:
        self.asset_id = asset_id

    async def get_by_id(self, asset_id: uuid.UUID) -> object:
        assert asset_id == self.asset_id
        return SimpleNamespace(id=asset_id, currency="USD")


class TransactionStub:
    def __init__(self, existing: Transaction | None = None) -> None:
        self.created: list[Transaction] = []
        self.existing = existing

    async def get_by_idempotency_key(self, **_kwargs: object) -> Transaction | None:
        return self.existing

    async def get_latest_for_asset(self, **_kwargs: object) -> None:
        return None

    def add(self, **kwargs: Any) -> Transaction:
        transaction = Transaction(id=uuid.uuid4(), **kwargs)
        self.created.append(transaction)
        return transaction


class PositionStub:
    def __init__(
        self,
        *,
        position: Position | None = None,
        lots: list[PositionLot] | None = None,
    ) -> None:
        self.position = position
        self.lots = lots or []
        self.added_lots: list[PositionLot] = []

    async def get_for_update(self, **_kwargs: object) -> Position | None:
        return self.position

    def add_position(self, *, portfolio_id: uuid.UUID, asset_id: uuid.UUID) -> Position:
        self.position = Position(
            id=uuid.uuid4(),
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            quantity=Decimal("0"),
            average_cost=Decimal("0"),
            realized_pnl=Decimal("0"),
        )
        return self.position

    async def list_open_lots_for_update(
        self,
        _position_id: uuid.UUID,
    ) -> list[PositionLot]:
        return self.lots

    def add_lot(self, **kwargs: Any) -> PositionLot:
        lot = PositionLot(
            id=uuid.uuid4(),
            quantity_initial=kwargs.pop("quantity"),
            quantity_open=kwargs.get("quantity_initial", Decimal("0")),
            **kwargs,
        )
        lot.quantity_open = lot.quantity_initial
        self.added_lots.append(lot)
        return lot


def payload(
    *,
    asset_id: uuid.UUID,
    transaction_type: TransactionType,
    quantity: str,
    unit_price: str,
    fees: str = "0",
    taxes: str = "0",
) -> TransactionCreate:
    return TransactionCreate(
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        fees=Decimal(fees),
        taxes=Decimal(taxes),
        currency="USD",
        trade_date=datetime(2026, 6, 23, 12, tzinfo=UTC),
    )


def build_service(
    *,
    asset_id: uuid.UUID,
    positions: PositionStub,
    transactions: TransactionStub | None = None,
) -> tuple[TransactionService, FakeSession, TransactionStub]:
    session = FakeSession()
    service = TransactionService(session)  # type: ignore[arg-type]
    transaction_repository = transactions or TransactionStub()
    service.portfolios = PortfolioStub()  # type: ignore[assignment]
    service.assets = AssetStub(asset_id)  # type: ignore[assignment]
    service.positions = positions  # type: ignore[assignment]
    service.transactions = transaction_repository  # type: ignore[assignment]
    return service, session, transaction_repository


async def test_buy_creates_fifo_lot_and_updates_position() -> None:
    asset_id = uuid.uuid4()
    positions = PositionStub()
    service, session, transactions = build_service(asset_id=asset_id, positions=positions)

    transaction = await service.record(
        portfolio_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        payload=payload(
            asset_id=asset_id,
            transaction_type=TransactionType.BUY,
            quantity="10",
            unit_price="100",
            fees="5",
            taxes="2",
        ),
        idempotency_key="buy-1",
    )

    assert transaction.realized_pnl == Decimal("0")
    assert positions.position is not None
    assert positions.position.quantity == Decimal("10.0000000000")
    assert positions.position.average_cost == Decimal("100.7000000000")
    assert positions.added_lots[0].unit_cost == Decimal("100.7000000000")
    assert transactions.created == [transaction]
    assert session.commits == 1
    assert session.rollbacks == 0


async def test_sell_consumes_fifo_and_updates_realized_pnl() -> None:
    portfolio_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    position = Position(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        quantity=Decimal("18"),
        average_cost=Decimal("108.8888888889"),
        realized_pnl=Decimal("0"),
    )
    lots = [
        PositionLot(
            id=uuid.uuid4(),
            position_id=position.id,
            source_transaction_id=uuid.uuid4(),
            quantity_initial=Decimal("10"),
            quantity_open=Decimal("10"),
            unit_cost=Decimal("100"),
            acquired_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        PositionLot(
            id=uuid.uuid4(),
            position_id=position.id,
            source_transaction_id=uuid.uuid4(),
            quantity_initial=Decimal("8"),
            quantity_open=Decimal("8"),
            unit_cost=Decimal("120"),
            acquired_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
    ]
    positions = PositionStub(position=position, lots=lots)
    service, session, _transactions = build_service(asset_id=asset_id, positions=positions)

    transaction = await service.record(
        portfolio_id=portfolio_id,
        user_id=uuid.uuid4(),
        payload=payload(
            asset_id=asset_id,
            transaction_type=TransactionType.SELL,
            quantity="12",
            unit_price="150",
            fees="5",
            taxes="3",
        ),
        idempotency_key="sell-1",
    )

    assert lots[0].quantity_open == Decimal("0E-10")
    assert lots[1].quantity_open == Decimal("6.0000000000")
    assert position.quantity == Decimal("6.0000000000")
    assert position.average_cost == Decimal("120.0000000000")
    assert position.realized_pnl == Decimal("552.0000")
    assert transaction.realized_pnl == Decimal("552.0000")
    assert session.commits == 1


async def test_failed_sell_rolls_back_all_changes() -> None:
    portfolio_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    position = Position(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        quantity=Decimal("1"),
        average_cost=Decimal("100"),
        realized_pnl=Decimal("0"),
    )
    service, session, _transactions = build_service(
        asset_id=asset_id,
        positions=PositionStub(position=position),
    )

    with pytest.raises(InsufficientPositionError):
        await service.record(
            portfolio_id=portfolio_id,
            user_id=uuid.uuid4(),
            payload=payload(
                asset_id=asset_id,
                transaction_type=TransactionType.SELL,
                quantity="2",
                unit_price="150",
            ),
            idempotency_key="sell-too-much",
        )

    assert session.commits == 0
    assert session.rollbacks == 1


async def test_same_idempotency_key_and_payload_returns_existing_transaction() -> None:
    portfolio_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    request_payload = payload(
        asset_id=asset_id,
        transaction_type=TransactionType.BUY,
        quantity="2",
        unit_price="100",
    )
    existing = Transaction(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=request_payload.transaction_type,
        quantity=request_payload.quantity,
        unit_price=request_payload.unit_price,
        fees=request_payload.fees,
        taxes=request_payload.taxes,
        realized_pnl=Decimal("0"),
        currency=request_payload.currency,
        trade_date=request_payload.trade_date,
        settlement_date=request_payload.settlement_date,
        notes=request_payload.notes,
        idempotency_key="same-key",
    )
    service, session, transactions = build_service(
        asset_id=asset_id,
        positions=PositionStub(),
        transactions=TransactionStub(existing),
    )

    result = await service.record(
        portfolio_id=portfolio_id,
        user_id=uuid.uuid4(),
        payload=request_payload,
        idempotency_key="same-key",
    )

    assert result is existing
    assert transactions.created == []
    assert session.commits == 1


async def test_reused_idempotency_key_with_different_payload_is_rejected() -> None:
    portfolio_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    request_payload = payload(
        asset_id=asset_id,
        transaction_type=TransactionType.BUY,
        quantity="2",
        unit_price="100",
    )
    existing = Transaction(
        id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("1"),
        unit_price=request_payload.unit_price,
        fees=request_payload.fees,
        taxes=request_payload.taxes,
        realized_pnl=Decimal("0"),
        currency=request_payload.currency,
        trade_date=request_payload.trade_date,
        settlement_date=None,
        notes=None,
        idempotency_key="same-key",
    )
    service, session, _transactions = build_service(
        asset_id=asset_id,
        positions=PositionStub(),
        transactions=TransactionStub(existing),
    )

    with pytest.raises(IdempotencyConflictError):
        await service.record(
            portfolio_id=portfolio_id,
            user_id=uuid.uuid4(),
            payload=request_payload,
            idempotency_key="same-key",
        )

    assert session.commits == 0
    assert session.rollbacks == 1
