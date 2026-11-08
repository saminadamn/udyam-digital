from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BACKEND_DIR / ".env"), extra="ignore")

    app_env: str = "dev"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'udyam.db'}"
    data_dir: Path = REPO_DIR / "data"
    jwt_secret: str = "dev-only-change-me-32-bytes-minimum!!"
    jwt_expires_min: int = 1440
    app_encryption_key: str = ""
    pii_hash_key: str = "dev-only-hash-key"
    otp_mode: str = "mock"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str = ""          # e.g. https://udyam-[a-z0-9-]+\.vercel\.app for Vercel preview URLs
    llm_provider: str = "template"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_s: float = 8.0
    advisor_max_questions: int = 6
    advisor_max_failed_turns: int = 2
    ocr_engine: str = "tesseract"
    kyc_today: str = "2026-07-15"
    kyc_address_proof_max_days: int = 90
    upload_dir: Path = BACKEND_DIR / "storage"
    upload_max_mb: int = 8
    doc_retention_days: int = 90
    doc_retention_abandoned_days: int = 30
    sla_job_enabled: bool = True
    sla_scan_interval_sec: int = 300
    supported_langs: str = "hi,en,mr,ta,bn,kn,gu,te"
    propensity_model_path: Path = BACKEND_DIR / "models" / "propensity.pkl"

    # Phase 5: notifications (D3.9, D4.5). NOTIFY_PROVIDER=twilio with no credentials falls back to the mock outbox.
    notify_provider: str = "mock"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    twilio_voice_from: str = ""
    twilio_api_base: str = "https://api.twilio.com"
    twilio_timeout_s: float = 10.0
    notify_dispatch_enabled: bool = True
    notify_dispatch_interval_sec: int = 3
    public_app_url: str = "http://localhost:3000"
    public_api_url: str = ""

    # Phase 5: voice (D3.2). browser = Web Speech API in the phone, server endpoints answer 503 with a browser fallback.
    voice_provider: str = "browser"
    voice_api_key: str = ""
    voice_timeout_s: float = 15.0
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_stt_model: str = "saaras:v4"       # saaras:v3 also works; saarika:v2.5 is deprecated
    sarvam_tts_model: str = "bulbul:v3"       # all 8 app languages; bulbul:v2 is legacy
    sarvam_speaker: str = "priya"           # a bulbul:v3 voice; others: ritu, kavya, neha, shubh, aditya, rahul
    bhashini_inference_url: str = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
    bhashini_asr_service_ids: str = ""
    bhashini_tts_service_ids: str = ""
    voice_spoken_max_chars: int = 180

    # Security (build Phase 6)
    lookup_rate_limit: int = 20
    lookup_rate_window_s: int = 600
    otp_ip_rate_limit: int = 20
    retention_job_enabled: bool = True
    retention_job_interval_sec: int = 3600

    # Phase 5: admin leads (D3.8)
    advisor_abandon_minutes: int = 30
    call_cooldown_hours: int = 24

    def check_secrets(self) -> None:
        """Outside dev, refuse to start with missing or built-in secrets (they would make every token and PII column forgeable)."""
        if self.app_env == "dev":
            return
        bad = [n for n, v in (("JWT_SECRET", self.jwt_secret), ("PII_HASH_KEY", self.pii_hash_key)) if not v or v.startswith(("dev-only", "change-me")) or len(v) < 32]
        if len(self.app_encryption_key) < 32:
            bad.append("APP_ENCRYPTION_KEY")
        if bad:
            raise RuntimeError(f"APP_ENV={self.app_env} needs real secrets in the environment: {', '.join(bad)}")

    @property
    def langs(self) -> list[str]:
        return [x.strip() for x in self.supported_langs.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
