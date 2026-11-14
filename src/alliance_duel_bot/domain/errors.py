class ContentValidationError(ValueError):
    """Raised when the campaign content catalog is invalid."""


class DeliveryError(RuntimeError):
    """Raised when Telegram cannot accept a message."""


class RecipientUnavailableError(DeliveryError):
    """Raised when a Telegram user has blocked the bot or is unreachable."""
