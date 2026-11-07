"""Escalation assignment (DESIGN.md D4.4): skill filter, language first, least-loaded, max_open cap, unassigned when nobody fits.
Each test runs inside a transaction that is rolled back, starting from an empty queue."""
import json

import pytest


@pytest.fixture()
def db(seeded):
    from app.db import SessionLocal
    from app.models import Escalation

    s = SessionLocal()
    s.begin()
    for e in s.query(Escalation).filter(Escalation.status.in_(("open", "assigned", "in_progress"))):
        e.status = "resolved"
    s.flush()
    yield s
    s.rollback()
    s.close()


def agent(db, first):
    from app.models import Agent

    return next(a for a in db.query(Agent) if a.name.startswith(first))


def load(db, first, n):
    from app.models import Escalation, now_iso

    a = agent(db, first)
    for _ in range(n):
        db.add(Escalation(trigger="user_request", priority="P3", reason="load", status="assigned", assigned_agent_id=a.id, assigned_at=now_iso(),
                          required_skill="sales", lead_id="L00001"))
    db.flush()


def pick(db, skill, lang):
    from app.escalations.service import assign_agent

    a = assign_agent(db, skill, lang)
    return a.name.split()[0] if a else None


def test_skill_and_language_come_first(db):
    assert pick(db, "kyc", "mr") == "Meera"
    assert pick(db, "kyc", "kn") == "Kavya"
    assert pick(db, "install", "ta") == "Arjun"
    assert pick(db, "account_manager", "bn") == "Sanjay"
    assert pick(db, "kyc", "ta") in {"Priya", "Meera", "Kavya"}, "no Tamil KYC agent: still assigned to someone with the skill"


def test_least_loaded_wins_among_language_matches(db):
    assert {pick(db, "kyc", "hi")} <= {"Priya", "Meera"}
    load(db, "Priya", 3)
    assert pick(db, "kyc", "hi") == "Meera"
    load(db, "Meera", 5)
    assert pick(db, "kyc", "hi") == "Priya"


def test_full_agents_are_skipped_and_nobody_means_open_queue(db):
    from app.escalations.service import create

    for first in ("Priya", "Meera", "Kavya"):
        agent(db, first).max_open = 1
        load(db, first, 1)
    assert pick(db, "kyc", "hi") is None
    e = create(db, trigger="kyc_flag", priority="P1", skill="kyc", reason="test", lang="hi", lead_id="L00001")
    assert e.status == "open" and e.assigned_agent_id is None and e.sla_due_at


def test_inactive_agents_never_get_cases(db):
    for first in ("Priya", "Meera"):
        agent(db, first).active = 0
    db.flush()
    assert pick(db, "kyc", "hi") == "Kavya"


def test_every_trigger_maps_to_a_skill_an_agent_has(db):
    from app.models import Agent

    skills = {s for a in db.query(Agent) for s in json.loads(a.skills)}
    assert {"kyc", "sales", "install", "account_manager"} <= skills
