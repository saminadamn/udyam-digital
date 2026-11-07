"""Order state machine (DESIGN.md D4.1, D4.3): every allowed move works and writes an event; every other move is refused with 409."""
from datetime import datetime, timedelta

import pytest

from app.errors import ApiError
from app.models import Order, OrderEvent
from app.orders import state_machine as sm

STATES = [s for s in sm.TRANSITIONS if s]


class FakeDb:
    def __init__(self):
        self.added = []

    def add(self, x):
        self.added.append(x)

    def flush(self):
        pass


@pytest.fixture(autouse=True)
def no_side_effects(monkeypatch):
    monkeypatch.setattr(sm, "_after", lambda db, order, to: None)


def order_in(state):
    o = Order(id="ord_test", display_id="UD-0000-0001", quote_id="q", business_id="b", user_id="u")
    o.state = state
    return o


@pytest.mark.parametrize("frm", STATES)
def test_every_pair(frm):
    for to in STATES:
        db, o = FakeDb(), order_in(frm)
        if to in sm.TRANSITIONS[frm]:
            ev = sm.transition(db, o, to, "test", "why")
            assert o.state == to and isinstance(ev, OrderEvent) and (ev.from_state, ev.to_state, ev.actor) == (frm, to, "test")
            assert ev in db.added and o.state_entered_at
            h = sm.SLA_HOURS.get(to)
            if h:
                gap = datetime.fromisoformat(o.state_due_at) - datetime.fromisoformat(o.state_entered_at)
                assert gap == timedelta(hours=h)
            else:
                assert o.state_due_at is None
        else:
            with pytest.raises(ApiError) as e:
                sm.transition(db, o, to, "test")
            assert e.value.status == 409 and e.value.code == "INVALID_TRANSITION" and o.state == frm and not db.added
            assert e.value.details["allowed"] == sorted(sm.TRANSITIONS[frm])


def test_terminal_states_and_happy_path():
    assert sm.TRANSITIONS["LIVE"] == set() and sm.TRANSITIONS["CANCELLED"] == set()
    db, o = FakeDb(), order_in(None)
    sm.create(db, o, "user")
    for st in ["CONSENT_GIVEN", "KYC_SUBMITTED", "KYC_FLAGGED", "KYC_SUBMITTED", "KYC_VERIFIED", "INSTALL_BOOKED", "INSTALL_BOOKED", "INSTALLED", "LIVE"]:
        sm.transition(db, o, st, "test")
    events = [x for x in db.added if isinstance(x, OrderEvent)]
    assert [e.to_state for e in events][0] == "QUOTE_ACCEPTED" and events[-1].to_state == "LIVE" and len(events) == 10


def test_review_paths():
    for path, end in ([["KYC_FLAGGED", "HUMAN_REVIEW", "KYC_VERIFIED"], "KYC_VERIFIED"], [["KYC_FLAGGED", "HUMAN_REVIEW", "CANCELLED"], "CANCELLED"],
                      [["KYC_FLAGGED", "QUOTE_ACCEPTED"], "QUOTE_ACCEPTED"]):
        o = order_in("KYC_SUBMITTED")
        for st in path:
            sm.transition(FakeDb(), o, st, "agent:x")
        assert o.state == end
