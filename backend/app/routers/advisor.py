from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.advisor import service
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.security.jwt import current_user
from app.voice import spoken

router = APIRouter(prefix="/advisor", tags=["advisor"])


class StartIn(BaseModel):
    language: str = "hi"
    channel: str = Field("text", pattern="^(text|voice)$")
    lead_source: str | None = None
    referral_code: str | None = None


class MessageIn(BaseModel):
    conversation_id: str
    content: str = Field(min_length=1, max_length=1000)
    modality: str = Field("text", pattern="^(text|voice)$")


class RecommendIn(BaseModel):
    conversation_id: str


def _spoken(text: str) -> str:
    """The short version text-to-speech reads (build Phase 5); the screen shows the full text."""
    return spoken(text, get_settings().voice_spoken_max_chars)


@router.post("/conversations", status_code=201)
def start(body: StartIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = service.start(db, user, body.language, body.channel, body.lead_source, body.referral_code)
    return out | {"speak": _spoken(out["message"]["content"])}


@router.post("/message")
def message(body: MessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = service.message(db, user, body.conversation_id, body.content, body.modality)
    return out | {"speak": _spoken(out["message"]["content"])}


@router.post("/recommend")
def recommend(body: RecommendIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = service.recommend(db, user, body.conversation_id)
    return out | {"speak": _spoken(out["explanation"])}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.get(db, user, conversation_id)
