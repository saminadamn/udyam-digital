"""Server speech adapters behind one interface (DESIGN.md D1.1 Voice service, D3.2 /voice/*).

The phone's Web Speech API is the default; these run only when the browser can't (no SpeechRecognition, or no voice installed
for the language). VOICE_PROVIDER picks one: browser (server answers 503 so the app uses the phone), sarvam or bhashini."""
from __future__ import annotations

import base64
import json

import httpx

from app.voice import audio
from app.voice.base import Speech, Transcript, VoiceUnavailable

LOCALE = {"hi": "hi-IN", "en": "en-IN", "mr": "mr-IN", "ta": "ta-IN", "bn": "bn-IN", "kn": "kn-IN", "gu": "gu-IN", "te": "te-IN"}
# Bhashini (Dhruva) public service ids by language family; override with BHASHINI_ASR_SERVICE_IDS / BHASHINI_TTS_SERVICE_IDS
# as JSON, e.g. {"hi": "ai4bharat/conformer-hi-gpu--t4"}.
INDO_ARYAN, DRAVIDIAN = {"hi", "mr", "gu", "bn"}, {"ta", "te", "kn"}
BHASHINI_ASR = {**{l: "ai4bharat/conformer-multilingual-indo_aryan-gpu--t4" for l in INDO_ARYAN},
                **{l: "ai4bharat/conformer-multilingual-dravidian-gpu--t4" for l in DRAVIDIAN}, "en": "ai4bharat/whisper-medium-en--gpu--t4"}
BHASHINI_TTS = {**{l: "ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4" for l in INDO_ARYAN},
                **{l: "ai4bharat/indic-tts-coqui-dravidian-gpu--t4" for l in DRAVIDIAN}, "en": "ai4bharat/indic-tts-coqui-misc-gpu--t4"}


class BrowserOnly:
    """The default: speech stays on the phone. The endpoints exist so the app can tell the server has no speech configured."""
    name = "browser"

    def transcribe(self, audio_bytes: bytes, mime: str, lang: str) -> Transcript:
        raise VoiceUnavailable("Server speech is not configured; the app uses your phone's speech recognition.")

    def speak(self, text: str, lang: str) -> Speech:
        raise VoiceUnavailable("Server speech is not configured; the app uses your phone's voice.")


class _Http:
    def __init__(self, settings, client: httpx.Client | None = None):
        self.key = settings.voice_api_key
        self.timeout = settings.voice_timeout_s
        self.client = client or httpx.Client(timeout=self.timeout)
        if not self.key:
            raise VoiceUnavailable(f"{self.name} needs VOICE_API_KEY.")

    def _post(self, url: str, **kw) -> dict:
        try:
            r = self.client.post(url, timeout=self.timeout, **kw)
        except httpx.HTTPError as e:
            raise VoiceUnavailable(f"{self.name} unreachable: {type(e).__name__}") from e
        if r.status_code >= 400:
            raise VoiceUnavailable(f"{self.name} returned {r.status_code}")
        try:
            return r.json()
        except ValueError as e:
            raise VoiceUnavailable(f"{self.name} sent an unreadable reply") from e


class Sarvam(_Http):
    """Sarvam AI: Saaras speech-to-text (multipart) and Bulbul text-to-speech (JSON, base64 WAV back)."""
    name = "sarvam"

    def __init__(self, settings, client: httpx.Client | None = None):
        super().__init__(settings, client)
        self.base = settings.sarvam_base_url.rstrip("/")
        self.stt_model, self.tts_model, self.speaker = settings.sarvam_stt_model, settings.sarvam_tts_model, settings.sarvam_speaker

    def transcribe(self, audio_bytes: bytes, mime: str, lang: str) -> Transcript:
        if audio.ffmpeg_available():
            audio_bytes, mime = audio.to_wav16k(audio_bytes), "audio/wav"
        mime = mime.split(";")[0].strip() or "audio/webm"  # Sarvam rejects "audio/webm;codecs=opus" but accepts "audio/webm"
        ext = "wav" if "wav" in mime else "webm" if "webm" in mime else "ogg"
        out = self._post(f"{self.base}/speech-to-text", headers={"api-subscription-key": self.key},
                         data={"model": self.stt_model, "language_code": LOCALE.get(lang, "unknown"),
                               **({"mode": "transcribe"} if self.stt_model.startswith("saaras") else {})},
                         files={"file": (f"speech.{ext}", audio_bytes, mime)})
        return Transcript(text=(out.get("transcript") or "").strip(), confidence=out.get("confidence"))

    def speak(self, text: str, lang: str) -> Speech:
        out = self._post(f"{self.base}/text-to-speech", headers={"api-subscription-key": self.key},
                         json={"text": text, "language_code": LOCALE.get(lang, "hi-IN"), "speaker": self.speaker,
                               "model": self.tts_model})
        clips = out.get("audios") or []
        if not clips:
            raise VoiceUnavailable("sarvam returned no audio")
        return Speech(audio=base64.b64decode(clips[0]), mime="audio/wav")


class Bhashini(_Http):
    """Bhashini / Dhruva inference pipeline: one ASR or TTS task per call, authorised with the inference API key."""
    name = "bhashini"

    def __init__(self, settings, client: httpx.Client | None = None):
        super().__init__(settings, client)
        self.url = settings.bhashini_inference_url
        self.asr = BHASHINI_ASR | (json.loads(settings.bhashini_asr_service_ids) if settings.bhashini_asr_service_ids else {})
        self.tts = BHASHINI_TTS | (json.loads(settings.bhashini_tts_service_ids) if settings.bhashini_tts_service_ids else {})

    def _task(self, task: dict, data: dict) -> dict:
        out = self._post(self.url, headers={"Authorization": self.key, "Content-Type": "application/json"},
                         json={"pipelineTasks": [task], "inputData": data})
        resp = (out.get("pipelineResponse") or [{}])[0]
        return resp

    def transcribe(self, audio_bytes: bytes, mime: str, lang: str) -> Transcript:
        if not audio.ffmpeg_available():
            raise VoiceUnavailable("bhashini needs WAV audio and ffmpeg is not installed")
        wav = audio.to_wav16k(audio_bytes)
        resp = self._task({"taskType": "asr", "config": {"language": {"sourceLanguage": lang}, "serviceId": self.asr.get(lang, self.asr["hi"]),
                                                          "audioFormat": "wav", "samplingRate": 16000}},
                          {"audio": [{"audioContent": base64.b64encode(wav).decode()}]})
        text = ((resp.get("output") or [{}])[0].get("source") or "").strip()
        return Transcript(text=text, confidence=None)

    def speak(self, text: str, lang: str) -> Speech:
        resp = self._task({"taskType": "tts", "config": {"language": {"sourceLanguage": lang}, "serviceId": self.tts.get(lang, self.tts["hi"]),
                                                          "gender": "female", "samplingRate": 22050}},
                          {"input": [{"source": text}]})
        clips = resp.get("audio") or []
        if not clips or not clips[0].get("audioContent"):
            raise VoiceUnavailable("bhashini returned no audio")
        return Speech(audio=base64.b64decode(clips[0]["audioContent"]), mime="audio/wav")
