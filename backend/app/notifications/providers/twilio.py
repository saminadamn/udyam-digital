"""Twilio REST adapter (WhatsApp sandbox messages and voice calls) plus webhook signature checks. Uses httpx, no SDK."""
from __future__ import annotations

import base64
import hashlib
import hmac

import httpx

from app.notifications.providers.base import SendResult

STATUS = {"queued": "queued", "accepted": "queued", "sending": "queued", "sent": "sent", "delivered": "delivered", "read": "delivered",
          "failed": "failed", "undelivered": "failed", "ringing": "ringing", "initiated": "ringing", "in-progress": "ringing",
          "completed": "completed", "busy": "failed", "no-answer": "failed", "canceled": "failed"}


class TwilioProvider:
    name = "twilio"

    def __init__(self, settings, client: httpx.Client | None = None):
        self.sid = settings.twilio_account_sid
        self.token = settings.twilio_auth_token
        self.wa_from = settings.twilio_whatsapp_from
        self.voice_from = settings.twilio_voice_from
        self.base = settings.twilio_api_base.rstrip("/")
        self.timeout = settings.twilio_timeout_s
        self.client = client

    def _post(self, resource: str, data: dict) -> SendResult:
        url = f"{self.base}/2010-04-01/Accounts/{self.sid}/{resource}.json"
        try:
            if self.client:
                r = self.client.post(url, data=data, auth=(self.sid, self.token), timeout=self.timeout)
            else:
                r = httpx.post(url, data=data, auth=(self.sid, self.token), timeout=self.timeout)
        except httpx.HTTPError as e:
            return SendResult(ok=False, provider=self.name, status="failed", error=f"twilio unreachable: {type(e).__name__}")
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400:
            msg = body.get("message") or r.text[:200]
            return SendResult(ok=False, provider=self.name, status="failed", error=f"twilio {r.status_code} {body.get('code', '')}: {msg}".strip())
        return SendResult(ok=True, provider=self.name, ref=body.get("sid"), status=STATUS.get(body.get("status", "queued"), "queued"))

    def send_whatsapp(self, to_e164: str, body: str, status_callback: str | None = None) -> SendResult:
        frm = self.wa_from if self.wa_from.startswith("whatsapp:") else f"whatsapp:{self.wa_from}"
        data = {"From": frm, "To": f"whatsapp:{to_e164}", "Body": body}
        if status_callback:
            data["StatusCallback"] = status_callback
        return self._post("Messages", data)

    def call(self, to_e164: str, twiml: str, status_callback: str | None = None) -> SendResult:
        if not self.voice_from:
            return SendResult(ok=False, provider=self.name, status="failed", error="TWILIO_VOICE_FROM is not set")
        data = {"From": self.voice_from, "To": to_e164, "Twiml": twiml}
        if status_callback:
            data["StatusCallback"] = status_callback
        return self._post("Calls", data)


def signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """X-Twilio-Signature: base64(HMAC-SHA1(token, url + sorted key/value pairs))."""
    payload = url + "".join(k + params[k] for k in sorted(params))
    return base64.b64encode(hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()).decode()


def valid_signature(auth_token: str, url: str, params: dict[str, str], sig: str | None) -> bool:
    return bool(sig and auth_token) and hmac.compare_digest(signature(auth_token, url, params), sig)
