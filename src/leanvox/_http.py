"""HTTP client with retry logic."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator

import httpx

from .errors import _raise_for_status, RateLimitError, LeanvoxError


_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_DEFAULT_TIMEOUT = 30.0
_STREAM_TIMEOUT = 120.0
_BACKOFF_BASE = [1.0, 2.0, 4.0]


class HTTPClient:
    """Sync HTTP client with retry and error handling."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "leanvox-python/0.1.0",
            },
            timeout=timeout,
        )

    @property
    def raw_client(self) -> httpx.Client:
        return self._client

    def request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        data: Any = None,
        files: Any = None,
        params: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        """Make an HTTP request with retry logic."""
        last_err: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                kwargs: dict[str, Any] = {"params": params}
                if files:
                    kwargs["files"] = files
                    kwargs["data"] = data
                elif json is not None:
                    kwargs["json"] = json

                resp = self._client.request(
                    method,
                    path,
                    timeout=timeout or self._timeout,
                    **kwargs,
                )

                if resp.status_code < 400:
                    return resp.json() if resp.content else {}

                # Parse error body
                try:
                    body = resp.json()
                except Exception:
                    body = {"error": {"message": resp.text}}

                # Don't retry 4xx (except 429)
                if resp.status_code < 500 and resp.status_code != 429:
                    _raise_for_status(resp.status_code, body)

                # Retry on 5xx and 429
                if resp.status_code in _RETRY_STATUS_CODES and attempt < self._max_retries:
                    wait = _get_backoff(attempt, resp)
                    time.sleep(wait)
                    continue

                _raise_for_status(resp.status_code, body)

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_err = e
                if attempt < self._max_retries:
                    time.sleep(_BACKOFF_BASE[min(attempt, len(_BACKOFF_BASE) - 1)])
                    continue
                raise LeanvoxError(
                    f"Connection failed after {self._max_retries + 1} attempts: {e}",
                    code="connection_error",
                ) from e

        if last_err:
            raise LeanvoxError(str(last_err), code="connection_error") from last_err
        return {}

    @contextmanager
    def stream(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> Iterator[httpx.Response]:
        """Make a streaming request. Returns raw response for iteration."""
        with self._client.stream(
            method,
            path,
            json=json,
            timeout=_STREAM_TIMEOUT,
        ) as resp:
            yield resp

    def close(self) -> None:
        self._client.close()


class AsyncHTTPClient:
    """Async HTTP client with retry logic."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "leanvox-python/0.1.0",
            },
            timeout=timeout,
        )

    @property
    def raw_client(self) -> httpx.AsyncClient:
        return self._client

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        data: Any = None,
        files: Any = None,
        params: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        """Make an async HTTP request with retry logic."""
        import asyncio

        last_err: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                kwargs: dict[str, Any] = {"params": params}
                if files:
                    kwargs["files"] = files
                    kwargs["data"] = data
                elif json is not None:
                    kwargs["json"] = json

                resp = await self._client.request(
                    method,
                    path,
                    timeout=timeout or self._timeout,
                    **kwargs,
                )

                if resp.status_code < 400:
                    return resp.json() if resp.content else {}

                try:
                    body = resp.json()
                except Exception:
                    body = {"error": {"message": resp.text}}

                if resp.status_code < 500 and resp.status_code != 429:
                    _raise_for_status(resp.status_code, body)

                if resp.status_code in _RETRY_STATUS_CODES and attempt < self._max_retries:
                    wait = _get_backoff(attempt, resp)
                    await asyncio.sleep(wait)
                    continue

                _raise_for_status(resp.status_code, body)

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_err = e
                if attempt < self._max_retries:
                    await asyncio.sleep(_BACKOFF_BASE[min(attempt, len(_BACKOFF_BASE) - 1)])
                    continue
                raise LeanvoxError(
                    f"Connection failed after {self._max_retries + 1} attempts: {e}",
                    code="connection_error",
                ) from e

        if last_err:
            raise LeanvoxError(str(last_err), code="connection_error") from last_err
        return {}

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> AsyncIterator[httpx.Response]:
        """Make an async streaming request."""
        async with self._client.stream(
            method,
            path,
            json=json,
            timeout=_STREAM_TIMEOUT,
        ) as resp:
            yield resp

    async def close(self) -> None:
        await self._client.aclose()


def _get_backoff(attempt: int, resp: httpx.Response | None = None) -> float:
    """Calculate backoff, respecting Retry-After header."""
    if resp is not None:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
    return _BACKOFF_BASE[min(attempt, len(_BACKOFF_BASE) - 1)]
