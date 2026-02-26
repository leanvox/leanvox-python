"""Tests for Leanvox sync client — generate(), stream(), dialogue()."""

import pytest
import httpx
import respx

from leanvox import Leanvox, GenerateResult, Job
from leanvox.errors import InvalidRequestError, StreamingFormatError


BASE_URL = "https://api.leanvox.com"
API_KEY = "lv_live_test_key_123"


@pytest.fixture
def client():
    c = Leanvox(api_key=API_KEY, base_url=BASE_URL)
    yield c
    c.close()


class TestGenerate:
    @respx.mock
    def test_generate_basic(self, client):
        respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "https://cdn.leanvox.com/audio/abc.mp3",
                "model": "standard",
                "voice": "af_heart",
                "characters": 12,
                "cost_cents": 0.06,
            })
        )
        result = client.generate("Hello world!", voice="af_heart")
        assert isinstance(result, GenerateResult)
        assert result.audio_url == "https://cdn.leanvox.com/audio/abc.mp3"
        assert result.model == "standard"
        assert result.voice == "af_heart"
        assert result.characters == 12
        assert result.cost_cents == 0.06

    @respx.mock
    def test_generate_sends_correct_body(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "https://cdn.leanvox.com/audio/abc.mp3",
                "model": "pro",
                "voice": "nova",
                "characters": 5,
                "cost_cents": 0.05,
            })
        )
        client.generate(
            "Hello", model="pro", voice="nova", language="en",
            format="wav", speed=1.5, exaggeration=0.8,
        )
        req = route.calls.last.request
        body = req.content
        import json
        payload = json.loads(body)
        assert payload["text"] == "Hello"
        assert payload["model"] == "pro"
        assert payload["voice"] == "nova"
        assert payload["language"] == "en"
        assert payload["format"] == "wav"
        assert payload["speed"] == 1.5
        assert payload["exaggeration"] == 0.8

    @respx.mock
    def test_generate_standard_omits_exaggeration(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            })
        )
        client.generate("Hello")
        import json
        payload = json.loads(route.calls.last.request.content)
        assert "exaggeration" not in payload

    @respx.mock
    def test_generate_omits_empty_voice(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            })
        )
        client.generate("Hello")
        import json
        payload = json.loads(route.calls.last.request.content)
        assert "voice" not in payload

    @respx.mock
    def test_generate_includes_voice_when_set(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "af_heart", "characters": 5, "cost_cents": 0,
            })
        )
        client.generate("Hello", voice="af_heart")
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["voice"] == "af_heart"

    def test_generate_empty_text_raises(self, client):
        with pytest.raises(InvalidRequestError, match="cannot be empty"):
            client.generate("")

    def test_generate_text_too_long_raises(self, client):
        with pytest.raises(InvalidRequestError, match="exceeds maximum"):
            client.generate("x" * 10_001)

    def test_generate_invalid_model_raises(self, client):
        with pytest.raises(InvalidRequestError, match="must be"):
            client.generate("Hello", model="bad")

    def test_generate_speed_out_of_range_raises(self, client):
        with pytest.raises(InvalidRequestError, match="Speed"):
            client.generate("Hello", speed=3.0)

    def test_generate_exaggeration_on_standard_raises(self, client):
        with pytest.raises(InvalidRequestError, match="exaggeration"):
            client.generate("Hello", model="standard", exaggeration=0.8)

    @respx.mock
    def test_generate_auto_async_long_text(self, client):
        """Text exceeding auto_async_threshold should use async path."""
        long_text = "x" * 5001  # exceeds default 5000

        respx.post(f"{BASE_URL}/v1/tts/generate-async").mock(
            return_value=httpx.Response(200, json={
                "id": "job_123", "status": "pending", "estimated_seconds": 10,
            })
        )
        respx.get(f"{BASE_URL}/v1/jobs/job_123").mock(
            return_value=httpx.Response(200, json={
                "id": "job_123", "status": "completed",
                "audio_url": "https://cdn.leanvox.com/audio/done.mp3",
            })
        )
        result = client.generate(long_text, model="pro", exaggeration=0.5)
        assert isinstance(result, GenerateResult)
        assert result.audio_url == "https://cdn.leanvox.com/audio/done.mp3"

    @respx.mock
    def test_generate_sets_auth_header(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            })
        )
        client.generate("Hello")
        assert route.calls.last.request.headers["authorization"] == f"Bearer {API_KEY}"

    @respx.mock
    def test_generate_sets_user_agent(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            })
        )
        client.generate("Hello")
        assert "leanvox-python" in route.calls.last.request.headers["user-agent"]


class TestStream:
    @respx.mock
    def test_stream_yields_chunks(self, client):
        audio_data = b"\xff\xfb\x90\x00" * 1024  # fake MP3 data
        respx.post(f"{BASE_URL}/v1/tts/stream").mock(
            return_value=httpx.Response(200, content=audio_data)
        )
        with client.stream("Hello world!") as chunks:
            collected = b"".join(chunks)
        assert collected == audio_data

    def test_stream_non_mp3_raises(self, client):
        with pytest.raises(StreamingFormatError, match="MP3"):
            with client.stream("Hello", format="wav") as _:
                pass

    @respx.mock
    def test_stream_sends_correct_body(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/stream").mock(
            return_value=httpx.Response(200, content=b"audio")
        )
        with client.stream("Test", voice="nova", model="standard") as chunks:
            _ = b"".join(chunks)
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["text"] == "Test"
        assert payload["format"] == "mp3"


class TestDialogue:
    @respx.mock
    def test_dialogue_basic(self, client):
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
        result = client.dialogue(lines)
        assert isinstance(result, GenerateResult)
        assert result.audio_url == "https://cdn.leanvox.com/audio/dial.mp3"
        assert result.voice == "dialogue"
        assert result.cost_cents == 0.14

    @respx.mock
    def test_dialogue_sends_correct_body(self, client):
        lines = [
            {"voice": "af_heart", "text": "Hello"},
            {"voice": "am_adam", "text": "Hi there"},
        ]
        route = respx.post(f"{BASE_URL}/v1/tts/dialogue").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "pro",
                "characters": 14, "cost_cents": 0,
            })
        )
        client.dialogue(lines, gap_ms=300)
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["model"] == "pro"
        assert payload["gap_ms"] == 300
        assert len(payload["lines"]) == 2

    def test_dialogue_too_few_lines_raises(self, client):
        with pytest.raises(InvalidRequestError, match="at least 2"):
            client.dialogue([{"voice": "af_heart", "text": "solo"}])

    def test_dialogue_empty_lines_raises(self, client):
        with pytest.raises(InvalidRequestError, match="at least 2"):
            client.dialogue([])


class TestAsyncJobs:
    @respx.mock
    def test_generate_async(self, client):
        respx.post(f"{BASE_URL}/v1/tts/generate-async").mock(
            return_value=httpx.Response(200, json={
                "id": "job_abc", "status": "pending",
                "estimated_seconds": 15,
            })
        )
        job = client.generate_async("Hello")
        assert isinstance(job, Job)
        assert job.id == "job_abc"
        assert job.status == "pending"
        assert job.estimated_seconds == 15

    @respx.mock
    def test_generate_async_with_webhook(self, client):
        route = respx.post(f"{BASE_URL}/v1/tts/generate-async").mock(
            return_value=httpx.Response(200, json={
                "id": "job_abc", "status": "pending",
                "estimated_seconds": 5,
            })
        )
        client.generate_async("Hello", webhook_url="https://example.com/hook")
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["webhook_url"] == "https://example.com/hook"

    @respx.mock
    def test_get_job(self, client):
        respx.get(f"{BASE_URL}/v1/jobs/job_xyz").mock(
            return_value=httpx.Response(200, json={
                "id": "job_xyz", "status": "completed",
                "audio_url": "https://cdn.leanvox.com/audio/done.mp3",
            })
        )
        job = client.get_job("job_xyz")
        assert job.status == "completed"
        assert job.audio_url == "https://cdn.leanvox.com/audio/done.mp3"

    @respx.mock
    def test_list_jobs(self, client):
        respx.get(f"{BASE_URL}/v1/jobs").mock(
            return_value=httpx.Response(200, json={
                "jobs": [
                    {"id": "j1", "status": "completed"},
                    {"id": "j2", "status": "pending"},
                ],
            })
        )
        jobs = client.list_jobs()
        assert len(jobs) == 2
        assert jobs[0].id == "j1"
        assert jobs[1].status == "pending"


class TestClientContextManager:
    @respx.mock
    def test_context_manager(self):
        respx.post(f"{BASE_URL}/v1/tts/generate").mock(
            return_value=httpx.Response(200, json={
                "audio_url": "", "model": "standard",
                "voice": "", "characters": 5, "cost_cents": 0,
            })
        )
        with Leanvox(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.generate("Hello")
            assert isinstance(result, GenerateResult)
