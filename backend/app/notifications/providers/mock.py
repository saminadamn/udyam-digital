"""The mock outbox. Nothing leaves the server: the notifications / call_logs rows are the record the demo shows (screen A6)."""
import uuid

from app.notifications.providers.base import SendResult


class MockProvider:
    name = "mock"

    def send_whatsapp(self, to_e164: str, body: str, status_callback: str | None = None) -> SendResult:
        return SendResult(ok=True, provider=self.name, ref=f"mock-wa-{uuid.uuid4().hex[:10]}", status="sent")

    def call(self, to_e164: str, twiml: str, status_callback: str | None = None) -> SendResult:
        return SendResult(ok=True, provider=self.name, ref=f"mock-call-{uuid.uuid4().hex[:10]}", status="logged")
