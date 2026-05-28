"""Domain enumerations."""

from enum import StrEnum


class AssetType(StrEnum):
    """Supported investment asset categories."""

    STOCK = "stock"
    ETF = "etf"
    REIT = "reit"
    CRYPTO = "crypto"
    FIXED_INCOME = "fixed_income"


class TransactionType(StrEnum):
    """Supported portfolio ledger event types."""

    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    SPLIT = "split"
