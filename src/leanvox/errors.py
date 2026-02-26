"""Leanvox error types."""

from __future__ import annotations


class LeanvoxError(Exception):
    """Base error for all Leanvox API errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "unknown",
        status_code: int = 0,
        body: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.body = body or {}


class InvalidRequestError(LeanvoxError):
    """400 — Bad parameters."""
    pass


class AuthenticationError(LeanvoxError):
    """401 — Invalid API key."""
    pass


class InsufficientBalanceError(LeanvoxError):
    """402 — Not enough credits."""

    def __init__(self, message: str, *, balance_cents: float = 0, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.balance_cents = balance_cents


class NotFoundError(LeanvoxError):
    """404 — Resource not found."""
    pass


class RateLimitError(LeanvoxError):
    """429 — Too many requests."""

    def __init__(self, message: str, *, retry_after: float = 0, **kwargs) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(LeanvoxError):
    """500 — Internal server error."""
    pass


class StreamingFormatError(InvalidRequestError):
    """Raised when non-MP3 format is passed to stream()."""
    pass


# Map HTTP status codes to error classes
_ERROR_MAP: dict[int, type[LeanvoxError]] = {
    400: InvalidRequestError,
    401: AuthenticationError,
    402: InsufficientBalanceError,
    404: NotFoundError,
    429: RateLimitError,
    500: ServerError,
}


def _raise_for_status(status_code: int, body: dict) -> None:
    """Raise typed error from API response."""
    if status_code < 400:
        return
    error_data = body.get("error", body)
    message = error_data.get("message", f"API error {status_code}")
    code = error_data.get("code", "unknown")
    cls = _ERROR_MAP.get(status_code, LeanvoxError)

    kwargs: dict = {"code": code, "status_code": status_code, "body": body}
    if cls is InsufficientBalanceError:
        kwargs["balance_cents"] = error_data.get("balance_cents", 0)
    elif cls is RateLimitError:
        kwargs["retry_after"] = error_data.get("retry_after", 0)

    raise cls(message, **kwargs)
