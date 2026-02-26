"""Leanvox client — sync and async."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from ._auth import ensure_api_key, resolve_api_key
from ._http import HTTPClient, AsyncHTTPClient
from ._resources import AccountResource, FilesResource, GenerationsResource, VoicesResource
from .errors import InvalidRequestError, StreamingFormatError
from .types import GenerateResult, Job


_DEFAULT_BASE_URL = "https://api.leanvox.com"
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_AUTO_ASYNC_THRESHOLD = 5000


class Leanvox:
    """Sync Leanvox client.

    Usage:
        client = Leanvox(api_key="lv_live_...")
        result = client.generate(text="Hello world!")
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        auto_async_threshold: int = _DEFAULT_AUTO_ASYNC_THRESHOLD,
    ) -> None:
        self._api_key = resolve_api_key(api_key)
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._auto_async_threshold = auto_async_threshold
        self._http: HTTPClient | None = None

        # Sub-resources (lazy init with HTTP client)
        self._voices: VoicesResource | None = None
        self._files: FilesResource | None = None
        self._generations: GenerationsResource | None = None
        self._account: AccountResource | None = None

    def _get_http(self) -> HTTPClient:
        if self._http is None:
            key = ensure_api_key(self._api_key)
            self._http = HTTPClient(
                base_url=self._base_url,
                api_key=key,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        return self._http

    @property
    def voices(self) -> VoicesResource:
        if self._voices is None:
            self._voices = VoicesResource(self._get_http())
        return self._voices

    @property
    def files(self) -> FilesResource:
        if self._files is None:
            self._files = FilesResource(self._get_http())
        return self._files

    @property
    def generations(self) -> GenerationsResource:
        if self._generations is None:
            self._generations = GenerationsResource(self._get_http())
        return self._generations

    @property
    def account(self) -> AccountResource:
        if self._account is None:
            self._account = AccountResource(self._get_http())
        return self._account

    def generate(
        self,
        text: str,
        *,
        model: str = "standard",
        voice: str = "",
        language: str = "en",
        format: str = "mp3",
        speed: float = 1.0,
        exaggeration: float = 0.5,
    ) -> GenerateResult:
        """Generate speech from text."""
        _validate_generate_params(text, model, speed, exaggeration)

        # Auto-route to async if text exceeds threshold
        if len(text) > self._auto_async_threshold:
            job = self.generate_async(
                text=text, model=model, voice=voice, language=language,
                format=format, speed=speed, exaggeration=exaggeration,
            )
            # Poll until complete
            import time
            while job.status not in ("completed", "failed"):
                time.sleep(2)
                job = self.get_job(job.id)
            if job.status == "failed":
                raise InvalidRequestError(
                    job.error or "Async generation failed",
                    code="job_failed", status_code=400,
                )
            return GenerateResult(
                audio_url=job.audio_url, model=model, voice=voice,
                characters=len(text), cost_cents=0,
                _http_client=self._get_http().raw_client,
            )

        body = _build_generate_body(text, model, voice, language, format, speed, exaggeration)
        data = self._get_http().request("POST", "/v1/tts/generate", json=body)
        return GenerateResult(
            audio_url=data.get("audio_url", ""),
            model=data.get("model", model),
            voice=data.get("voice", voice),
            characters=data.get("characters", 0),
            cost_cents=data.get("cost_cents", 0),
            _http_client=self._get_http().raw_client,
        )

    @contextmanager
    def stream(
        self,
        text: str,
        *,
        model: str = "standard",
        voice: str = "",
        language: str = "en",
        speed: float = 1.0,
        exaggeration: float = 0.5,
        format: str = "mp3",
    ) -> Iterator[Iterator[bytes]]:
        """Stream audio as byte chunks. Always MP3."""
        if format.lower() != "mp3":
            raise StreamingFormatError(
                "Streaming only supports MP3 format. "
                f"Got format='{format}'. Use generate() for other formats.",
                code="streaming_format_error", status_code=400,
            )
        _validate_generate_params(text, model, speed, exaggeration)
        body = _build_generate_body(text, model, voice, language, "mp3", speed, exaggeration)

        with self._get_http().stream("POST", "/v1/tts/stream", json=body) as resp:
            resp.raise_for_status()
            yield resp.iter_bytes(chunk_size=4096)

    def dialogue(
        self,
        lines: List[Dict[str, Any]],
        *,
        model: str = "pro",
        gap_ms: int = 500,
    ) -> GenerateResult:
        """Generate multi-speaker dialogue."""
        if len(lines) < 2:
            raise InvalidRequestError(
                "Dialogue requires at least 2 lines",
                code="invalid_request", status_code=400,
            )
        body = {"model": model, "lines": lines, "gap_ms": gap_ms}
        data = self._get_http().request("POST", "/v1/tts/dialogue", json=body)
        return GenerateResult(
            audio_url=data.get("audio_url", ""),
            model=data.get("model", model),
            voice="dialogue",
            characters=data.get("characters", 0),
            cost_cents=data.get("cost_cents", 0),
            _http_client=self._get_http().raw_client,
        )

    def generate_async(
        self,
        text: str,
        *,
        model: str = "standard",
        voice: str = "",
        language: str = "en",
        format: str = "mp3",
        speed: float = 1.0,
        exaggeration: float = 0.5,
        webhook_url: str = "",
    ) -> Job:
        """Submit async generation job."""
        _validate_generate_params(text, model, speed, exaggeration)
        body = _build_generate_body(text, model, voice, language, format, speed, exaggeration)
        if webhook_url:
            body["webhook_url"] = webhook_url
        data = self._get_http().request("POST", "/v1/tts/generate-async", json=body)
        return Job(
            id=data.get("id", ""),
            status=data.get("status", "pending"),
            estimated_seconds=data.get("estimated_seconds", 0),
        )

    def get_job(self, job_id: str) -> Job:
        """Get async job status."""
        data = self._get_http().request("GET", f"/v1/jobs/{job_id}")
        return Job(**{k: v for k, v in data.items() if k in Job.__dataclass_fields__})

    def list_jobs(self) -> List[Job]:
        """List all async jobs."""
        data = self._get_http().request("GET", "/v1/jobs")
        return [Job(**{k: v for k, v in j.items() if k in Job.__dataclass_fields__}) for j in data.get("jobs", [])]

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http:
            self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncLeanvox:
    """Async Leanvox client.

    Usage:
        async with AsyncLeanvox(api_key="lv_live_...") as client:
            result = await client.generate(text="Hello world!")
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        auto_async_threshold: int = _DEFAULT_AUTO_ASYNC_THRESHOLD,
    ) -> None:
        self._api_key = resolve_api_key(api_key)
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._auto_async_threshold = auto_async_threshold
        self._http: AsyncHTTPClient | None = None

    def _get_http(self) -> AsyncHTTPClient:
        if self._http is None:
            key = ensure_api_key(self._api_key)
            self._http = AsyncHTTPClient(
                base_url=self._base_url,
                api_key=key,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        return self._http

    async def generate(
        self,
        text: str,
        *,
        model: str = "standard",
        voice: str = "",
        language: str = "en",
        format: str = "mp3",
        speed: float = 1.0,
        exaggeration: float = 0.5,
    ) -> GenerateResult:
        """Generate speech from text (async)."""
        _validate_generate_params(text, model, speed, exaggeration)
        body = _build_generate_body(text, model, voice, language, format, speed, exaggeration)
        data = await self._get_http().request("POST", "/v1/tts/generate", json=body)
        return GenerateResult(
            audio_url=data.get("audio_url", ""),
            model=data.get("model", model),
            voice=data.get("voice", voice),
            characters=data.get("characters", 0),
            cost_cents=data.get("cost_cents", 0),
        )

    async def dialogue(
        self,
        lines: List[Dict[str, Any]],
        *,
        model: str = "pro",
        gap_ms: int = 500,
    ) -> GenerateResult:
        """Generate multi-speaker dialogue (async)."""
        if len(lines) < 2:
            raise InvalidRequestError(
                "Dialogue requires at least 2 lines",
                code="invalid_request", status_code=400,
            )
        body = {"model": model, "lines": lines, "gap_ms": gap_ms}
        data = await self._get_http().request("POST", "/v1/tts/dialogue", json=body)
        return GenerateResult(
            audio_url=data.get("audio_url", ""),
            model=data.get("model", model),
            voice="dialogue",
            characters=data.get("characters", 0),
            cost_cents=data.get("cost_cents", 0),
        )

    async def generate_async(
        self,
        text: str,
        *,
        model: str = "standard",
        voice: str = "",
        language: str = "en",
        format: str = "mp3",
        speed: float = 1.0,
        exaggeration: float = 0.5,
        webhook_url: str = "",
    ) -> Job:
        """Submit async generation job."""
        _validate_generate_params(text, model, speed, exaggeration)
        body = _build_generate_body(text, model, voice, language, format, speed, exaggeration)
        if webhook_url:
            body["webhook_url"] = webhook_url
        data = await self._get_http().request("POST", "/v1/tts/generate-async", json=body)
        return Job(
            id=data.get("id", ""),
            status=data.get("status", "pending"),
            estimated_seconds=data.get("estimated_seconds", 0),
        )

    async def get_job(self, job_id: str) -> Job:
        data = await self._get_http().request("GET", f"/v1/jobs/{job_id}")
        return Job(**{k: v for k, v in data.items() if k in Job.__dataclass_fields__})

    async def list_jobs(self) -> List[Job]:
        data = await self._get_http().request("GET", "/v1/jobs")
        return [Job(**{k: v for k, v in j.items() if k in Job.__dataclass_fields__}) for j in data.get("jobs", [])]

    async def close(self) -> None:
        if self._http:
            await self._http.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


# --- Validation helpers ---

def _validate_generate_params(
    text: str, model: str, speed: float, exaggeration: float
) -> None:
    if not text:
        raise InvalidRequestError(
            "Text cannot be empty", code="invalid_request", status_code=400
        )
    if len(text) > 10_000:
        raise InvalidRequestError(
            f"Text exceeds maximum of 10,000 characters (got {len(text)})",
            code="invalid_request", status_code=400,
        )
    if model not in ("standard", "pro"):
        raise InvalidRequestError(
            f"Model must be 'standard' or 'pro', got '{model}'",
            code="invalid_request", status_code=400,
        )
    if not (0.5 <= speed <= 2.0):
        raise InvalidRequestError(
            f"Speed must be between 0.5 and 2.0, got {speed}",
            code="invalid_request", status_code=400,
        )
    if model == "standard" and exaggeration != 0.5:
        raise InvalidRequestError(
            "exaggeration is only supported on the 'pro' model. "
            "Use model='pro' or remove the exaggeration parameter.",
            code="invalid_request", status_code=400,
        )
    if not (0.0 <= exaggeration <= 1.0):
        raise InvalidRequestError(
            f"Exaggeration must be between 0.0 and 1.0, got {exaggeration}",
            code="invalid_request", status_code=400,
        )


def _build_generate_body(
    text: str,
    model: str,
    voice: str,
    language: str,
    format: str,
    speed: float,
    exaggeration: float,
) -> dict:
    body: dict = {"text": text, "model": model, "language": language, "format": format, "speed": speed}
    if voice:
        body["voice"] = voice
    if model == "pro":
        body["exaggeration"] = exaggeration
    return body
