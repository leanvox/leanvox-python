"""Sub-resource classes for the Leanvox client."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, BinaryIO, List, Optional, Union

from .errors import LeanvoxError
from .types import (
    AccountBalance,
    AccountUsage,
    FileExtractResult,
    Generation,
    GenerationList,
    SpeakersData,
    SummaryData,
    TranscribeResult,
    TranscribeUsage,
    TranscriptData,
    TranscriptSegment,
    Voice,
    VoiceDesign,
    VoiceList,
)


class AudioResource:
    """Audio intelligence operations (transcription, diarization, summarization)."""

    def __init__(self, http: Any) -> None:
        self._http = http

    def transcribe(
        self,
        file: Union[str, os.PathLike, BinaryIO, bytes],
        *,
        language: Optional[str] = None,
        features: Optional[List[str]] = None,
        num_speakers: Optional[int] = None,
    ) -> TranscribeResult:
        """Transcribe an audio file.

        Args:
            file: Path to audio file, file-like object, or raw bytes.
            language: Language code (auto-detect if omitted).
            features: List of features. Default: ["transcript", "diarization"].
                      Add "summary" for AI-generated summary.
            num_speakers: Hint for expected number of speakers.

        Returns:
            TranscribeResult with transcript, speakers, and optional summary.
        """
        # Build multipart files
        fp: Optional[BinaryIO] = None
        if isinstance(file, (str, os.PathLike)):
            filename = os.path.basename(str(file))
            fp = open(file, "rb")  # noqa: SIM115
            upload_file: Any = (filename, fp, "application/octet-stream")
        elif isinstance(file, bytes):
            upload_file = ("audio.wav", file, "application/octet-stream")
        else:
            filename = getattr(file, "name", "audio.wav")
            if isinstance(filename, (str, os.PathLike)):
                filename = os.path.basename(str(filename))
            upload_file = (filename, file, "application/octet-stream")
        files: Any = {"file": upload_file}

        data: dict[str, Any] = {}
        if language:
            data["language"] = language
        if features:
            data["features"] = json.dumps(features)
        if num_speakers is not None:
            data["num_speakers"] = str(num_speakers)

        try:
            resp = self._http.request(
                "POST",
                "/v1/audio/transcribe",
                files=files,
                data=data,
                timeout=600.0,
            )
        finally:
            if fp is not None:
                fp.close()

        # Async response (202) — poll until complete
        if "job_id" in resp and "poll_url" in resp:
            return self._poll_transcription_job(resp["job_id"])

        return self._parse_result(resp)

    def _poll_transcription_job(self, job_id: str) -> "TranscribeResult":
        """Poll an async transcription job until completion."""
        import time as _time

        poll_url = f"/v1/audio/transcriptions/{job_id}"
        max_attempts = 600  # 30 minutes at 3s intervals

        for _ in range(max_attempts):
            _time.sleep(3)
            job = self._http.request("GET", poll_url)

            status = job.get("status", "")
            if status == "completed":
                result = job.get("result")
                if result is None:
                    raise LeanvoxError("Job completed but no result returned")
                return self._parse_result(result)
            elif status == "failed":
                msg = job.get("error_message", "Unknown error")
                raise LeanvoxError(f"Transcription failed: {msg}")
            # pending/processing — keep polling

        raise LeanvoxError("Transcription timed out after 30 minutes")

    @staticmethod
    def _parse_result(data: dict) -> TranscribeResult:
        transcript_data = data.get("transcript", {})
        segments = [
            TranscriptSegment(
                start=s["start"],
                end=s["end"],
                text=s["text"],
                confidence=s.get("confidence"),
                speaker=s.get("speaker"),
            )
            for s in transcript_data.get("segments", [])
        ]

        speakers = None
        if "speakers" in data and data["speakers"]:
            sp = data["speakers"]
            speakers = SpeakersData(count=sp["count"], labels=sp.get("labels", []))

        summary = None
        if "summary" in data and data["summary"]:
            sm = data["summary"]
            summary = SummaryData(
                text=sm.get("text"),
                action_items=sm.get("action_items", []),
                topics=sm.get("topics", []),
                error=sm.get("error"),
            )

        usage = None
        if "usage" in data and data["usage"]:
            u = data["usage"]
            usage = TranscribeUsage(
                duration_minutes=u["duration_minutes"],
                cost_cents=u.get("cost_cents", 0),
                tier=u.get("tier", "transcribe"),
                balance_cents=u.get("balance_cents", 0),
            )

        return TranscribeResult(
            id=data["id"],
            duration_seconds=data["duration_seconds"],
            language=data["language"],
            confidence=data["confidence"],
            transcript=TranscriptData(
                text=transcript_data.get("text", ""),
                segments=segments,
            ),
            formatted_transcript=data.get("formatted_transcript", ""),
            speakers=speakers,
            summary=summary,
            usage=usage,
        )


class VoicesResource:
    """client.voices — voice management."""

    def __init__(self, http: Any) -> None:
        self._http = http

    def list(self, *, model: str | None = None) -> VoiceList:
        params = {"model": model} if model else None
        data = self._http.request("GET", "/v1/voices", params=params)
        return VoiceList(
            standard_voices=[Voice(**v) for v in data.get("standard_voices", [])],
            pro_voices=[Voice(**v) for v in data.get("pro_voices", [])],
            cloned_voices=[Voice(**v) for v in data.get("cloned_voices", [])],
        )

    def list_curated(self) -> List[Voice]:
        data = self._http.request("GET", "/v1/voices/curated")
        return [Voice(**v) for v in data.get("voices", [])]

    def clone(
        self,
        name: str,
        audio: Union[BinaryIO, str],
        *,
        description: str = "",
        auto_unlock: bool = False,
    ) -> Voice:
        if isinstance(audio, str):
            # base64 string
            files = None
            json_body = {
                "name": name,
                "audio_base64": audio,
                "description": description,
            }
            data = self._http.request("POST", "/v1/voices/clone", json=json_body)
        else:
            files = {"audio": ("audio.wav", audio, "audio/wav")}
            form_data = {"name": name, "description": description}
            data = self._http.request(
                "POST", "/v1/voices/clone", data=form_data, files=files
            )

        voice = Voice(**{k: v for k, v in data.items() if k in Voice.__dataclass_fields__})

        if auto_unlock and voice.status == "pending_unlock":
            self.unlock(voice.voice_id)
            voice.status = "active"

        return voice

    def unlock(self, voice_id: str) -> dict:
        return self._http.request("POST", f"/v1/voices/{voice_id}/unlock")

    def design(
        self,
        name: str,
        prompt: str,
        *,
        language: str = "",
        description: str = "",
    ) -> VoiceDesign:
        body = {"name": name, "prompt": prompt}
        if language:
            body["language"] = language
        if description:
            body["description"] = description
        data = self._http.request("POST", "/v1/voices/design", json=body)
        return VoiceDesign(**{k: v for k, v in data.items() if k in VoiceDesign.__dataclass_fields__})

    def list_designs(self) -> List[VoiceDesign]:
        data = self._http.request("GET", "/v1/voices/designs")
        return [VoiceDesign(**d) for d in data.get("designs", [])]

    def delete(self, voice_id: str) -> None:
        self._http.request("DELETE", f"/v1/voices/{voice_id}")


class FilesResource:
    """client.files — file processing."""

    def __init__(self, http: Any) -> None:
        self._http = http

    def extract_text(self, file: BinaryIO) -> FileExtractResult:
        files = {"file": (getattr(file, "name", "upload"), file)}
        data = self._http.request("POST", "/v1/files/extract-text", files=files)
        return FileExtractResult(**{k: v for k, v in data.items() if k in FileExtractResult.__dataclass_fields__})


class GenerationsResource:
    """client.generations — generation history."""

    def __init__(self, http: Any) -> None:
        self._http = http

    def list(self, *, limit: int = 20, offset: int = 0) -> GenerationList:
        data = self._http.request(
            "GET", "/v1/generations", params={"limit": limit, "offset": offset}
        )
        return GenerationList(
            generations=[Generation(**g) for g in data.get("generations", [])],
            total=data.get("total", 0),
        )

    def get_audio(self, generation_id: str) -> Generation:
        data = self._http.request("GET", f"/v1/generations/{generation_id}/audio")
        return Generation(**{k: v for k, v in data.items() if k in Generation.__dataclass_fields__})

    def delete(self, generation_id: str) -> None:
        self._http.request("DELETE", f"/v1/generations/{generation_id}")


class AccountResource:
    """client.account — account & billing."""

    def __init__(self, http: Any) -> None:
        self._http = http

    def balance(self) -> AccountBalance:
        data = self._http.request("GET", "/v1/account/balance")
        return AccountBalance(**{k: v for k, v in data.items() if k in AccountBalance.__dataclass_fields__})

    def usage(
        self, *, days: int = 30, model: str | None = None, limit: int = 100
    ) -> AccountUsage:
        params: dict = {"days": days, "limit": limit}
        if model:
            params["model"] = model
        data = self._http.request("GET", "/v1/account/usage", params=params)
        return AccountUsage(entries=data.get("entries", []))

    def buy_credits(self, amount_cents: int) -> dict:
        data = self._http.request(
            "POST", "/v1/billing/checkout", json={"amount_cents": amount_cents}
        )
        return data
