"""Messaging providers behind one interface (DESIGN.md D1.1 Notification service): Twilio sandbox or the mock outbox."""
from app.config import get_settings
from app.notifications.providers.base import MessagingProvider, SendResult
from app.notifications.providers.mock import MockProvider
from app.notifications.providers.twilio import TwilioProvider


def twilio_configured() -> bool:
    s = get_settings()
    return bool(s.twilio_account_sid and s.twilio_auth_token)


def get_provider() -> MessagingProvider:
    if get_settings().notify_provider == "twilio" and twilio_configured():
        return TwilioProvider(get_settings())
    return MockProvider()


def status() -> str:
    """For /health: what actually sends messages right now."""
    if get_settings().notify_provider == "twilio":
        return "twilio" if twilio_configured() else "mock (twilio not configured)"
    return "mock"


__all__ = ["MessagingProvider", "SendResult", "MockProvider", "TwilioProvider", "get_provider", "status", "twilio_configured"]
