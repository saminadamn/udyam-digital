"""POST /voice/transcribe and /voice/speak (DESIGN.md D3.2). Server fallback only: the phone's Web Speech API is the default."""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.errors import ApiError
from app.models import User
from app.security.jwt import current_user
from app.voice import VoiceUnavailable, audio, get_provider, spoken

router = APIRouter(prefix="/voice", tags=["voice"])
MAX_BYTES = 2_000_000          # about 30 s of opus/webm; WAV is checked by duration below
MAX_SECONDS = 30.5


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: str = "hi"
    short: bool = True


def _unavailable(e: Exception, what: str):
    return ApiError(503, "PROVIDER_UNAVAILABLE", str(e) or f"Server {what} is not available.", {"fallback": "browser"})


@router.post("/transcribe")
async def transcribe(audio_file: UploadFile = File(..., alias="audio"), language: str = Form("hi"), _: User = Depends(current_user)):
    data = await audio_file.read()
    if len(data) > MAX_BYTES:
        raise ApiError(413, "AUDIO_TOO_LONG", "Please keep voice messages under 30 seconds.")
    if language not in get_settings().langs:
        raise ApiError(400, "VALIDATION_ERROR", "Unsupported language.", {"field": "language"})
    try:
        provider = get_provider()
        if provider.name != "browser" and audio.ffmpeg_available():
            wav = audio.to_wav16k(data)
            if audio.duration_s(wav) > MAX_SECONDS:
                raise ApiError(413, "AUDIO_TOO_LONG", "Please keep voice messages under 30 seconds.")
        out = provider.transcribe(data, audio_file.content_type or "audio/webm", language)
    except VoiceUnavailable as e:
        raise _unavailable(e, "speech recognition") from e
    except RuntimeError as e:
        raise ApiError(400, "AUDIO_UNREADABLE", "We couldn't hear that recording. Please try again.") from e
    return {"text": out.text, "confidence": out.confidence, "provider": provider.name}


@router.post("/speak")
def speak(body: SpeakIn, _: User = Depends(current_user)):
    if body.language not in get_settings().langs:
        raise ApiError(400, "VALIDATION_ERROR", "Unsupported language.", {"field": "language"})
    text = spoken(body.text, get_settings().voice_spoken_max_chars) if body.short else body.text
    try:
        out = get_provider().speak(text, body.language)
    except VoiceUnavailable as e:
        raise _unavailable(e, "speech") from e
    return Response(content=out.audio, media_type=out.mime, headers={"Cache-Control": "no-store", "X-Spoken-Text-Length": str(len(text))})
