"""Leanvox response types."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class GenerateResult:
    """Result from generate() or dialogue()."""

    audio_url: str
    model: str
    voice: str
    characters: int
    cost_cents: float
    generated_voice_id: str | None = None
    suggestion: str | None = None
    _http_client: Any = field(default=None, repr=False)

    def download(self) -> bytes:
        """Download audio bytes from the CDN URL."""
        if self._http_client is None:
            import httpx
            resp = httpx.get(self.audio_url)
            resp.raise_for_status()
            return resp.content
        resp = self._http_client.get(self.audio_url)
        resp.raise_for_status()
        return resp.content

    def save(self, path: str | os.PathLike) -> None:
        """Download and save audio to a file."""
        data = self.download()
        with open(path, "wb") as f:
            f.write(data)


@dataclass
class Voice:
    """A voice resource."""

    voice_id: str
    name: str
    model: str = "standard"
    language: str = "en"
    status: str = "active"
    description: str = ""
    preview_url: str = ""
    unlock_cost_cents: float = 0


@dataclass
class VoiceList:
    """Grouped voice listing."""

    standard_voices: List[Voice] = field(default_factory=list)
    pro_voices: List[Voice] = field(default_factory=list)
    cloned_voices: List[Voice] = field(default_factory=list)


@dataclass
class Job:
    """An async generation job."""

    id: str
    status: str  # pending, processing, completed, failed
    estimated_seconds: float = 0
    audio_url: str = ""
    error: str = ""


@dataclass
class FileExtractResult:
    """Result from file text extraction."""

    text: str
    filename: str
    char_count: int
    truncated: bool = False


@dataclass
class Generation:
    """A historical generation."""

    id: str
    audio_url: str = ""
    model: str = ""
    voice: str = ""
    characters: int = 0
    cost_cents: float = 0
    created_at: str = ""


@dataclass
class GenerationList:
    """Paginated generation listing."""

    generations: List[Generation] = field(default_factory=list)
    total: int = 0


@dataclass
class AccountBalance:
    """Account balance info."""

    balance_cents: float
    total_spent_cents: float


@dataclass
class AccountUsage:
    """Account usage data."""

    entries: List[dict] = field(default_factory=list)


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio."""
    start: float
    end: float
    text: str
    confidence: Optional[float] = None
    speaker: Optional[str] = None


@dataclass
class TranscriptData:
    """Transcript with segments."""
    text: str
    segments: List[TranscriptSegment] = field(default_factory=list)


@dataclass
class SpeakersData:
    """Speaker diarization results."""
    count: int
    labels: List[str] = field(default_factory=list)


@dataclass
class SummaryData:
    """AI-generated summary of the transcript."""
    text: Optional[str] = None
    action_items: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class TranscribeUsage:
    """Usage and billing info for a transcription."""
    duration_minutes: float
    cost_cents: int = 0
    tier: str = "transcribe"
    balance_cents: int = 0


@dataclass
class TranscribeResult:
    """Result of an audio transcription."""
    id: str
    duration_seconds: float
    language: str
    confidence: float
    transcript: TranscriptData
    formatted_transcript: str
    speakers: Optional[SpeakersData] = None
    summary: Optional[SummaryData] = None
    usage: Optional[TranscribeUsage] = None


@dataclass
class VoiceDesign:
    """A designed voice."""

    id: str
    name: str
    status: str = ""
    cost_cents: float = 0
