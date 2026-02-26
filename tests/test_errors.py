"""Tests for error mapping."""

import pytest
from leanvox.errors import (
    _raise_for_status,
    AuthenticationError,
    InsufficientBalanceError,
    InvalidRequestError,
    LeanvoxError,
    NotFoundError,
    RateLimitError,
    ServerError,
)


class TestRaiseForStatus:
    def test_200_no_error(self):
        _raise_for_status(200, {})

    def test_400_invalid_request(self):
        with pytest.raises(InvalidRequestError) as exc_info:
            _raise_for_status(400, {"error": {"message": "bad", "code": "invalid_request"}})
        assert exc_info.value.status_code == 400
        assert exc_info.value.code == "invalid_request"

    def test_401_auth_error(self):
        with pytest.raises(AuthenticationError):
            _raise_for_status(401, {"error": {"message": "invalid key", "code": "invalid_api_key"}})

    def test_402_balance_error(self):
        with pytest.raises(InsufficientBalanceError) as exc_info:
            _raise_for_status(402, {"error": {"message": "low", "code": "insufficient_balance", "balance_cents": 50}})
        assert exc_info.value.balance_cents == 50

    def test_404_not_found(self):
        with pytest.raises(NotFoundError):
            _raise_for_status(404, {"error": {"message": "nope", "code": "not_found"}})

    def test_429_rate_limit(self):
        with pytest.raises(RateLimitError) as exc_info:
            _raise_for_status(429, {"error": {"message": "slow down", "code": "rate_limit_exceeded", "retry_after": 5}})
        assert exc_info.value.retry_after == 5

    def test_500_server_error(self):
        with pytest.raises(ServerError):
            _raise_for_status(500, {"error": {"message": "boom", "code": "server_error"}})

    def test_unknown_status(self):
        with pytest.raises(LeanvoxError):
            _raise_for_status(418, {"error": {"message": "teapot", "code": "teapot"}})


class TestErrorHierarchy:
    def test_all_inherit_from_leanvox_error(self):
        for cls in [InvalidRequestError, AuthenticationError, InsufficientBalanceError,
                     NotFoundError, RateLimitError, ServerError]:
            err = cls("test", code="test", status_code=0)
            assert isinstance(err, LeanvoxError)
