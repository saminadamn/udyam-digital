"""In-memory audio conversion with ffmpeg (browser MediaRecorder gives webm/ogg; some speech APIs want 16 kHz mono WAV)."""
from __future__ import annotations

import shutil
import subprocess


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def to_wav16k(data: bytes, timeout: float = 20.0) -> bytes:
    """Audio never touches disk (DESIGN.md D2.8: voice audio not stored)."""
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not installed")
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"],
                       input=data, capture_output=True, timeout=timeout, check=False)
    if p.returncode != 0 or not p.stdout:
        raise RuntimeError("could not decode the recording")
    return p.stdout


def duration_s(wav: bytes) -> float:
    """Duration of a 16-bit PCM WAV from its header (data bytes / byte rate)."""
    if len(wav) < 44 or wav[:4] != b"RIFF":
        return 0.0
    byte_rate = int.from_bytes(wav[28:32], "little") or 1
    return max(0.0, (len(wav) - 44) / byte_rate)
