"""Advisor orchestration (DESIGN.md D1.3 flow 1, D1.4 guardrails).

The conversation is slot-filling over six questions. The LLM may rephrase questions, read free text,
nudge the bundle and write the explanation, but every product, quantity and rupee comes from the rules
engine and pricing service, and every LLM output is checked before the owner sees it.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin import lead_sync
from app.advisor import guards, parse
from app.advisor.llm.base import get_provider
from app.advisor.rules import Profile, build_bundle, eligible_products, plan_options, rules_version, validate_bundle
from app.config import get_settings
from app.errors import ApiError
from app.i18n import text
from app.models import Agent, Business, Conversation, Escalation, GstinRecord, Lead, Message, Recommendation, User, new_id, now_iso
from app.pricing.service import price
from app.rules.catalogue import cached_from_db
from app.rules.engine import BASE_LINKS, NEED_PRODUCTS
from app.security.crypto import encrypt
from app.security.masking import mask_gstin, scrub

log = logging.getLogger("app.advisor")
ORDER = ["type", "team", "city", "gst", "internet", "needs"]


@lru_cache(maxsize=1)
def known_cities() -> dict[str, dict]:
    from app.db import SessionLocal

    with SessionLocal() as db:
        rows = db.execute(select(Lead.city, func.min(Lead.city_tier), func.min(Lead.state)).where(Lead.city.is_not(None)).group_by(Lead.city)).all()
    return {c: {"tier": int(t), "state": s} for c, t, s in rows}


def _state(conv: Conversation) -> dict:
    s = json.loads(conv.profile_json or "{}")
    s.setdefault("answers", {})
    s.setdefault("needs", [])
    return s


def _save_state(conv: Conversation, s: dict) -> None:
    conv.profile_json = json.dumps(s, ensure_ascii=False)
    conv.updated_at = now_iso()


def _next_field(s: dict) -> str | None:
    for f in ORDER:
        if f not in s["answers"]:
            return f
    return None


def _question(field: str, lang: str, s: dict) -> dict:
    seg = s["answers"].get("type")
    key = {"type": "q_type", "team": "q_team_chain" if seg == "multi" else "q_team", "city": "q_city", "gst": "q_gst",
           "internet": "q_internet", "needs": "q_needs"}[field]
    chips = {"type": "chips_type", "team": "chips_team_chain" if seg == "multi" else "chips_team", "city": "chips_city_other",
             "gst": "chips_gst", "internet": "chips_internet", "needs": "chips_needs"}[field]
    default = text(lang, key)
    phrased = get_provider().phrase_question(field, lang, public_profile(s), default)
    if phrased != default and (guards.problems(phrased, lang, set(), set()) or "?" not in phrased and "？" not in phrased and "।" not in phrased):
        phrased = default
    out = {"role": "assistant", "content": phrased, "quick_replies": list(text(lang, chips)), "field": field}
    if field == "needs":
        out["multi_select"] = True
        out["done_label"] = text(lang, "chip_done")
    if field == "city":
        top = [c for c in ("Mumbai", "Delhi", "Bengaluru", "Pune", "Jaipur", "Lucknow") if c in known_cities()]
        out["quick_replies"] = top + out["quick_replies"]
    return out


def public_profile(s: dict) -> dict:
    a = s["answers"]
    team = a.get("team") or [None, None]
    city = a.get("city") or {}
    gst = s.get("gst") or {}
    missing = [f for f in ORDER if f not in a]
    return {
        "segment": parse.SEGMENT_NAME.get(a.get("type")), "employees": team[0], "sites": team[1], "city": city.get("city"),
        "city_tier": city.get("city_tier"), "state": city.get("state"), "has_gstin": gst.get("has_gstin"), "gst_status": gst.get("status"),
        "gstin_masked": gst.get("masked"), "current_internet": a.get("internet"), "needs": s.get("needs", []),
        "complete": not missing, "missing": missing,
    }


def _msg(db: Session, conv: Conversation, role: str, content: str, modality: str = "text", status: str = "ok") -> None:
    db.add(Message(conversation_id=conv.id, role=role, content=scrub(content), modality=modality, validation_status=status))


def _assign_agent(db: Session, skill: str, lang: str) -> Agent | None:
    from app.escalations.service import assign_agent

    return assign_agent(db, skill, lang)


def escalate(db: Session, conv: Conversation, trigger: str, reason: str) -> dict:
    existing = db.scalar(select(Escalation).where(Escalation.conversation_id == conv.id, Escalation.status.in_(("open", "assigned", "in_progress"))))
    esc = existing
    if not esc:
        from app.escalations.service import create

        esc = create(db, trigger=trigger, priority="P2", skill="sales", reason=reason, lang=conv.language, conversation_id=conv.id,
                     lead_id=conv.lead_id, user_id=conv.user_id, sla_hours=4)
    agent = db.get(Agent, esc.assigned_agent_id) if esc.assigned_agent_id else None
    from app.escalations.service import when_text

    eta = when_text(esc.sla_due_at, conv.language)
    conv.status = "escalated"
    if conv.lead_id:
        lead = db.get(Lead, conv.lead_id)
        if lead:
            lead.advisor_outcome = "escalated"
            lead.drop_reason = "Asked for a person in the advisor" if trigger == "user_request" else "Advisor couldn't understand the answers"
    msg = text(conv.language, "handoff", agent=agent.name.split()[0], eta=eta) if agent else text(conv.language, "handoff_queue", eta=eta)
    return {"id": esc.id, "agent_name": agent.name.split()[0] if agent else None, "eta": eta, "message": msg}


def _restart_greeting(db: Session, conv: Conversation) -> Conversation:
    s = _state(conv)
    q = _question(_next_field(s), conv.language, s)
    _msg(db, conv, "assistant", text(conv.language, "greet") + " " + q["content"])
    conv.questions_asked = 1
    conv.failed_turns = 0
    return conv


def start(db: Session, user: User, language: str, channel: str, lead_source: str | None, referral_code: str | None) -> dict:
    if language not in get_settings().langs:
        raise ApiError(400, "VALIDATION_ERROR", "Unsupported language.", {"field": "language"})
    conv = db.scalar(select(Conversation).where(Conversation.user_id == user.id, Conversation.status == "active").order_by(Conversation.created_at.desc()))
    if conv and conv.language != language and not _state(conv)["answers"]:
        conv.language = language
        db.query(Message).filter(Message.conversation_id == conv.id).delete()
        conv = _restart_greeting(db, conv)
        db.commit()
        s = _state(conv)
        q = _question(_next_field(s), language, s)
        q["content"] = text(language, "greet") + " " + q["content"]
        return {"conversation_id": conv.id, "message": q, "resumed": False, "profile": public_profile(s)}
    resumed = bool(conv)
    if not conv:
        lead = Lead(lead_id=f"L-APP-{new_id('x')[-8:].upper()}", origin="app", created_date=now_iso()[:10], lead_source=lead_source or "App",
                    preferred_language=language, advisor_outcome="not_started", lead_status="open")
        db.add(lead)
        db.flush()
        conv = Conversation(user_id=user.id, lead_id=lead.lead_id, language=language, channel=channel,
                            profile_json=json.dumps({"answers": {}, "needs": [], "referral_code": referral_code}))
        db.add(conv)
        db.flush()
    s = _state(conv)
    field = _next_field(s)
    q = _question(field, conv.language, s) if field else {"role": "assistant", "content": text(conv.language, "ready"), "quick_replies": []}
    if not resumed:
        q["content"] = text(conv.language, "greet") + " " + q["content"]
        _msg(db, conv, "assistant", q["content"])
        conv.questions_asked = 1
    db.commit()
    return {"conversation_id": conv.id, "message": q, "resumed": resumed, "profile": public_profile(s)}


def _apply_gst(db: Session, s: dict, parsed: dict, lang: str) -> tuple[bool, str | None]:
    if parsed["answer"] in ("no", "later"):
        s["gst"] = {"has_gstin": parsed["answer"] == "later", "valid": False, "status": "None"}
        return True, None
    g = parsed["gstin"]
    if not parsed.get("checksum_ok"):
        return False, text(lang, "gst_invalid")
    rec = db.get(GstinRecord, g)
    if not rec:
        s["gst"] = {"has_gstin": True, "valid": False, "status": "None", "masked": mask_gstin(g), "enc": None}
        s["_gstin_enc"] = encrypt(g).decode()
        return True, text(lang, "gst_not_found")
    s["gst"] = {"has_gstin": True, "valid": True, "status": rec.status, "masked": mask_gstin(g), "trade_name": rec.trade_name, "state": rec.state}
    s["_gstin_enc"] = encrypt(g).decode()
    note = text(lang, "gst_found", name=rec.trade_name, status=rec.status)
    if rec.status != "Active":
        note += " " + text(lang, "gst_not_active", status=rec.status)
    return True, note


def _parse(db: Session, field: str, content: str, s: dict, lang: str):
    seg = s["answers"].get("type")
    if field == "type":
        v = parse.parse_type(content, lang)
    elif field == "team":
        v = parse.parse_team(content, lang, seg)
        v = list(v) if v else None
    elif field == "city":
        v = parse.parse_city(content, lang, known_cities())
    elif field == "gst":
        v = parse.parse_gst(content, lang)
    elif field == "internet":
        v = parse.parse_internet(content, lang)
    else:
        v = parse.parse_needs(content, lang)
        return v
    if v is None and field in ("type", "team", "city"):
        extracted = get_provider().extract(field, content, lang, public_profile(s))
        if extracted:
            if field == "type" and extracted.get("type") in parse.TYPE_VALUES:
                v = extracted["type"]
            elif field == "team" and isinstance(extracted.get("employees"), int) and extracted["employees"] > 0:
                v = [min(extracted["employees"], 5000), max(1, int(extracted.get("sites") or (2 if seg == "multi" else 1)))]
            elif field == "city" and extracted.get("city") and extracted.get("city_tier") in (1, 2):
                v = {"city": str(extracted["city"])[:60], "city_tier": extracted["city_tier"], "state": None, "assumed": True}
    return v


def message(db: Session, user: User, conversation_id: str, content: str, modality: str) -> dict:
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_id != user.id:
        raise ApiError(404, "CONVERSATION_NOT_FOUND", "This conversation was not found.")
    if conv.status in ("recommended", "abandoned"):
        raise ApiError(409, "CONVERSATION_CLOSED", "This conversation is finished. Start a new one.")
    s = _state(conv)
    lang = conv.language
    _msg(db, conv, "user", content, modality)
    settings = get_settings()
    conv.updated_at = now_iso()
    if modality == "voice":
        conv.channel = "voice"

    if parse.wants_human(content):
        esc = escalate(db, conv, "user_request", "Owner asked for a person during the advisor chat")
        reply = {"role": "assistant", "content": esc["message"], "quick_replies": []}
        _msg(db, conv, "assistant", reply["content"], modality)
        _save_state(conv, s)
        db.commit()
        return {"message": reply, "profile": public_profile(s), "status": conv.status, "failed_turns": conv.failed_turns, "escalation": esc}

    field = _next_field(s)
    notes: list[str] = []
    understood = False
    if field:
        v = _parse(db, field, content, s, lang)
        if field == "gst" and v:
            ok, note = _apply_gst(db, s, v, lang)
            if ok:
                s["answers"]["gst"] = v["answer"]
                understood = True
            if note:
                notes.append(note)
        elif field == "needs":
            s["needs"] = v
            s["answers"]["needs"] = True
            understood = True
        elif v is not None:
            s["answers"][field] = v
            understood = True

    escalation = None
    if field and not understood:
        conv.failed_turns += 1
        if conv.failed_turns >= settings.advisor_max_failed_turns:
            escalation = escalate(db, conv, "advisor_failed", f"Advisor could not understand the answer to '{field}' twice")

    nxt = _next_field(s)
    if escalation:
        reply = {"role": "assistant", "content": escalation["message"], "quick_replies": []}
    elif nxt is None:
        conv.status = "ready_to_recommend" if conv.status != "escalated" else conv.status
        reply = {"role": "assistant", "content": " ".join(notes + [text(lang, "ready")]), "quick_replies": []}
    else:
        q = _question(nxt, lang, s)
        if not understood:
            q["content"] = (notes[0] if notes else text(lang, "retry")) + " " + q["content"] if field == nxt else q["content"]
        elif notes:
            q["content"] = " ".join(notes) + " " + q["content"]
        if understood:
            conv.questions_asked = min(conv.questions_asked + 1, settings.advisor_max_questions)
        reply = q
    _msg(db, conv, "assistant", reply["content"], modality)
    _save_state(conv, s)
    lead_sync.from_conversation(db, conv, public_profile(s), [pid for need in s.get("needs", []) for pid in NEED_PRODUCTS.get(need, [])])
    db.commit()
    return {"message": reply, "profile": public_profile(s), "status": "ready_to_recommend" if nxt is None and not escalation else conv.status,
            "failed_turns": conv.failed_turns, "escalation": escalation}


def _profile(s: dict) -> Profile:
    a = s["answers"]
    gst = s.get("gst") or {}
    return Profile(segment=parse.SEGMENT_NAME[a["type"]], city_tier=int(a["city"]["city_tier"]), employees=int(a["team"][0]),
                   sites=int(a["team"][1]), gst_status=gst.get("status") or "None", gstin_valid=bool(gst.get("valid")), needs=list(s.get("needs", [])))


def _name(pid: str, catalogue) -> str:
    return catalogue[pid].name


def _why(pid: str, lang: str) -> str:
    w = text(lang, "why")
    if pid in BASE_LINKS:
        return w["link"]
    if pid in ("P07", "P08"):
        return w["mobile"]
    return w.get(pid) or text(lang, "products")[pid]


def _unlock(v: dict, lang: str) -> str:
    u = text(lang, "unlock")
    return u.get(v["rule"], "").format(**{k: v2 for k, v2 in (v.get("params") or {}).items() if not isinstance(v2, list)})


def _llm_adjust(profile: Profile, bundle: dict, catalogue) -> tuple[dict, str]:
    elig = eligible_products(profile, catalogue)["eligible"]
    allowed = [{"id": pid, "name": catalogue[pid].name} for pid in elig]
    choice = get_provider().choose({"segment": profile.segment, "employees": profile.employees, "sites": profile.sites, "needs": profile.needs},
                                   allowed, {"core": [p for p, _ in bundle["core"]], "addons": [p for p, _ in bundle["addons"]]})
    if not choice:
        return bundle, "rules"
    qty = {p: q for p, q in bundle["core"] + bundle["addons"]}
    core_ids = [p for p in choice.get("core", []) if p in elig]
    addon_ids = [p for p in choice.get("addons", []) if p in elig and p not in core_ids]
    if not core_ids or not any(p in BASE_LINKS for p in core_ids):
        return bundle, "rules_override"
    from app.rules.engine import _need_qty

    core = [(p, qty.get(p) or _need_qty(p, profile, catalogue)) for p in core_ids]
    addons = [(p, qty.get(p) or _need_qty(p, profile, catalogue)) for p in addon_ids]
    if validate_bundle(profile, core, catalogue) or validate_bundle(profile, core + addons, catalogue):
        log.info("LLM proposed an invalid bundle; rules engine overrides it")
        return bundle, "rules_override"
    rejected = [p for p in choice.get("core", []) + choice.get("addons", []) if p not in elig]
    if rejected:
        log.info("LLM proposed ineligible products %s; dropped by rules engine", rejected)
    return {**bundle, "core": core, "addons": addons}, "llm"


def _explanation(profile: Profile, bundle: dict, total: int, setup: int, lang: str, catalogue) -> tuple[str, str]:
    link = next((p for p, _ in bundle["core"] if p in BASE_LINKS), None)
    extras = [p for p, _ in bundle["core"] if p not in BASE_LINKS and p not in ("P07", "P08")]
    seg = text(lang, "segment")[profile.key].format(sites=profile.sites)
    and_ = text(lang, "and")
    whys = [_why(p, lang) for p in extras[:3]]
    if whys:
        extras_text = (", ".join(whys[:-1]) + f" {and_} " + whys[-1]) if len(whys) > 1 else whys[0]
        default = text(lang, "explain", segment=seg, employees=profile.employees, link=_name(link, catalogue), extras=extras_text, total=f"{total:,}")
    else:
        default = text(lang, "explain_noextras", segment=seg, employees=profile.employees, link=_name(link, catalogue), total=f"{total:,}")
    names_all = {p.name for p in catalogue.values()}
    names_ok = {_name(p, catalogue) for p, _ in bundle["core"] + bundle["addons"]}
    ctx = {"segment": seg, "employees": profile.employees, "sites": profile.sites, "needs": profile.needs, "total": total, "setup": setup,
           "products": [{"name": _name(p, catalogue), "qty": q, "what_it_does": _why(p, lang)} for p, q in bundle["core"]]}
    provider = get_provider()
    for attempt in range(2):
        out = provider.explain(ctx, lang, default)
        if out == default:
            return default, "template"
        issues = guards.problems(out, lang, names_ok, names_all, allowed_amounts={total, setup}, max_sentences=3)
        if not issues:
            return out, "ok" if attempt == 0 else "regenerated"
        log.info("explanation rejected: %s", issues)
    return default, "template"


def recommend(db: Session, user: User, conversation_id: str) -> dict:
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_id != user.id:
        raise ApiError(404, "CONVERSATION_NOT_FOUND", "This conversation was not found.")
    s = _state(conv)
    pub = public_profile(s)
    if not pub["complete"]:
        raise ApiError(409, "PROFILE_INCOMPLETE", "A few answers are still missing.", {"missing": pub["missing"]})
    lang = conv.language
    catalogue = cached_from_db()
    profile = _profile(s)
    bundle = build_bundle(profile, catalogue)
    if bundle["violations"] or not bundle["core"]:
        raise ApiError(422, "NO_ELIGIBLE_BUNDLE", "We couldn't build a plan for this business automatically. A specialist can help.")
    bundle, source = _llm_adjust(profile, bundle, catalogue)
    assert not validate_bundle(profile, bundle["core"] + bundle["addons"], catalogue)
    priced = price(bundle["core"], profile.key, catalogue)
    total, setup = priced["monthly_total_inr"], priced["setup_total_inr"]
    explanation, exp_status = _explanation(profile, bundle, total, setup, lang, catalogue)

    a = s["answers"]
    gst = s.get("gst") or {}
    biz = db.get(Business, conv.business_id) if conv.business_id else None
    if not biz:
        biz = Business(user_id=user.id, segment=profile.segment, city_tier=profile.city_tier, employees=profile.employees, sites=profile.sites)
        db.add(biz)
    biz.segment, biz.city_tier, biz.employees, biz.sites = profile.segment, profile.city_tier, profile.employees, profile.sites
    biz.city, biz.state = a["city"].get("city"), a["city"].get("state") or gst.get("state")
    biz.current_internet = a.get("internet")
    biz.has_gstin = 1 if gst.get("has_gstin") else 0
    biz.gst_status = gst.get("status") or "None"
    if s.get("_gstin_enc"):
        biz.gstin_enc, biz.gstin_masked = s["_gstin_enc"].encode(), gst.get("masked")
        if gst.get("trade_name"):
            biz.name = gst["trade_name"]
    wanted = [pid for need in profile.needs for pid in NEED_PRODUCTS.get(need, [])]
    biz.products_of_interest = json.dumps(sorted(set(wanted)))
    biz.updated_at = now_iso()
    db.flush()
    conv.business_id = biz.id
    lead = db.get(Lead, conv.lead_id) if conv.lead_id else None
    if lead:
        lead.business_id, lead.segment, lead.city, lead.city_tier, lead.state = biz.id, biz.segment, biz.city, biz.city_tier, biz.state
        lead.employee_count, lead.num_sites, lead.has_gstin = biz.employees, biz.sites, "Y" if biz.has_gstin else "N"
        lead.current_internet, lead.products_of_interest, lead.advisor_outcome = biz.current_internet, ";".join(sorted(set(wanted))), "quoted"

    def core_out(core):
        return [{"product_id": p, "name": _name(p, catalogue), "qty": q, "role": "core", "why": _why(p, lang),
                 "what_it_does": text(lang, "products")[p]} for p, q in core]

    def addon_out(addons):
        return [{"product_id": p, "name": _name(p, catalogue), "qty": q, "role": "addon", "why": _why(p, lang),
                 "what_it_does": text(lang, "products")[p], "monthly_inr": price([(p, q)], profile.key, catalogue)["monthly_total_inr"]}
                for p, q in addons]

    items_out, addons_out = core_out(bundle["core"]), addon_out(bundle["addons"])
    blocked_out = [{"product_id": pid, "name": _name(pid, catalogue), "reasons": [v["message"] for v in vs], "unlock": _unlock(vs[0], lang)}
                   for pid, vs in bundle["blocked"].items() if pid in bundle["wanted_blocked"]]
    rec = Recommendation(conversation_id=conv.id, business_id=biz.id, bundle_key=bundle["key"],
                         items=json.dumps([{"product_id": p, "qty": q, "role": "core"} for p, q in bundle["core"]] +
                                          [{"product_id": p, "qty": q, "role": "addon"} for p, q in bundle["addons"]]),
                         blocked=json.dumps([{"product_id": b["product_id"], "reasons": b["reasons"]} for b in blocked_out]),
                         explanation=explanation, rules_version=rules_version())
    db.add(rec)
    db.flush()

    # Alternative plans (cheaper, faster, growth, security, complete). Each is its own rules-checked
    # Recommendation, so a quote can be opened from any of them; bundle_key "<segment>:<option>" keeps
    # them apart from the main recommendation.
    options = []
    for opt in plan_options(profile, catalogue, bundle):
        op = price(opt["core"], profile.key, catalogue)
        if opt["key"] == "recommended":
            oid = rec.id
        else:
            alt = Recommendation(conversation_id=conv.id, business_id=biz.id, bundle_key=f"{bundle['key']}:{opt['key']}",
                                 items=json.dumps([{"product_id": p, "qty": q, "role": "core"} for p, q in opt["core"]] +
                                                  [{"product_id": p, "qty": q, "role": "addon"} for p, q in opt["addons"]]),
                                 blocked=rec.blocked, explanation="", rules_version=rec.rules_version)
            db.add(alt)
            db.flush()
            oid = alt.id
        options.append({"key": opt["key"], "recommended": opt["key"] == "recommended", "recommendation_id": oid,
                        "items": core_out(opt["core"]), "addons": addon_out(opt["addons"]),
                        "monthly_total_inr": op["monthly_total_inr"], "setup_total_inr": op["setup_total_inr"],
                        "contract_months": op["contract_months"], "max_install_days": op["max_install_days"]})
    conv.status = "recommended"
    _msg(db, conv, "assistant", explanation, status=exp_status)
    db.commit()
    return {"options": options, "recommendation_id": rec.id, "bundle_key": bundle["key"], "bundle_name": bundle["name"], "items": items_out, "addons": addons_out,
            "blocked": blocked_out, "explanation": explanation, "monthly_total_inr": total, "setup_total_inr": setup,
            "contract_months": priced["contract_months"], "max_install_days": priced["max_install_days"], "pricing_rule": priced["pricing_rule"],
            "rules_version": rec.rules_version, "source": source}


def get(db: Session, user: User, conversation_id: str) -> dict:
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.user_id != user.id:
        raise ApiError(404, "CONVERSATION_NOT_FOUND", "This conversation was not found.")
    msgs = db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at, Message.id)).all()
    rec = db.scalar(select(Recommendation).where(Recommendation.conversation_id == conv.id, Recommendation.bundle_key.not_like("%:%"))
                    .order_by(Recommendation.created_at.desc()))
    s = _state(conv)
    return {"conversation": {"id": conv.id, "status": conv.status, "language": conv.language, "questions_asked": conv.questions_asked,
                             "failed_turns": conv.failed_turns, "profile": public_profile(s)},
            "messages": [{"role": m.role, "content": m.content, "modality": m.modality, "created_at": m.created_at} for m in msgs],
            "recommendation": None if not rec else {"recommendation_id": rec.id, "bundle_key": rec.bundle_key, "items": json.loads(rec.items),
                                                    "blocked": json.loads(rec.blocked), "explanation": rec.explanation},
            "next_question": _question(_next_field(s), conv.language, s) if _next_field(s) and conv.status == "active" else None}
