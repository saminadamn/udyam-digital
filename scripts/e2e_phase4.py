"""Phase 4 end to end: a verified order is booked, made late in the simulator, the SLA job escalates it on its own,
the customer's tracker names the person, the agent sees full context and rebooks, and the customer can ask for a call."""
import re
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_phase3 import DOCS, TYPES, advisor_micro, consent, layout, login_and_order, problems  # noqa: E402

OUT = Path(sys.argv[1])
DB = sys.argv[2]
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:3000"
AGENT_PHONE = {"Priya": "9000000101", "Arjun": "9000000102", "Meera": "9000000103", "Sanjay": "9000000104", "Kavya": "9000000105"}
report = []


def staff_login(page, phone):
    page.goto(BASE + "/login")
    page.fill("#phone", phone)
    page.locator("button.btn-primary").first.click()
    code = re.search(r"\d{6}", page.get_by_role("status").first.inner_text()).group()
    page.fill("#otp", code)
    page.locator("button.btn-primary").first.click()
    page.wait_for_url(re.compile(r".*/admin/(escalations|leads)$"))  # admins land on leads since Phase 5


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    errors = []

    cust = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2)
    c = cust.new_page()
    c.on("pageerror", lambda e: errors.append(str(e)))
    login_and_order(c)
    advisor_micro(c)
    consent(c)
    c.get_by_role("button", name="I don't have my GSTIN handy").click()
    for t in TYPES:
        c.get_by_test_id(f"file-{t}").set_input_files(str(DOCS / f"K02_{t}.png"))
        c.wait_for_selector(f"[data-testid=tile-{t}]:not([data-state=busy]):not([data-state=empty])", timeout=30000)
    c.get_by_test_id("kyc-submit").click()
    c.get_by_test_id("track-order").click(timeout=60000)
    c.wait_for_url(re.compile(r"/order/[^/]+$"))
    c.get_by_test_id("timeline").wait_for()
    order_id = c.url.rsplit("/", 1)[1]
    display = c.inner_text("main p").split("·")[-1].strip()
    statuses = [c.get_by_test_id(f"step-{k}").get_attribute("data-status") for k in ("KYC_VERIFIED", "INSTALL_BOOKED", "INSTALLED", "LIVE")]
    visit = c.get_by_test_id("step-INSTALL_BOOKED").inner_text().replace("\n", " | ")
    report.append(f"{display}: tracker after KYC {statuses}; {visit}")
    assert statuses == ["done", "current", "upcoming", "upcoming"] and "Technician visit on" in visit
    c.screenshot(path=OUT / "c9_tracker_booked.png", full_page=True)
    layout(c, "c9_tracker_booked.png")

    adm = browser.new_context(viewport={"width": 1280, "height": 860})
    a = adm.new_page()
    a.on("pageerror", lambda e: errors.append(str(e)))
    staff_login(a, "9000000001")
    a.goto(BASE + "/admin/simulator")
    a.get_by_role("button", name=re.compile(display)).click()
    a.wait_for_selector(f"[data-testid=sim-panel] >> text={display}")
    a.fill("#late", "30")
    a.get_by_test_id("make-late").click()
    t0 = time.time()
    report.append(f"{display}: made 30 h late in the simulator; waiting for the SLA job (no manual scan)")

    banner = None
    for _ in range(30):
        c.reload()
        c.get_by_test_id("timeline").wait_for()
        if c.get_by_test_id("human-banner").count():
            banner = c.get_by_test_id("human-message").inner_text()
            break
        time.sleep(2)
    assert banner, "SLA job did not escalate within 60 s"
    report.append(f"{display}: auto-escalated after {time.time() - t0:.0f} s; tracker says: {banner!r}")
    delay = c.get_by_test_id("delay-banner").inner_text()
    report.append(f"{display}: delay banner: {delay!r}")
    assert re.match(r"^\w+ from Accel will call you by \d", banner)
    c.screenshot(path=OUT / "c9_tracker_delayed_escalated.png", full_page=True)
    layout(c, "c9_tracker_delayed_escalated.png")
    a.wait_for_timeout(5500)
    a.screenshot(path=OUT / "a7_simulator.png", full_page=True)

    con = sqlite3.connect(DB)
    row = con.execute("select e.trigger, e.priority, e.required_skill, g.name, g.languages, e.reason from escalations e join agents g on g.id=e.assigned_agent_id "
                      "where e.order_id=? and e.status in ('open','assigned')", (order_id,)).fetchone()
    report.append(f"{display}: escalation row {row[:5]}; reason {row[5]!r}")
    agent_first = banner.split()[0]

    ag = browser.new_context(viewport={"width": 1280, "height": 900})
    g = ag.new_page()
    g.on("pageerror", lambda e: errors.append(str(e)))
    staff_login(g, AGENT_PHONE[agent_first])
    g.get_by_test_id("queue").wait_for()
    g.screenshot(path=OUT / "a4_agent_queue.png", full_page=True)
    g.get_by_role("link", name=re.compile(f"Late order · {display}")).click()
    g.get_by_test_id("case-header").wait_for()
    for panel in ("panel-business", "panel-chat", "panel-quote", "panel-order", "panel-kyc"):
        assert g.get_by_test_id(panel).count(), panel
    told = g.get_by_test_id("customer-told").inner_text()
    report.append(f"agent {agent_first}: case shows business, chat, plan, order timeline and KYC; customer was told {told}")
    chat = g.get_by_test_id("panel-chat").locator("p").first.inner_text()
    report.append(f"agent view chat {chat!r}")
    g.screenshot(path=OUT / "a5_agent_case.png", full_page=True)
    g.get_by_role("button", name="Rebook install (tomorrow)").click()
    g.get_by_label("Resolution note").fill("Technician was off sick. Rebooked for tomorrow, customer agreed.")
    g.get_by_role("button", name="Resolve", exact=True).click()
    g.wait_for_selector("text=Note: Technician was off sick")
    g.screenshot(path=OUT / "a5_agent_case_resolved.png", full_page=True)

    c.reload()
    c.get_by_test_id("timeline").wait_for()
    assert not c.get_by_test_id("delay-banner").count() and not c.get_by_test_id("human-banner").count()
    report.append(f"{display}: after rebook: " + c.get_by_test_id("step-INSTALL_BOOKED").inner_text().replace("\n", " | "))
    c.screenshot(path=OUT / "c9_tracker_rebooked.png", full_page=True)

    c.get_by_test_id("talk").click()
    c.get_by_test_id("talk-sheet").wait_for()
    c.get_by_role("button", name="Evening").click()
    c.screenshot(path=OUT / "c10_talk_sheet.png")
    layout(c, "c10_talk_sheet.png")
    c.get_by_test_id("talk-send").click()
    c.get_by_test_id("human-banner").wait_for()
    report.append(f"{display}: talk to a person -> {c.get_by_test_id('human-message').inner_text()!r}")
    c.locator("header select").select_option("hi")
    c.wait_for_timeout(1200)
    report.append(f"{display}: in Hindi -> {c.get_by_test_id('human-message').inner_text()!r}")
    c.screenshot(path=OUT / "c9_tracker_hi.png", full_page=True)
    layout(c, "c9_tracker_hi.png")
    browser.close()

report.append(f"page errors: {errors or 'none'}")
report.append(f"layout/masking problems: {problems or 'none'}")
(OUT / "e2e_report.txt").write_text("\n".join(report) + "\n")
print("\n".join(report))
sys.exit(1 if errors or problems else 0)
