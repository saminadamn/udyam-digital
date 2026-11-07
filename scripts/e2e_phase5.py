"""Phase 5 end to end, one demo run (build Phase 5 "done when"):
  1. voice chat: a Hindi-speaking owner answers all six advisor questions by holding the mic; replies are read back, short;
  2. WhatsApp: the owner opted in at login, accepts the quote, and the quote_ready message is in the outbox;
  3. admin: the leads dashboard with the live metrics strip, "High propensity, not contacted", and a Call logged with its outcome.

Headless Chrome has no microphone or speech service, so the page gets a scripted SpeechRecognition (it "hears" the strings below)
and a speechSynthesis spy that records what would be spoken. Everything after the transcript is the real app and API.

Usage: python scripts/e2e_phase5.py docs/screenshots/phase5 backend/udyam.db   (both servers running)"""
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_phase3 import layout, problems  # noqa: E402

OUT = Path(sys.argv[1])
DB = sys.argv[2]
OUT.mkdir(parents=True, exist_ok=True)
BASE, API = "http://localhost:3000", "http://localhost:8000/api/v1"
HI = json.loads((Path(__file__).resolve().parents[1] / "frontend" / "messages" / "hi.json").read_text(encoding="utf-8"))
SPOKEN_ANSWERS = ["मेरी दुकान है", "3 लोग", "लखनऊ", "अभी GST नहीं है", "मोबाइल हॉटस्पॉट", "UPI और बिलिंग, और CCTV कैमरे"]
report = []

FAKE_SPEECH = """
(() => {
  window.__spoken = []; window.__heard = []; window.__voiceQueue = [];
  class FakeRecognition {
    constructor() { this.lang = ''; this.interimResults = false; this.continuous = false; this.onresult = null; this.onerror = null; this.onend = null; }
    start() {
      const text = window.__voiceQueue.shift() || '';
      window.__heard.push({ text, lang: this.lang });
      setTimeout(() => { if (text && this.onresult) { const alt = [{ transcript: text }]; alt.isFinal = true; this.onresult({ results: [alt] }); } }, 120);
      setTimeout(() => this.onend && this.onend(), 260);
    }
    stop() {}
  }
  window.SpeechRecognition = FakeRecognition; window.webkitSpeechRecognition = FakeRecognition;
  const s = window.speechSynthesis;
  s.speak = (u) => window.__spoken.push({ text: u.text, lang: u.lang });
  s.cancel = () => {};
  s.getVoices = () => [{ lang: 'hi-IN', name: 'Test Hindi' }, { lang: 'en-IN', name: 'Test English' }];
})();
"""


def db():
    return sqlite3.connect(DB)


def otp_login(page, phone, shot=None):
    page.fill("#phone", phone)
    if shot:
        assert page.get_by_role("checkbox").is_checked(), "WhatsApp opt-in should be ticked by default (C2)"
        page.screenshot(path=OUT / shot, full_page=True)
        layout(page, shot)
    page.locator("button.btn-primary").first.click()
    code = re.search(r"\d{6}", page.get_by_role("status").first.inner_text()).group()
    page.fill("#otp", code)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    errors = []

    # 1. Voice chat in Hindi ------------------------------------------------------------------------------------------
    cust = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2, locale="hi-IN")
    cust.add_init_script(FAKE_SPEECH)
    c = cust.new_page()
    c.on("pageerror", lambda e: errors.append(str(e)))
    c.goto(BASE)
    c.get_by_role("radio", name=re.compile("हिंदी")).click()
    c.locator("button.btn-primary").first.click()
    c.wait_for_url("**/login")
    phone = f"97{random.randint(10**7, 10**8 - 1)}"
    otp_login(c, phone, "c2_login_whatsapp_optin.png")
    c.locator("button.btn-primary").first.click()
    c.wait_for_url("**/advisor")
    c.wait_for_selector(f"text={HI['chat']['thinking']}", state="detached")

    mic = c.locator("button[data-engine]")
    mic.wait_for()
    assert mic.get_attribute("data-engine") == "browser"
    for said in SPOKEN_ANSWERS:
        c.evaluate("t => window.__voiceQueue.push(t)", said)
        with c.expect_response("**/advisor/message") as resp:
            mic.hover()
            c.mouse.down()
            c.wait_for_timeout(350)
            c.mouse.up()
        body = resp.value.json()
        assert body["escalation"] is None, body
        c.wait_for_timeout(150)
    c.wait_for_selector(f"text={HI['chat']['see_plan']}")
    spoken = c.evaluate("window.__spoken")
    heard = c.evaluate("window.__heard")
    assert len(spoken) == len(SPOKEN_ANSWERS), spoken
    assert all(s["lang"] == "hi-IN" and len(s["text"]) <= 180 for s in spoken), spoken
    assert all(h["lang"] == "hi-IN" for h in heard)
    assert c.get_by_role("checkbox", name=HI["chat"]["read_aloud"]).is_checked(), "read-aloud turns on after a spoken answer"
    c.screenshot(path=OUT / "c3_voice_chat_hi.png", full_page=True)
    layout(c, "c3_voice_chat_hi.png")
    con = db()
    cid = con.execute("select c.id, c.channel from conversations c join messages m on m.conversation_id=c.id where m.content=? order by c.created_at desc limit 1",
                      (SPOKEN_ANSWERS[-1],)).fetchone()
    voice_msgs = con.execute("select count(*) from messages where conversation_id=? and role='user' and modality='voice'", (cid[0],)).fetchone()[0]
    assert cid[1] == "voice" and voice_msgs == len(SPOKEN_ANSWERS)
    report.append(f"voice: {voice_msgs} answers spoken in Hindi (recognition lang {heard[0]['lang']}), conversation channel={cid[1]}")
    for s in spoken:
        report.append(f"  read aloud ({len(s['text'])} chars): {s['text']}")

    # 2. Quote accepted -> WhatsApp in the outbox ----------------------------------------------------------------------
    c.get_by_role("button", name=HI["chat"]["see_plan"]).click()
    c.wait_for_url("**/advisor/recommendation**")
    c.get_by_role("button", name=HI["rec"]["next"]).click()
    c.wait_for_url("**/quote/**")
    c.get_by_role("button", name=re.compile(HI["quote"]["accept"])).click()
    c.get_by_test_id("continue-kyc").wait_for()
    oid = re.search(r"/order/([^/]+)/consent", c.get_by_test_id("continue-kyc").get_attribute("href")).group(1)
    row = con.execute("select status, provider_ref, payload, language from notifications where order_id=? and channel='whatsapp' and template='quote_ready'",
                      (oid,)).fetchone()
    assert row and row[0] == "sent" and row[1].startswith("mock-wa-") and row[3] == "hi", row
    preview = json.loads(row[2])["preview"]
    report.append(f"whatsapp: quote_ready {row[0]} via {row[1]}: {preview}")
    c.goto(f"{BASE}/order/{oid}")
    c.get_by_test_id("updates").wait_for()
    c.screenshot(path=OUT / "c9_tracker_updates_hi.png", full_page=True)
    layout(c, "c9_tracker_updates_hi.png")

    # An owner who asks for a person in the advisor, so "Advisor could not close" has an app lead in it.
    r = httpx.post(f"{API}/auth/otp/request", json={"phone": f"96{random.randint(10**7, 10**8 - 1)}"}).json()
    tok = httpx.post(f"{API}/auth/otp/verify", json={"request_id": r["request_id"], "code": r["dev_code"], "language": "en", "whatsapp_opt_in": True}).json()["token"]
    hh = {"Authorization": f"Bearer {tok}"}
    conv = httpx.post(f"{API}/advisor/conversations", json={"language": "en", "lead_source": "Referral"}, headers=hh).json()["conversation_id"]
    httpx.post(f"{API}/advisor/message", json={"conversation_id": conv, "content": "Clinic or office"}, headers=hh)
    httpx.post(f"{API}/advisor/message", json={"conversation_id": conv, "content": "talk to a person"}, headers=hh)

    # 3. Admin: dashboard, outbox, call a high-propensity lead ----------------------------------------------------------
    adm = browser.new_context(viewport={"width": 1360, "height": 900})
    a = adm.new_page()
    a.on("pageerror", lambda e: errors.append(str(e)))
    a.goto(BASE + "/login")
    otp_login(a, "9000000001")
    a.locator("button.btn-primary").first.click()
    a.wait_for_url("**/admin/leads")
    a.get_by_test_id("metric-strip").wait_for()
    a.locator("[data-testid=leads] tbody tr").first.wait_for()
    tiles = {k: a.get_by_test_id(f"metric-{k}").inner_text().replace("\n", " | ")
             for k in ("lead_to_activation", "days_to_activate", "cac_per_activation", "churn_6m", "chase_calls_per_customer")}
    for k, v in tiles.items():
        report.append(f"metric {k}: {v}")
    assert "7.4%" in tiles["lead_to_activation"] and "17.6 d" in tiles["days_to_activate"] and "Rs 15,053" in tiles["cac_per_activation"]
    a.screenshot(path=OUT / "a2_leads_high_not_contacted.png", full_page=True)

    first = a.locator("[data-testid=leads] tbody tr").first
    lead_id = first.get_attribute("data-row")
    bucket = first.get_by_test_id("bucket").inner_text()
    assert bucket == "High"
    before = con.execute("select propensity_score, propensity_bucket, last_contacted_at from leads where lead_id=?", (lead_id,)).fetchone()
    assert before[1] == "High" and before[2] is None
    a.get_by_test_id(f"call-{lead_id}").click()
    panel = a.get_by_test_id("call-panel")
    a.get_by_test_id("call-status").wait_for()
    a.get_by_role("button", name="Interested", exact=True).click()
    a.get_by_label("Minutes").fill("3")
    a.get_by_label("Note (optional)").fill("Wants Office Pro; will finish KYC tonight")
    a.screenshot(path=OUT / "a3_call_outcome.png", full_page=True)
    a.get_by_test_id("save-outcome").click()
    a.get_by_test_id("call-saved").wait_for()
    call_id = panel.get_attribute("data-call")
    call = con.execute("select provider, outcome, duration_s, agent_id from call_logs where id=?", (call_id,)).fetchone()
    after = con.execute("select last_contacted_at, lead_status from leads where lead_id=?", (lead_id,)).fetchone()
    note = con.execute("select body from lead_notes where lead_id=? order by created_at desc", (lead_id,)).fetchone()
    assert call == ("mock", "interested", 180, None) and after[0] and after[1] == "contacted" and note
    report.append(f"call: {lead_id} (High, score {before[0]}) called from the dashboard -> call_logs {call}, lead {after}")
    a.get_by_role("button", name="Close").click()
    a.wait_for_timeout(400)
    assert lead_id not in [r.get_attribute("data-row") for r in a.locator("[data-testid=leads] tbody tr").all()], "called lead should leave the not-contacted list"

    a.get_by_test_id("preset-not_closed").click()
    a.wait_for_timeout(500)
    a.screenshot(path=OUT / "a2_leads_advisor_could_not_close.png", full_page=True)
    nc = a.locator("[data-testid=leads] tbody tr").count()
    report.append(f"'Advisor could not close': {nc} rows on screen, first: {a.locator('[data-testid=leads] tbody tr').first.inner_text()[:120]!r}")

    a.goto(f"{BASE}/admin/leads/{lead_id}")
    a.get_by_test_id("calls").wait_for()
    a.screenshot(path=OUT / "a3_lead_detail.png", full_page=True)
    a.goto(BASE + "/admin/notifications")
    a.locator("[data-testid=outbox] tbody tr").first.wait_for()
    a.screenshot(path=OUT / "a6_outbox.png", full_page=True)
    outbox = a.get_by_test_id("outbox").inner_text()
    assert preview.split(":", 1)[1].strip()[:20] in outbox, "the customer's quote_ready message is on the outbox screen"

    report.append(f"page errors: {errors or 'none'}")
    report.append(f"360px layout problems: {problems or 'none'}")
    browser.close()

(OUT / "e2e_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
print("\n".join(report))
assert not errors and not problems
