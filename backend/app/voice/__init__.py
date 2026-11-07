from app.config import get_settings
from app.voice.base import Speech, Transcript, VoiceProvider, VoiceUnavailable
from app.voice.brevity import spoken

PROVIDERS = ("browser", "sarvam", "bhashini")


def get_provider() -> VoiceProvider:
    from app.voice import providers

    name = get_settings().voice_provider
    if name == "sarvam":
        return providers.Sarvam(get_settings())
    if name == "bhashini":
        return providers.Bhashini(get_settings())
    return providers.BrowserOnly()


def status() -> str:
    s = get_settings()
    if s.voice_provider in ("sarvam", "bhashini"):
        return s.voice_provider if s.voice_api_key else f"browser ({s.voice_provider} has no key)"
    return "browser"


__all__ = ["get_provider", "status", "spoken", "Speech", "Transcript", "VoiceProvider", "VoiceUnavailable"]
