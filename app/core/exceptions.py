"""Application exception hierarchy."""


class ApplicationError(Exception):
    """Base class for expected application-level failures."""


class NotFoundError(ApplicationError):
    """Base class for resources that are absent or inaccessible."""


class ConflictError(ApplicationError):
    """Base class for operations that conflict with current state."""


class ValidationError(ApplicationError):
    """Base class for domain validation failures."""


class PortfolioNotFoundError(NotFoundError):
    """Raised when a portfolio is absent or not owned by the user."""


class AssetNotFoundError(NotFoundError):
    """Raised when an asset does not exist."""


class PortfolioNameAlreadyExistsError(ConflictError):
    """Raised when a user already has a portfolio with the requested name."""


class InsufficientPositionError(ConflictError):
    """Raised when a sell exceeds the currently open quantity."""


class IdempotencyConflictError(ConflictError):
    """Raised when an idempotency key is reused with a different payload."""


class OutOfOrderTransactionError(ConflictError):
    """Raised when a transaction predates the latest ledger entry for an asset."""


class AssetCurrencyMismatchError(ValidationError):
    """Raised when a transaction currency differs from the asset currency."""


class PortfolioCurrencyMismatchError(ValidationError):
    """Raised when a position cannot be valued in the portfolio base currency."""


class PriceUnavailableError(ApplicationError):
    """Raised when a current market price cannot be obtained."""
