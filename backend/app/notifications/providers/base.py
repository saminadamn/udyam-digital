from dataclasses import dataclass
from typing import Protocol


@dataclass
class SendResult:
    ok: bool
    provider: str
    ref: str | None = None
    status: str = "sent"
    error: str | None = None


class MessagingProvider(Protocol):
    name: str

    def send_whatsapp(self, to_e164: str, body: str, status_callback: str | None = None) -> SendResult: ...

    def call(self, to_e164: str, twiml: str, status_callback: str | None = None) -> SendResult: ...
