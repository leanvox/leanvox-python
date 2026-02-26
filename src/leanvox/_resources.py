"""Sub-resource classes for the Leanvox client."""

from __future__ import annotations

import base64
from typing import Any, BinaryIO, List, Optional, Union

from .types import (
    AccountBalance,
    AccountUsage,
    FileExtractResult,
    Generation,
    GenerationList,
    Voice,
    VoiceDesign,
    VoiceList,
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
