"""Build Phase 5: voice in the advisor. Browser speech first; Sarvam / Bhashini adapters behind one interface (DESIGN.md D3.2)."""
import base64
import json

import httpx
import pytest

from tests.test_advisor import chips, login
from tests.test_tracker import login as cached_login
from app.voice.brevity import spoken


def test_spoken_keeps_the_question_and_stays_short():
    long = ("Found Neelgiri Physio Clinic, GST Active. Your GSTIN 27•••••••••1Z5 is saved. We also checked the registry for your state "
            "and everything matches what you told us earlier in this chat. What internet do you use today?")
    out = spoken(long)
    assert out.endswith("What internet do you use today?") and len(out) <= 180 and "•" not in out
    assert spoken("Hello. How many people work here?") == "Hello. How many people work here?"
    assert "http" not in spoken("Track it here: https://x.example/order/1 Thanks.")
    assert spoken("Your plan costs Rs 6,055 a month.") == "Your plan costs ₹6,055 a month."
    hi = spoken("ठीक है। आपकी GST जानकारी मिल गई और सब सही है। आपके पास अभी कौन सा इंटरनेट है?")
    assert hi.endswith("इंटरनेट है?") and len(hi) <= 180


def test_advisor_returns_a_short_spoken_reply_and_records_voice(client):
    h = login(client, "+919855500001", "hi")
    r = client.post("/api/v1/advisor/conversations", json={"language": "hi"}, headers=h).json()
    assert r["speak"] and len(r["speak"]) <= 180
    cid = r["conversation_id"]
    r = client.post("/api/v1/advisor/message", json={"conversation_id": cid, "content": chips("hi", "chips_type", 1), "modality": "voice"},
                    headers=h).json()
    assert r["speak"] and len(r["speak"]) <= 180 and r["speak"].endswith("?")
    from app.db import SessionLocal
    from app.models import Conversation, Message

    with SessionLocal() as db:
        assert db.get(Conversation, cid).channel == "voice"
        assert {m.modality for m in db.query(Message).filter(Message.conversation_id == cid, Message.role != "system")} >= {"voice"}


def test_server_speech_falls_back_to_the_browser_when_not_configured(client):
    auth = cached_login(client, '+919855500099')
    r = client.post("/api/v1/voice/transcribe", data={"language": "hi"}, files={"audio": ("a.webm", b"\x1aE\xdf\xa3", "audio/webm")}, headers=auth)
    assert r.status_code == 503 and r.json()["error"]["details"]["fallback"] == "browser"
    r = client.post("/api/v1/voice/speak", json={"text": "नमस्ते", "language": "hi"}, headers=auth)
    assert r.status_code == 503 and r.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    r = client.post("/api/v1/voice/transcribe", data={"language": "hi"}, files={"audio": ("a.webm", b"0" * 2_000_001, "audio/webm")}, headers=auth)
    assert r.status_code == 413 and r.json()["error"]["code"] == "AUDIO_TOO_LONG"
    assert client.get("/api/v1/health").json()["providers"]["voice"] == "browser"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _settings(**kw):
    from app.config import Settings

    return Settings(voice_api_key="k", **kw)


def test_sarvam_adapter(monkeypatch):
    from app.voice import audio, providers

    monkeypatch.setattr(audio, "ffmpeg_available", lambda: False)
    seen = []

    def handler(req):
        seen.append(req)
        if req.url.path == "/speech-to-text":
            return httpx.Response(200, json={"transcript": " मेरी दुकान है ", "language_code": "hi-IN"})
        return httpx.Response(200, json={"audios": [base64.b64encode(b"RIFFwav").decode()]})

    p = providers.Sarvam(_settings(), _client(handler))
    t = p.transcribe(b"opus", "audio/webm", "hi")
    assert t.text == "मेरी दुकान है"
    req = seen[0]
    assert req.headers["api-subscription-key"] == "k" and b'name="language_code"\r\n\r\nhi-IN' in req.content and b"saarika" in req.content
    s = p.speak("नमस्ते", "ta")
    assert s.audio == b"RIFFwav" and s.mime == "audio/wav"
    body = json.loads(seen[1].content)
    assert body["target_language_code"] == "ta-IN" and body["text"] == "नमस्ते"
    with pytest.raises(providers.VoiceUnavailable):
        providers.Sarvam(_settings(), _client(lambda r: httpx.Response(500))).speak("x", "hi")


def test_bhashini_adapter(monkeypatch):
    from app.voice import audio, providers

    monkeypatch.setattr(audio, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(audio, "to_wav16k", lambda data: b"RIFF....")
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append((req.headers.get("authorization"), body))
        task = body["pipelineTasks"][0]["taskType"]
        if task == "asr":
            return httpx.Response(200, json={"pipelineResponse": [{"taskType": "asr", "output": [{"source": "ನಮ್ಮ ಅಂಗಡಿ"}]}]})
        return httpx.Response(200, json={"pipelineResponse": [{"taskType": "tts", "audio": [{"audioContent": base64.b64encode(b"wav").decode()}]}]})

    p = providers.Bhashini(_settings(), _client(handler))
    assert p.transcribe(b"opus", "audio/webm", "kn").text == "ನಮ್ಮ ಅಂಗಡಿ"
    auth, body = seen[0]
    assert auth == "k" and body["pipelineTasks"][0]["config"]["language"]["sourceLanguage"] == "kn"
    assert "dravidian" in body["pipelineTasks"][0]["config"]["serviceId"] and body["inputData"]["audio"][0]["audioContent"]
    assert p.speak("ನಮಸ್ಕಾರ", "kn").audio == b"wav"


def test_speak_endpoint_reads_the_short_version(client, monkeypatch):
    auth = cached_login(client, '+919855500099')
    from app.routers import voice as voice_router
    from app.voice.base import Speech

    said = []

    class Fake:
        name = "fake"

        def speak(self, text, lang):
            said.append((text, lang))
            return Speech(audio=b"RIFFxx", mime="audio/wav")

    monkeypatch.setattr(voice_router, "get_provider", lambda: Fake())
    long = "One. Two is a longer sentence that goes on for quite a while. " * 6 + "Which city are you in?"
    r = client.post("/api/v1/voice/speak", json={"text": long, "language": "en"}, headers=auth)
    assert r.status_code == 200 and r.content == b"RIFFxx" and r.headers["content-type"] == "audio/wav"
    assert said[0][0].endswith("Which city are you in?") and len(said[0][0]) <= 180


def test_missing_key_is_reported_not_crashed(client, monkeypatch):
    auth = cached_login(client, '+919855500099')
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "voice_provider", "sarvam")
    monkeypatch.setattr(s, "voice_api_key", "")
    r = client.post("/api/v1/voice/speak", json={"text": "hi", "language": "en"}, headers=auth)
    assert r.status_code == 503 and "VOICE_API_KEY" in r.json()["error"]["message"]
    assert client.get("/api/v1/health").json()["providers"]["voice"] == "browser (sarvam has no key)"


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="ffmpeg not installed")
def test_browser_recording_converts_to_16k_wav_in_memory():
    import subprocess

    from app.voice import audio

    webm = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "libopus",
                           "-f", "webm", "pipe:1"], capture_output=True, check=True).stdout
    wav = audio.to_wav16k(webm)
    assert wav[:4] == b"RIFF" and 1.9 < audio.duration_s(wav) < 2.2
    with pytest.raises(RuntimeError):
        audio.to_wav16k(b"not audio")
