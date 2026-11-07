from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class VoiceUnavailable(Exception):
    """The server can't do speech right now; the app falls back to the phone's own speech (or typing)."""


@dataclass
class Transcript:
    text: str
    confidence: float | None = None


@dataclass
class Speech:
    audio: bytes
    mime: str


class VoiceProvider(Protocol):
    name: str

    def transcribe(self, audio: bytes, mime: str, lang: str) -> Transcript: ...

    def speak(self, text: str, lang: str) -> Speech: ...
