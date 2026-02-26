"""Tests for retry logic — 5xx, 429, exponential backoff, Retry-After header."""

from unittest.mock import patch

import httpx
import pytest
import respx

from leanvox import Leanvox
from leanvox.errors import LeanvoxError, RateLimitError, ServerError

BASE_URL = "https://api.leanvox.com"
API_KEY = "lv_live_test_key_123"


@pytest.fixture
def client():
    c = Leanvox(api_key=API_KEY, base_url=BASE_URL, max_retries=2)
    yield c
    c.close()


@pytest.fixture
def client_no_retry():
    c = Leanvox(api_key=API_KEY, base_url=BASE_URL, max_retries=0)
    yield c
    c.close()


class TestRetryOn5xx:
    @respx.mock
    def test_retries_on_500_then_succeeds(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.Response(500, json={"error": {"message": "Internal error", "code": "server_error"}}),
            httpx.Response(200, json={
                "audio_url": "https://cdn.leanvox.com/ok.mp3",
                "model": "standard", "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        with patch("time.sleep"):
            result = client.generate("Hello")
        assert result.audio_url == "https://cdn.leanvox.com/ok.mp3"
        assert route.call_count == 2

    @respx.mock
    def test_retries_on_502(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.Response(502, json={"error": {"message": "Bad gateway"}}),
            httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        with patch("time.sleep"):
            client.generate("Hello")
        assert route.call_count == 2

    @respx.mock
    def test_retries_on_503(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.Response(503, json={"error": {"message": "Service unavailable"}}),
            httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        with patch("time.sleep"):
            client.generate("Hello")
        assert route.call_count == 2

    @respx.mock
    def test_retries_on_504(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.Response(504, json={"error": {"message": "Gateway timeout"}}),
            httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        with patch("time.sleep"):
            client.generate("Hello")
        assert route.call_count == 2

    @respx.mock
    def test_exhausts_retries_then_raises(self, client):
        respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(500, json={
                "error": {"message": "Internal error", "code": "server_error"},
            })
        )
        with patch("time.sleep"):
            with pytest.raises(ServerError, match="Internal error"):
                client.generate("Hello")

    @respx.mock
    def test_no_retry_on_500_when_max_retries_zero(self, client_no_retry):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(500, json={
                "error": {"message": "Internal error", "code": "server_error"},
            })
        )
        with pytest.raises(ServerError):
            client_no_retry.generate("Hello")
        assert route.call_count == 1


class TestRetryOn429:
    @respx.mock
    def test_retries_on_429_then_succeeds(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.Response(429, json={
                "error": {"message": "Rate limited", "code": "rate_limit", "retry_after": 1},
            }),
            httpx.Response(200, json={
                "audio_url": "https://cdn.leanvox.com/ok.mp3",
                "model": "standard", "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        with patch("time.sleep"):
            result = client.generate("Hello")
        assert result.audio_url == "https://cdn.leanvox.com/ok.mp3"
        assert route.call_count == 2

    @respx.mock
    def test_429_exhausted_raises_rate_limit_error(self, client):
        respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(429, json={
                "error": {"message": "Rate limited", "code": "rate_limit", "retry_after": 1},
            })
        )
        with patch("time.sleep"):
            with pytest.raises(RateLimitError, match="Rate limited"):
                client.generate("Hello")


class TestNoRetryOn4xx:
    @respx.mock
    def test_no_retry_on_400(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(400, json={
                "error": {"message": "Bad request", "code": "invalid_request"},
            })
        )
        with pytest.raises(LeanvoxError):
            client.generate("Hello")
        assert route.call_count == 1

    @respx.mock
    def test_no_retry_on_401(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(401, json={
                "error": {"message": "Unauthorized", "code": "auth_error"},
            })
        )
        with pytest.raises(LeanvoxError):
            client.generate("Hello")
        assert route.call_count == 1

    @respx.mock
    def test_no_retry_on_404(self, client):
        route = respx.get(f"{BASE_URL}/v1/jobs/nonexistent").mock(
            return_value=httpx.Response(404, json={
                "error": {"message": "Not found", "code": "not_found"},
            })
        )
        with pytest.raises(LeanvoxError):
            client.get_job("nonexistent")
        assert route.call_count == 1


class TestExponentialBackoff:
    @respx.mock
    def test_backoff_increases(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.Response(500, json={"error": {"message": "err"}}),
            httpx.Response(500, json={"error": {"message": "err"}}),
            httpx.Response(500, json={"error": {"message": "err"}}),
        ]
        sleep_calls = []
        with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
            with pytest.raises(ServerError):
                client.generate("Hello")
        # Should have slept twice (before retry 1 and retry 2)
        assert len(sleep_calls) == 2
        # Backoff base: [1.0, 2.0, 4.0] → attempt 0 = 1.0, attempt 1 = 2.0
        assert sleep_calls[0] == 1.0
        assert sleep_calls[1] == 2.0

    @respx.mock
    def test_retry_after_header_respected(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.Response(
                429,
                json={"error": {"message": "Rate limited", "code": "rate_limit", "retry_after": 5}},
                headers={"Retry-After": "3.5"},
            ),
            httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        sleep_calls = []
        with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
            client.generate("Hello")
        # Should respect Retry-After header value 3.5 instead of default backoff 1.0
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == 3.5

    @respx.mock
    def test_backoff_without_retry_after_header(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.Response(500, json={"error": {"message": "err"}}),
            httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        sleep_calls = []
        with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
            client.generate("Hello")
        # Without Retry-After, uses backoff base: attempt 0 = 1.0
        assert sleep_calls[0] == 1.0


class TestConnectionRetry:
    @respx.mock
    def test_retries_on_connect_error(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.ConnectError("Connection refused"),
            httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        with patch("time.sleep"):
            result = client.generate("Hello")
        assert result is not None

    @respx.mock
    def test_retries_on_timeout(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate")
        route.side_effect = [
            httpx.TimeoutException("Request timed out"),
            httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            }),
        ]
        with patch("time.sleep"):
            result = client.generate("Hello")
        assert result is not None

    @respx.mock
    def test_connection_error_exhausted(self, client):
        respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        with patch("time.sleep"):
            with pytest.raises(LeanvoxError, match="Connection failed"):
                client.generate("Hello")


class TestRetryCount:
    @respx.mock
    def test_total_attempts_is_max_retries_plus_one(self, client):
        """With max_retries=2, there should be 3 total attempts."""
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(500, json={"error": {"message": "err"}})
        )
        with patch("time.sleep"):
            with pytest.raises(ServerError):
                client.generate("Hello")
        assert route.call_count == 3  # 1 initial + 2 retries
