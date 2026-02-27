# Leanvox Python SDK

Official Python SDK for the [Leanvox](https://leanvox.com) TTS API.

## Install

```bash
pip install leanvox
```

## Quick Start

```python
from leanvox import Leanvox

client = Leanvox(api_key="lv_live_...")
# or set LEANVOX_API_KEY env var

# Generate speech
result = client.generate(text="Hello from Leanvox!", model="standard")
print(result.audio_url)

# Download audio
result.save("hello.mp3")
```

## Streaming

```python
with client.stream(text="Long narration...", voice="af_heart") as stream:
    with open("output.mp3", "wb") as f:
        for chunk in stream:
            f.write(chunk)
```

## Dialogue

```python
result = client.dialogue(
    model="pro",
    lines=[
        {"text": "Welcome to the show!", "voice": "narrator_warm_male", "language": "en"},
        {"text": "Thanks for having me.", "voice": "assistant_pro_female", "language": "en"},
    ],
    gap_ms=500,
)
```

## Async

```python
from leanvox import AsyncLeanvox

async with AsyncLeanvox() as client:
    result = await client.generate(text="Hello async!")
```

## Voice Management

```python
# List voices
voices = client.voices.list(model="pro")

# Clone a voice ($3 to unlock)
voice = client.voices.clone(name="My Voice", audio=open("ref.wav", "rb"))
client.voices.unlock(voice.voice_id)

# Design a voice ($1)
voice = client.voices.design(name="Narrator", prompt="Deep warm male voice")
```

## Error Handling

```python
from leanvox import LeanvoxError, InsufficientBalanceError, RateLimitError

try:
    result = client.generate(text="Hello")
except InsufficientBalanceError as e:
    print(f"Need credits: balance={e.balance_cents}")
except RateLimitError as e:
    print(f"Rate limited, retry after: {e.retry_after}")
except LeanvoxError as e:
    print(f"API error: {e.code} - {e.message}")
```

## Auth Priority

1. Constructor param: `Leanvox(api_key="...")`
2. Environment variable: `LEANVOX_API_KEY`
3. Config file: `~/.lvox/config.toml`

## Requirements

- Python 3.9+
- httpx
