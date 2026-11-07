from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import Order, User
from app.pricing import quote as svc
from app.security.jwt import current_user

router = APIRouter(prefix="/quotes", tags=["quotes"])
orders_router = APIRouter(prefix="/orders", tags=["orders"])


class QuoteIn(BaseModel):
    recommendation_id: str


class ItemPatch(BaseModel):
    selected: bool | None = None
    qty: int | None = Field(None, ge=1, le=5000)

    @model_validator(mode="after")
    def one_field(self):
        if self.selected is None and self.qty is None:
            raise ValueError("send selected or qty")
        return self


class QuotePatch(BaseModel):
    current_spend_inr: int = Field(ge=0, le=10_000_000)


class OrderIn(BaseModel):
    quote_id: str


@router.post("", status_code=201)
def create_quote(body: QuoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return svc.create(db, user, body.recommendation_id)


@router.get("/{quote_id}")
def get_quote(quote_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return svc.get(db, user, quote_id)


@router.patch("/{quote_id}")
def patch_quote(quote_id: str, body: QuotePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return svc.set_spend(db, user, quote_id, body.current_spend_inr)


@router.patch("/{quote_id}/items/{product_id}")
def patch_item(quote_id: str, product_id: str, body: ItemPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return svc.update_item(db, user, quote_id, product_id, body.selected, body.qty)


@router.post("/{quote_id}/accept")
def accept_quote(quote_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return svc.accept(db, user, quote_id)


@orders_router.post("", status_code=201)
def create_order(body: OrderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = svc.accept(db, user, body.quote_id)
    return {"order_id": out["order_id"], "display_id": out["display_id"], "state": out["state"], "next_step": out["next_step"]}


@orders_router.get("")
def list_orders(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Order).order_by(Order.created_at.desc())
    if user.role == "customer":
        q = q.where(Order.user_id == user.id)
    return {"orders": [svc.order_view(db, o) for o in db.scalars(q)]}


@orders_router.get("/{order_id}")
def get_order(order_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or (user.role == "customer" and o.user_id != user.id):
        raise ApiError(404, "NOT_FOUND", "Order not found.")
    return svc.order_view(db, o, detail=True)


@orders_router.get("/{order_id}/tracker")
def get_tracker(order_id: str, language: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.orders import tracker

    o = db.get(Order, order_id)
    if not o or (user.role == "customer" and o.user_id != user.id):
        raise ApiError(404, "NOT_FOUND", "Order not found.")
    lang = language if language in get_settings().langs else user.language
    return tracker.view(db, o, lang)
