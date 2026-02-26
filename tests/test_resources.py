"""Tests for resource classes — voices, files, generations, account."""

import io
import json

import httpx
import pytest
import respx

from leanvox import (
    Leanvox,
    AccountBalance,
    AccountUsage,
    FileExtractResult,
    Generation,
    GenerationList,
    Voice,
    VoiceDesign,
    VoiceList,
)

BASE_URL = "https://api.leanvox.com"
API_KEY = "lv_live_test_key_123"


@pytest.fixture
def client():
    c = Leanvox(api_key=API_KEY, base_url=BASE_URL)
    yield c
    c.close()


class TestVoicesList:
    @respx.mock
    def test_list_all_voices(self, client):
        respx.get(f"{BASE_URL}/v1/voices").mock(
            return_value=httpx.Response(200, json={
                "standard_voices": [
                    {"voice_id": "af_heart", "name": "Heart", "model": "standard", "language": "en"},
                ],
                "pro_voices": [
                    {"voice_id": "nova", "name": "Nova", "model": "pro", "language": "en"},
                ],
                "cloned_voices": [],
            })
        )
        result = client.voices.list()
        assert isinstance(result, VoiceList)
        assert len(result.standard_voices) == 1
        assert len(result.pro_voices) == 1
        assert len(result.cloned_voices) == 0
        assert result.standard_voices[0].voice_id == "af_heart"
        assert result.pro_voices[0].name == "Nova"

    @respx.mock
    def test_list_voices_with_model_filter(self, client):
        route = respx.get(f"{BASE_URL}/v1/voices").mock(
            return_value=httpx.Response(200, json={
                "standard_voices": [
                    {"voice_id": "af_heart", "name": "Heart"},
                ],
                "pro_voices": [],
                "cloned_voices": [],
            })
        )
        client.voices.list(model="standard")
        assert route.calls.last.request.url.params["model"] == "standard"

    @respx.mock
    def test_list_curated(self, client):
        respx.get(f"{BASE_URL}/v1/voices/curated").mock(
            return_value=httpx.Response(200, json={
                "voices": [
                    {"voice_id": "nova", "name": "Nova", "model": "pro",
                     "preview_url": "https://cdn.leanvox.com/preview/nova.mp3"},
                ],
            })
        )
        voices = client.voices.list_curated()
        assert len(voices) == 1
        assert voices[0].preview_url == "https://cdn.leanvox.com/preview/nova.mp3"


class TestVoicesClone:
    @respx.mock
    def test_clone_with_base64(self, client):
        route = respx.post(f"{BASE_URL}/v1/voices/clone").mock(
            return_value=httpx.Response(200, json={
                "voice_id": "cloned_abc",
                "name": "My Voice",
                "model": "pro",
                "status": "pending_unlock",
            })
        )
        voice = client.voices.clone("My Voice", "base64audiodatahere==")
        assert isinstance(voice, Voice)
        assert voice.voice_id == "cloned_abc"
        assert voice.status == "pending_unlock"
        payload = json.loads(route.calls.last.request.content)
        assert payload["name"] == "My Voice"
        assert payload["audio_base64"] == "base64audiodatahere=="

    @respx.mock
    def test_clone_with_file_upload(self, client):
        respx.post(f"{BASE_URL}/v1/voices/clone").mock(
            return_value=httpx.Response(200, json={
                "voice_id": "cloned_def",
                "name": "Uploaded Voice",
                "model": "pro",
                "status": "pending_unlock",
            })
        )
        audio_file = io.BytesIO(b"fake wav data")
        voice = client.voices.clone("Uploaded Voice", audio_file)
        assert voice.voice_id == "cloned_def"

    @respx.mock
    def test_clone_auto_unlock(self, client):
        respx.post(f"{BASE_URL}/v1/voices/clone").mock(
            return_value=httpx.Response(200, json={
                "voice_id": "cloned_ghi",
                "name": "Auto Unlock",
                "model": "pro",
                "status": "pending_unlock",
            })
        )
        respx.post(f"{BASE_URL}/v1/voices/cloned_ghi/unlock").mock(
            return_value=httpx.Response(200, json={"status": "active"})
        )
        voice = client.voices.clone("Auto Unlock", "base64data==", auto_unlock=True)
        assert voice.status == "active"

    @respx.mock
    def test_clone_no_auto_unlock_if_already_active(self, client):
        respx.post(f"{BASE_URL}/v1/voices/clone").mock(
            return_value=httpx.Response(200, json={
                "voice_id": "cloned_jkl",
                "name": "Already Active",
                "model": "pro",
                "status": "active",
            })
        )
        # unlock should not be called
        unlock_route = respx.post(f"{BASE_URL}/v1/voices/cloned_jkl/unlock").mock(
            return_value=httpx.Response(200, json={})
        )
        voice = client.voices.clone("Already Active", "base64data==", auto_unlock=True)
        assert voice.status == "active"
        assert not unlock_route.called


class TestVoicesDesign:
    @respx.mock
    def test_design_voice(self, client):
        route = respx.post(f"{BASE_URL}/v1/voices/design").mock(
            return_value=httpx.Response(200, json={
                "id": "design_123",
                "name": "Warm Narrator",
                "status": "processing",
                "cost_cents": 100,
            })
        )
        design = client.voices.design("Warm Narrator", "A warm, friendly male narrator")
        assert isinstance(design, VoiceDesign)
        assert design.id == "design_123"
        assert design.cost_cents == 100
        payload = json.loads(route.calls.last.request.content)
        assert payload["name"] == "Warm Narrator"
        assert payload["prompt"] == "A warm, friendly male narrator"
        assert "language" not in payload
        assert "description" not in payload

    @respx.mock
    def test_design_voice_with_optional_params(self, client):
        route = respx.post(f"{BASE_URL}/v1/voices/design").mock(
            return_value=httpx.Response(200, json={
                "id": "design_456", "name": "Test", "status": "processing",
            })
        )
        client.voices.design("Test", "prompt", language="fr", description="French voice")
        payload = json.loads(route.calls.last.request.content)
        assert payload["language"] == "fr"
        assert payload["description"] == "French voice"

    @respx.mock
    def test_list_designs(self, client):
        respx.get(f"{BASE_URL}/v1/voices/designs").mock(
            return_value=httpx.Response(200, json={
                "designs": [
                    {"id": "d1", "name": "Voice A", "status": "completed"},
                    {"id": "d2", "name": "Voice B", "status": "processing"},
                ],
            })
        )
        designs = client.voices.list_designs()
        assert len(designs) == 2
        assert designs[0].name == "Voice A"
        assert designs[1].status == "processing"


class TestVoicesDelete:
    @respx.mock
    def test_delete_voice(self, client):
        route = respx.delete(f"{BASE_URL}/v1/voices/voice_abc").mock(
            return_value=httpx.Response(204)
        )
        client.voices.delete("voice_abc")
        assert route.called

    @respx.mock
    def test_unlock_voice(self, client):
        respx.post(f"{BASE_URL}/v1/voices/voice_abc/unlock").mock(
            return_value=httpx.Response(200, json={"status": "active"})
        )
        result = client.voices.unlock("voice_abc")
        assert result["status"] == "active"


class TestFilesResource:
    @respx.mock
    def test_extract_text(self, client):
        respx.post(f"{BASE_URL}/v1/files/extract-text").mock(
            return_value=httpx.Response(200, json={
                "text": "Chapter 1: The Beginning",
                "filename": "book.epub",
                "char_count": 24,
                "truncated": False,
            })
        )
        file = io.BytesIO(b"fake epub content")
        file.name = "book.epub"
        result = client.files.extract_text(file)
        assert isinstance(result, FileExtractResult)
        assert result.text == "Chapter 1: The Beginning"
        assert result.filename == "book.epub"
        assert result.char_count == 24
        assert result.truncated is False

    @respx.mock
    def test_extract_text_truncated(self, client):
        respx.post(f"{BASE_URL}/v1/files/extract-text").mock(
            return_value=httpx.Response(200, json={
                "text": "Truncated content...",
                "filename": "big.txt",
                "char_count": 10000,
                "truncated": True,
            })
        )
        file = io.BytesIO(b"big content")
        result = client.files.extract_text(file)
        assert result.truncated is True


class TestGenerationsResource:
    @respx.mock
    def test_list_generations(self, client):
        respx.get(f"{BASE_URL}/v1/generations").mock(
            return_value=httpx.Response(200, json={
                "generations": [
                    {"id": "gen_1", "model": "standard", "voice": "af_heart",
                     "characters": 100, "cost_cents": 0.5, "audio_url": "https://cdn.leanvox.com/a.mp3"},
                    {"id": "gen_2", "model": "pro", "voice": "nova",
                     "characters": 200, "cost_cents": 2.0, "audio_url": "https://cdn.leanvox.com/b.mp3"},
                ],
                "total": 42,
            })
        )
        result = client.generations.list()
        assert isinstance(result, GenerationList)
        assert result.total == 42
        assert len(result.generations) == 2
        assert result.generations[0].id == "gen_1"
        assert result.generations[1].cost_cents == 2.0

    @respx.mock
    def test_list_generations_pagination(self, client):
        route = respx.get(f"{BASE_URL}/v1/generations").mock(
            return_value=httpx.Response(200, json={
                "generations": [], "total": 0,
            })
        )
        client.generations.list(limit=10, offset=20)
        params = route.calls.last.request.url.params
        assert params["limit"] == "10"
        assert params["offset"] == "20"

    @respx.mock
    def test_get_audio(self, client):
        respx.get(f"{BASE_URL}/v1/generations/gen_abc/audio").mock(
            return_value=httpx.Response(200, json={
                "id": "gen_abc",
                "audio_url": "https://cdn.leanvox.com/audio/gen_abc.mp3",
                "model": "standard",
            })
        )
        gen = client.generations.get_audio("gen_abc")
        assert isinstance(gen, Generation)
        assert gen.audio_url == "https://cdn.leanvox.com/audio/gen_abc.mp3"

    @respx.mock
    def test_delete_generation(self, client):
        route = respx.delete(f"{BASE_URL}/v1/generations/gen_del").mock(
            return_value=httpx.Response(204)
        )
        client.generations.delete("gen_del")
        assert route.called


class TestAccountResource:
    @respx.mock
    def test_balance(self, client):
        respx.get(f"{BASE_URL}/v1/account/balance").mock(
            return_value=httpx.Response(200, json={
                "balance_cents": 4500,
                "total_spent_cents": 1250,
            })
        )
        balance = client.account.balance()
        assert isinstance(balance, AccountBalance)
        assert balance.balance_cents == 4500
        assert balance.total_spent_cents == 1250

    @respx.mock
    def test_usage(self, client):
        respx.get(f"{BASE_URL}/v1/account/usage").mock(
            return_value=httpx.Response(200, json={
                "entries": [
                    {"date": "2025-01-15", "characters": 5000, "cost_cents": 25},
                    {"date": "2025-01-14", "characters": 3000, "cost_cents": 15},
                ],
            })
        )
        usage = client.account.usage()
        assert isinstance(usage, AccountUsage)
        assert len(usage.entries) == 2
        assert usage.entries[0]["characters"] == 5000

    @respx.mock
    def test_usage_with_filters(self, client):
        route = respx.get(f"{BASE_URL}/v1/account/usage").mock(
            return_value=httpx.Response(200, json={"entries": []})
        )
        client.account.usage(days=7, model="pro", limit=50)
        params = route.calls.last.request.url.params
        assert params["days"] == "7"
        assert params["model"] == "pro"
        assert params["limit"] == "50"

    @respx.mock
    def test_buy_credits(self, client):
        respx.post(f"{BASE_URL}/v1/billing/checkout").mock(
            return_value=httpx.Response(200, json={
                "checkout_url": "https://checkout.stripe.com/session_abc",
            })
        )
        result = client.account.buy_credits(2000)
        assert result["checkout_url"] == "https://checkout.stripe.com/session_abc"

    @respx.mock
    def test_buy_credits_sends_amount(self, client):
        route = respx.post(f"{BASE_URL}/v1/billing/checkout").mock(
            return_value=httpx.Response(200, json={"checkout_url": ""})
        )
        client.account.buy_credits(5000)
        payload = json.loads(route.calls.last.request.content)
        assert payload["amount_cents"] == 5000
