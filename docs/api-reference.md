# API Reference — Leanvox Python SDK

> `leanvox` v0.1.0 — Full method reference for the Python SDK.

---

## Client

### `Leanvox()`

Create a sync client.

```python
from leanvox import Leanvox

client = Leanvox(
    api_key="lv_live_...",       # or LEANVOX_API_KEY env var
    base_url="https://api.leanvox.com",
    timeout=30,                   # seconds
    max_retries=2,                # retries on 5xx/network errors
    auto_async_threshold=5000,    # chars before auto-async routing
)
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `api_key` | `str \| None` | env/config | API key (`lv_live_` prefix) |
| `base_url` | `str` | `https://api.leanvox.com` | API base URL |
| `timeout` | `float` | `30` | Request timeout (seconds) |
| `max_retries` | `int` | `2` | Auto-retry on 5xx/network errors |
| `auto_async_threshold` | `int` | `5000` | Character count to auto-route to async |

**Auth resolution order:** Constructor → `LEANVOX_API_KEY` env → `~/.lvox/config.toml`

Supports context manager:
```python
with Leanvox() as client:
    result = client.generate(text="Hello!")
```

### `AsyncLeanvox()`

Async equivalent. Same parameters. Use with `async with`:

```python
from leanvox import AsyncLeanvox

async with AsyncLeanvox() as client:
    result = await client.generate(text="Hello!")
```

---

## TTS Methods

### `client.generate()`

Generate speech from text. Returns `GenerateResult`.

```python
result = client.generate(
    text="Hello world!",
    model="standard",
    voice="af_heart",
    language="en",
    format="mp3",
    speed=1.0,
    exaggeration=0.5,
)
```

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | `str` | ✅ | — | Text to synthesize (max 10,000 chars) |
| `model` | `str` | — | `"standard"` | `"standard"` or `"pro"` |
| `voice` | `str` | — | model default | Voice ID |
| `language` | `str` | — | `"en"` | ISO 639-1 language code |
| `format` | `str` | — | `"mp3"` | `"mp3"` or `"wav"` |
| `speed` | `float` | — | `1.0` | Playback speed (0.5–2.0) |
| `exaggeration` | `float` | — | `0.5` | Emotion intensity, **pro only** (0.0–1.0) |

> ⚠️ Passing `exaggeration` with `model="standard"` raises `InvalidRequestError`.
> Text over `auto_async_threshold` chars is automatically routed to async processing.

**Returns: `GenerateResult`**

| Field | Type | Description |
|-------|------|-------------|
| `audio_url` | `str` | CDN URL to generated audio |
| `model` | `str` | Model used |
| `voice` | `str` | Voice used |
| `characters` | `int` | Character count |
| `cost_cents` | `float` | Credits charged |

```python
result.save("output.mp3")      # Download and save to file
data = result.download()        # Download as bytes
```

---

### `client.stream()`

Stream audio as byte chunks. Context manager yielding an iterator.

```python
with client.stream(text="Hello!", model="standard") as stream:
    with open("out.mp3", "wb") as f:
        for chunk in stream:
            f.write(chunk)
```

Parameters: Same as `generate()` except **format is always MP3**.

> Passing `format="wav"` raises `StreamingFormatError`.

---

### `client.dialogue()`

Generate multi-speaker dialogue. Returns `GenerateResult`.

```python
result = client.dialogue(
    lines=[
        {"text": "Hello!", "voice": "emma", "language": "en"},
        {"text": "Hi there!", "voice": "james", "exaggeration": 0.7},
    ],
    model="pro",
    gap_ms=500,
)
```

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `lines` | `list[dict]` | ✅ | — | Dialogue lines (min 2) |
| `lines[].text` | `str` | ✅ | — | Line text |
| `lines[].voice` | `str` | ✅ | — | Voice ID |
| `lines[].language` | `str` | — | `"en"` | Language |
| `lines[].exaggeration` | `float` | — | `0.5` | Per-line emotion (pro only) |
| `model` | `str` | — | `"pro"` | Model |
| `gap_ms` | `int` | — | `500` | Silence between speakers (ms) |

---

### `client.generate_async()`

Submit a long-text generation as an async job. Returns `Job`.

```python
job = client.generate_async(
    text="Very long text...",
    webhook_url="https://yourapp.com/hook",  # optional
)
print(job.id, job.status, job.estimated_seconds)
```

### `client.get_job(job_id)`

Poll an async job's status. Returns `Job`.

```python
job = client.get_job("job_abc123")
# job.status: "pending" | "processing" | "completed" | "failed"
# job.audio_url: available when completed
```

### `client.list_jobs()`

List all async jobs. Returns `list[Job]`.

---

## Voice Methods

Accessed via `client.voices.*`

### `client.voices.list(model=None)`

List available voices. Optional filter by model.

```python
voices = client.voices.list(model="pro")
```

Returns `VoiceList` with `.standard_voices`, `.pro_voices`, `.cloned_voices`.

### `client.voices.list_curated()`

List 14 curated Pro voices with preview URLs.

### `client.voices.clone(name, audio, description="")`

Clone a voice from reference audio.

```python
voice = client.voices.clone(
    name="My Voice",
    audio=open("reference.wav", "rb"),  # file object or base64
    description="Optional description",
)
# voice.voice_id, voice.status ("pending_unlock")
```

### `client.voices.unlock(voice_id)`

Unlock a cloned voice. **Cost: $3.00.**

```python
result = client.voices.unlock("voice_abc123")
# result.unlocked, result.balance_cents
```

### `client.voices.design(name, prompt, language="", description="")`

Create a voice from a text description. **Cost: $1.00.**

```python
voice = client.voices.design(
    name="Narrator",
    prompt="A deep, warm male voice with gentle storytelling tone",
)
```

### `client.voices.list_designs()`

List all designed voices.

### `client.voices.delete(voice_id)`

Delete a voice.

---

## File Methods

### `client.files.extract_text(file)`

Extract text from `.txt` or `.epub` files (max 5 MB, 500K chars).

```python
result = client.files.extract_text(open("book.epub", "rb"))
# result.text, result.filename, result.char_count, result.truncated
```

---

## Generation History

### `client.generations.list(limit=20, offset=0)`

List past generations.

### `client.generations.get_audio(generation_id)`

Get audio URL for a past generation (presigned, valid 1 hour).

### `client.generations.delete(generation_id)`

Delete a generation.

---

## Account Methods

### `client.account.balance()`

```python
balance = client.account.balance()
# balance.balance_cents, balance.total_spent_cents
```

### `client.account.usage(days=30, model=None, limit=100)`

Get usage history.

### `client.account.buy_credits(amount_cents)`

Returns a Stripe checkout URL.

```python
checkout = client.account.buy_credits(amount_cents=2000)
# checkout.payment_url → redirect user here
```

---

## Errors

All errors inherit from `LeanvoxError`.

```python
from leanvox import (
    LeanvoxError,
    InvalidRequestError,
    AuthenticationError,
    InsufficientBalanceError,
    NotFoundError,
    RateLimitError,
    ServerError,
    StreamingFormatError,
)
```

| Exception | HTTP | Code | When |
|-----------|------|------|------|
| `InvalidRequestError` | 400 | `invalid_request` | Bad params, empty text, wrong model |
| `AuthenticationError` | 401 | `invalid_api_key` | Missing/invalid API key |
| `InsufficientBalanceError` | 402 | `insufficient_balance` | Not enough credits |
| `NotFoundError` | 404 | `not_found` | Resource doesn't exist |
| `RateLimitError` | 429 | `rate_limit_exceeded` | Too many requests |
| `ServerError` | 500 | `server_error` | Internal error |
| `StreamingFormatError` | 400 | `streaming_format_error` | Non-MP3 format in `stream()` |

All errors have: `.message`, `.code`, `.status_code`
`RateLimitError` also has: `.retry_after` (seconds)
`InsufficientBalanceError` also has: `.balance_cents`

---

## Retry Behavior

| Behavior | Default | Configurable |
|----------|---------|-------------|
| Timeout | 30s (120s for async/stream) | ✅ `timeout` |
| Retries | 2 on 5xx/network errors | ✅ `max_retries` |
| Backoff | Exponential (1s, 2s, 4s) | No |
| 429 handling | Respects `Retry-After` header | ✅ |
| 4xx retry | No (except 429) | No |

---

*Leanvox Python SDK v0.1.0*
