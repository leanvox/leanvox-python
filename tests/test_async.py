"""Tests for AsyncLeanvox client methods."""

from unittest.mock import patch

import httpx
import pytest
import respx

from leanvox import AsyncLeanvox, GenerateResult, Job
from leanvox.errors import (
    InvalidRequestError,
    RateLimitError,
    ServerError,
)

BASE_URL = "https://api.leanvox.com"
API_KEY = "lv_live_test_key_123"


@pytest.fixture
def client():
    return AsyncLeanvox(api_key=API_KEY, base_url=BASE_URL)


class TestAsyncGenerate:
    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_basic(self, client):
        respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "https://cdn.leanvox.com/audio/abc.mp3",
                "model": "standard",
                "voice": "af_heart",
                "characters": 12,
                "cost_cents": 0.06,
            })
        )
        result = await client.generate("Hello world!", voice="af_heart")
        assert isinstance(result, GenerateResult)
        assert result.audio_url == "https://cdn.leanvox.com/audio/abc.mp3"
        assert result.model == "standard"
        assert result.voice == "af_heart"
        assert result.characters == 12

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_pro_with_exaggeration(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "pro",
                "voice": "nova", "characters": 5, "cost_cents": 0.05,
            })
        )
        await client.generate("Hello", model="pro", voice="nova", exaggeration=0.7)
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["model"] == "pro"
        assert payload["exaggeration"] == 0.7

    @pytest.mark.asyncio
    async def test_generate_validation_empty_text(self, client):
        with pytest.raises(InvalidRequestError, match="cannot be empty"):
            await client.generate("")

    @pytest.mark.asyncio
    async def test_generate_validation_invalid_model(self, client):
        with pytest.raises(InvalidRequestError, match="must be"):
            await client.generate("Hello", model="bad")

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_sets_auth_header(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            })
        )
        await client.generate("Hello")
        assert route.calls.last.request.headers["authorization"] == f"Bearer {API_KEY}"


class TestAsyncDialogue:
    @respx.mock
    @pytest.mark.asyncio
    async def test_dialogue_basic(self, client):
        lines = [
            {"voice": "af_heart", "text": "Hello"},
            {"voice": "am_adam", "text": "Hi there"},
        ]
        respx.post(f"{BASE_URL}/v1/tts/dialogue").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "https://cdn.leanvox.com/audio/dial.mp3",
                "model": "pro",
                "characters": 14,
                "cost_cents": 0.14,
            })
        )
        result = await client.dialogue(lines)
        assert isinstance(result, GenerateResult)
        assert result.voice == "dialogue"
        assert result.cost_cents == 0.14

    @respx.mock
    @pytest.mark.asyncio
    async def test_dialogue_sends_correct_body(self, client):
        lines = [
            {"voice": "af_heart", "text": "Line 1"},
            {"voice": "am_adam", "text": "Line 2"},
        ]
        route = respx.post(f"{BASE_URL}/v1/tts/dialogue").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "pro",
                "characters": 0, "cost_cents": 0,
            })
        )
        await client.dialogue(lines, gap_ms=250)
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["gap_ms"] == 250
        assert len(payload["lines"]) == 2

    @pytest.mark.asyncio
    async def test_dialogue_too_few_lines(self, client):
        with pytest.raises(InvalidRequestError, match="at least 2"):
            await client.dialogue([{"voice": "af", "text": "solo"}])


class TestAsyncJobs:
    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_async(self, client):
        respx.post(f"{BASE_URL}/v1/tts/generate-async").mock(
            return_value=httpx.Response(200, json={
                "id": "job_abc", "status": "pending",
                "estimated_seconds": 10,
            })
        )
        job = await client.generate_async("Hello")
        assert isinstance(job, Job)
        assert job.id == "job_abc"
        assert job.status == "pending"

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_async_with_webhook(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate-async").mock(
            return_value=httpx.Response(200, json={
                "id": "job_abc", "status": "pending",
                "estimated_seconds": 5,
            })
        )
        await client.generate_async("Hello", webhook_url="https://example.com/hook")
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["webhook_url"] == "https://example.com/hook"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_job(self, client):
        respx.get(f"{BASE_URL}/v1/jobs/job_xyz").mock(
            return_value=httpx.Response(200, json={
                "id": "job_xyz", "status": "completed",
                "audio_url": "https://cdn.leanvox.com/audio/done.mp3",
            })
        )
        job = await client.get_job("job_xyz")
        assert job.status == "completed"
        assert job.audio_url == "https://cdn.leanvox.com/audio/done.mp3"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_jobs(self, client):
        respx.get(f"{BASE_URL}/v1/jobs").mock(
            return_value=httpx.Response(200, json={
                "jobs": [
                    {"id": "j1", "status": "completed"},
                    {"id": "j2", "status": "failed", "error": "timeout"},
                ],
            })
        )
        jobs = await client.list_jobs()
        assert len(jobs) == 2
        assert jobs[1].error == "timeout"


class TestAsyncRetry:
    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_on_500(self):
        async with AsyncLeanvox(api_key=API_KEY, base_url=BASE_URL, max_retries=2) as client:
            route = respx.post(f"{BASE_URL}/v1/tts/generate")
            route.side_effect = [
                httpx.Response(500, json={"error": {"message": "err"}}),
                httpx.Response(200, json={
                    "audio_url": "https://cdn.leanvox.com/ok.mp3",
                    "model": "standard", "voice": "", "characters": 5, "cost_cents": 0,
                }),
            ]
            with patch("asyncio.sleep", return_value=None):
                result = await client.generate("Hello")
            assert result.audio_url == "https://cdn.leanvox.com/ok.mp3"
            assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_on_429_with_retry_after(self):
        async with AsyncLeanvox(api_key=API_KEY, base_url=BASE_URL, max_retries=1) as client:
            route = respx.post(f"{BASE_URL}/v1/tts/generate")
            route.side_effect = [
                httpx.Response(
                    429,
                    json={"error": {"message": "Rate limited", "code": "rate_limit"}},
                    headers={"Retry-After": "2.0"},
                ),
                httpx.Response(200, json={
                    "audio_url": "", "model": "standard",
                    "voice": "", "characters": 5, "cost_cents": 0,
                }),
            ]
            sleep_calls = []

            async def mock_sleep(t):
                sleep_calls.append(t)

            with patch("asyncio.sleep", side_effect=mock_sleep):
                await client.generate("Hello")
            assert sleep_calls[0] == 2.0

    @respx.mock
    @pytest.mark.asyncio
    async def test_exhausts_retries_raises(self):
        async with AsyncLeanvox(api_key=API_KEY, base_url=BASE_URL, max_retries=1) as client:
            respx.post(f"{BASE_URL}/v1/tts/generate").mock(
                return_value=httpx.Response(500, json={"error": {"message": "down"}})
            )
            with patch("asyncio.sleep", return_value=None):
                with pytest.raises(ServerError, match="down"):
                    await client.generate("Hello")

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self):
        async with AsyncLeanvox(api_key=API_KEY, base_url=BASE_URL, max_retries=2) as client:
            route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
                return_value=httpx.Response(401, json={
                    "error": {"message": "Unauthorized", "code": "auth_error"},
                })
            )
            with pytest.raises(Exception):
                await client.generate("Hello")
            assert route.call_count == 1


class TestAsyncContextManager:
    @respx.mock
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            })
        )
        async with AsyncLeanvox(api_key=API_KEY, base_url=BASE_URL) as client:
            result = await client.generate("Hello")
            assert isinstance(result, GenerateResult)
