# Leanvox SDK Specification

> Interface definitions for official Leanvox SDKs.
> Target languages: Python, Node.js/TypeScript, Go

**Version:** 0.1.0
**Date:** February 25, 2026

---

## 1. Design Principles

1. **Minimal surface area** — one client class, methods map 1:1 to API endpoints
2. **Idiomatic** — follow each language's conventions (snake_case for Python, camelCase for JS, PascalCase for Go)
3. **Sync + async** — Python offers both; Node is async-native; Go is sync with context
4. **Typed** — full type definitions for all requests/responses
5. **Zero dependencies where possible** — only HTTP client + JSON (no heavy frameworks)
6. **Streaming first-class** — stream methods return iterators/readers, not buffered responses

---

## 2. Authentication

All SDKs accept an API key via:
1. Constructor parameter (highest priority)
2. Environment variable `LEANVOX_API_KEY`
3. Config file `~/.lvox/config.toml` (lowest priority)

```python
# Python
client = Leanvox(api_key="lv_live_...")
client = Leanvox()  # reads from env or config

# Node
const client = new Leanvox({ apiKey: "lv_live_..." });
const client = new Leanvox();  // reads from env or config

// Go
client := leanvox.New(leanvox.WithAPIKey("lv_live_..."))
client := leanvox.New()  // reads from env or config
```

---

## 3. Client Interface

### 3.1 Constructor

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `api_key` | string | env/config | API key (`lv_live_` prefix) |
| `base_url` | string | `https://api.leanvox.com` | API base URL |
| `timeout` | float/int | 30 | Request timeout in seconds |
| `max_retries` | int | 2 | Auto-retry on 5xx/network errors |

### 3.2 TTS Methods

#### `generate()`

Generate speech from text. Returns audio URL and metadata.

```python
# Python
result = client.generate(
    text="Hello world!",
    model="standard",        # "standard" | "pro"
    voice="af_heart",        # voice ID
    language="en",           # ISO 639-1
    format="mp3",            # "mp3" | "wav"
    speed=1.0,               # 0.5–2.0
    exaggeration=0.5,        # 0.0–1.0 (pro only)
)
# result.audio_url, result.characters, result.cost_cents, result.model
```

```typescript
// Node.js
const result = await client.generate({
  text: "Hello world!",
  model: "standard",
  voice: "af_heart",
  language: "en",
  format: "mp3",
  speed: 1.0,
  exaggeration: 0.5,
});
// result.audioUrl, result.characters, result.costCents, result.model
```

```go
// Go
result, err := client.Generate(ctx, &leanvox.GenerateRequest{
    Text:         "Hello world!",
    Model:        "standard",
    Voice:        "af_heart",
    Language:     "en",
    Format:       "mp3",
    Speed:        1.0,
    Exaggeration: 0.5,
})
// result.AudioURL, result.Characters, result.CostCents, result.Model
```

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | ✅ | — | Text to synthesize (max 10,000 chars) |
| `model` | string | No | `"standard"` | `"standard"` or `"pro"` |
| `voice` | string | No | model default | Voice ID |
| `language` | string | No | `"en"` | ISO 639-1 language code |
| `format` | string | No | `"mp3"` | `"mp3"` or `"wav"` |
| `speed` | float | No | `1.0` | Playback speed (0.5–2.0) |
| `exaggeration` | float | No | `0.5` | Emotion intensity, pro only (0.0–1.0) |

**Returns:** `GenerateResult`

| Field | Type | Description |
|-------|------|-------------|
| `audio_url` | string | CDN URL to generated audio |
| `model` | string | Model used |
| `voice` | string | Voice used |
| `characters` | int | Character count |
| `cost_cents` | float | Credits charged |

#### `stream()`

Stream audio as it's generated. Returns a byte stream (chunked `audio/mpeg`).

```python
# Python — write to file
with client.stream(text="Hello world!", model="standard") as stream:
    with open("hello.mp3", "wb") as f:
        for chunk in stream:
            f.write(chunk)

# Python — async
async with client.astream(text="Hello world!") as stream:
    async for chunk in stream:
        process(chunk)
```

```typescript
// Node.js — returns ReadableStream
const stream = await client.stream({
  text: "Hello world!",
  model: "standard",
});
const writer = fs.createWriteStream("hello.mp3");
for await (const chunk of stream) {
  writer.write(chunk);
}
writer.end();
```

```go
// Go — returns io.ReadCloser
reader, headers, err := client.Stream(ctx, &leanvox.StreamRequest{
    Text:  "Hello world!",
    Model: "standard",
})
defer reader.Close()
io.Copy(outFile, reader)
// headers: X-Leanvox-Cost-Cents, X-Leanvox-Characters, etc.
```

**Parameters:** Same as `generate()` (except `format` — always MP3 for streaming).

**Response headers available:**

| Header | Description |
|--------|-------------|
| `X-Leanvox-Request-Id` | Unique request ID |
| `X-Leanvox-Cost-Cents` | Credits charged |
| `X-Leanvox-Balance-Cents` | Remaining balance |
| `X-Leanvox-Characters` | Character count |

#### `dialogue()`

Generate multi-speaker dialogue.

```python
# Python
result = client.dialogue(
    model="pro",
    lines=[
        {"text": "Welcome to the show!", "voice": "emma", "language": "en"},
        {"text": "Thanks for having me.", "voice": "james", "language": "en", "exaggeration": 0.6},
    ],
    gap_ms=500,
)
# result.audio_url, result.characters, result.cost_cents
```

```typescript
// Node.js
const result = await client.dialogue({
  model: "pro",
  lines: [
    { text: "Welcome to the show!", voice: "emma", language: "en" },
    { text: "Thanks for having me.", voice: "james", language: "en", exaggeration: 0.6 },
  ],
  gapMs: 500,
});
```

```go
// Go
result, err := client.Dialogue(ctx, &leanvox.DialogueRequest{
    Model: "pro",
    Lines: []leanvox.DialogueLine{
        {Text: "Welcome to the show!", Voice: "emma", Language: "en"},
        {Text: "Thanks for having me.", Voice: "james", Language: "en", Exaggeration: 0.6},
    },
    GapMs: 500,
})
```

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | No | `"pro"` | `"standard"` or `"pro"` |
| `lines` | array | ✅ | — | Array of dialogue lines |
| `lines[].text` | string | ✅ | — | Text for this line |
| `lines[].voice` | string | ✅ | — | Voice ID for this speaker |
| `lines[].language` | string | No | `"en"` | Language |
| `lines[].exaggeration` | float | No | `0.5` | Per-line emotion (pro only) |
| `gap_ms` | int | No | `500` | Silence between speakers (ms) |

### 3.3 Async Jobs

For long text that may take time to process.

#### `generate_async()`

```python
# Python
job = client.generate_async(
    text="Very long text...",
    model="standard",
    voice="af_heart",
    webhook_url="https://yourapp.com/webhook",  # optional
)
# job.id, job.status, job.estimated_seconds

# Poll for completion
result = client.get_job(job.id)
# result.status, result.audio_url (when completed)
```

```typescript
// Node.js
const job = await client.generateAsync({ text: "Very long text...", model: "standard" });
const result = await client.getJob(job.id);
```

```go
// Go
job, err := client.GenerateAsync(ctx, &leanvox.AsyncRequest{Text: "...", Model: "standard"})
result, err := client.GetJob(ctx, job.ID)
```

#### `get_job()` / `list_jobs()`

```python
job = client.get_job("job_id")
jobs = client.list_jobs()
```

### 3.4 Voice Methods

#### `voices.list()`

```python
voices = client.voices.list(model="standard")  # or "pro" or None for all
# voices.standard_voices, voices.pro_voices, voices.cloned_voices
```

#### `voices.list_curated()`

```python
curated = client.voices.list_curated()
# Returns 14 curated Pro voices with preview URLs
```

#### `voices.clone()`

```python
voice = client.voices.clone(
    name="My Voice",
    audio=open("reference.wav", "rb"),  # or base64 string
    description="Optional description",
)
# voice.voice_id, voice.status ("pending_unlock"), voice.unlock_cost_cents
```

#### `voices.unlock()`

```python
result = client.voices.unlock("voice_id")
# result.unlocked = True, result.balance_cents
```

**Cost:** $3.00 per voice unlock.

#### `voices.design()`

```python
voice = client.voices.design(
    name="Deep Narrator",
    prompt="A deep, warm male voice with a gentle storytelling tone",
    language="English",       # optional
    description="For audiobook narration",  # optional
)
# voice.id, voice.status, voice.cost_cents
```

**Cost:** $1.00 per voice design.

#### `voices.list_designs()`

```python
designs = client.voices.list_designs()
```

#### `voices.delete()`

```python
client.voices.delete("voice_id")
```

### 3.5 File Methods

#### `files.extract_text()`

```python
result = client.files.extract_text(open("book.epub", "rb"))
# result.text, result.filename, result.char_count, result.truncated
```

**Supported:** `.txt`, `.epub` — Max 5 MB, returns up to 500,000 characters.

### 3.6 Generation History

#### `generations.list()`

```python
gens = client.generations.list(limit=20, offset=0)
# gens.generations, gens.total
```

#### `generations.get_audio()`

```python
audio = client.generations.get_audio("generation_id")
# audio.audio_url (presigned, valid 1 hour)
```

#### `generations.delete()`

```python
client.generations.delete("generation_id")
```

### 3.7 Account Methods

#### `account.balance()`

```python
balance = client.account.balance()
# balance.balance_cents, balance.total_spent_cents
```

#### `account.usage()`

```python
usage = client.account.usage(days=30, model="standard", limit=100)
```

#### `account.buy_credits()`

```python
checkout = client.account.buy_credits(amount_cents=2000)
# checkout.payment_url (Stripe checkout URL)
```

---

## 4. Error Handling

All SDKs raise typed exceptions mapping to API error codes:

```python
# Python
from leanvox import LeanvoxError, InsufficientBalanceError, RateLimitError

try:
    result = client.generate(text="Hello")
except InsufficientBalanceError as e:
    print(f"Need more credits: balance={e.balance_cents}")
except RateLimitError as e:
    print(f"Rate limited, retry after: {e.retry_after}")
except LeanvoxError as e:
    print(f"API error: {e.code} - {e.message}")
```

```typescript
// Node.js
import { LeanvoxError, InsufficientBalanceError } from "leanvox";

try {
  const result = await client.generate({ text: "Hello" });
} catch (e) {
  if (e instanceof InsufficientBalanceError) {
    console.log(`Need credits: ${e.balanceCents}`);
  }
}
```

```go
// Go
result, err := client.Generate(ctx, req)
if errors.Is(err, leanvox.ErrInsufficientBalance) {
    // handle
}
var apiErr *leanvox.APIError
if errors.As(err, &apiErr) {
    fmt.Println(apiErr.Code, apiErr.Message)
}
```

**Error types:**

| Exception | HTTP | Code | Description |
|-----------|------|------|-------------|
| `InvalidRequestError` | 400 | `invalid_request` | Bad parameters |
| `AuthenticationError` | 401 | `invalid_api_key` | Invalid API key |
| `InsufficientBalanceError` | 402 | `insufficient_balance` | Not enough credits |
| `NotFoundError` | 404 | `not_found` | Resource not found |
| `RateLimitError` | 429 | `rate_limit_exceeded` | Too many requests |
| `ServerError` | 500 | `server_error` | Internal error |

---

## 5. Retry & Timeout Behavior

| Behavior | Default | Configurable |
|----------|---------|-------------|
| Timeout | 30s (120s for async/stream) | ✅ via constructor |
| Retries | 2 retries on 5xx / network | ✅ `max_retries` |
| Backoff | Exponential (1s, 2s, 4s) | No |
| Retry on 429 | Yes, respects `Retry-After` | ✅ |
| Retry on 4xx | No (except 429) | No |

---

## 6. Package Names & Distribution

| Language | Package Name | Install | Import |
|----------|-------------|---------|--------|
| Python | `leanvox` | `pip install leanvox` | `from leanvox import Leanvox` |
| Node.js | `leanvox` | `npm install leanvox` | `import { Leanvox } from "leanvox"` |
| Go | `github.com/leanvox/leanvox-go` | `go get github.com/leanvox/leanvox-go` | `import "github.com/leanvox/leanvox-go"` |

---

## 7. Quick Start Examples

### Python — Generate and play
```python
from leanvox import Leanvox

client = Leanvox()
result = client.generate(text="Hello from Leanvox!", model="standard")
print(result.audio_url)
```

### Python — Stream to file
```python
with client.stream(text="Long narration...", voice="af_heart") as stream:
    with open("output.mp3", "wb") as f:
        for chunk in stream:
            f.write(chunk)
```

### Python — Voice clone + generate
```python
voice = client.voices.clone(name="My Voice", audio=open("ref.wav", "rb"))
client.voices.unlock(voice.voice_id)
result = client.generate(text="Hello in my voice!", model="pro", voice=voice.voice_id)
```

### Node.js — Dialogue
```typescript
const result = await client.dialogue({
  model: "pro",
  lines: [
    { text: "Hey, welcome!", voice: "emma" },
    { text: "Thanks! Great to be here.", voice: "james" },
  ],
});
console.log(result.audioUrl);
```

---

*SDK Spec v0.1.0 — February 25, 2026*
*Priority: Python first, then Node.js, then Go.*
