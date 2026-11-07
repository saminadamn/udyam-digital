"""The happy path on a phone, end to end (DESIGN.md D6.1 tests/e2e): language -> OTP login (WhatsApp opt-in) -> advisor ->
recommendation -> quote -> accept -> consent -> GSTIN lookup -> 4 real document uploads -> verified -> install booked -> live.

Runs against local servers by default; point it at a deployment to check the live link:
    python scripts/e2e_happy_path.py out/                                   # localhost:3000 + localhost:8000
    E2E_WEB=https://udyam.vercel.app E2E_API=https://udyam-api.onrender.com/api/v1 python scripts/e2e_happy_path.py out/
Moving the order from booked to installed to live uses the admin simulator API (the technician's part), as in the demo."""
import os
import random
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

WEB = os.environ.get("E2E_WEB", "http://localhost:3000").rstrip("/")
API = os.environ.get("E2E_API", "http://localhost:8000/api/v1").rstrip("/")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "e2e_out")
OUT.mkdir(parents=True, exist_ok=True)
DOCS = Path(__file__).resolve().parents[1] / "data" / "kyc_documents"
TYPES = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]
RAW_GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]")
steps, errors = [], []


def step(name, page):
    page.screenshot(path=OUT / f"{len(steps) + 1:02d}_{name}.png", full_page=True)
    body = page.inner_text("body")
    assert not RAW_GSTIN.search(body), f"raw GSTIN on screen at {name}"
    wide = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
    assert not wide, f"horizontal scroll at {name}"
    steps.append(f"{name}: ok ({page.url.replace(WEB, '')})")
    print(steps[-1], flush=True)


def tap(page, label):
    page.get_by_role("button", name=label, exact=True).click()
    page.wait_for_timeout(150)
    page.wait_for_selector("text=Thinking…", state="detached")


def admin_headers():
    r = httpx.post(f"{API}/auth/otp/request", json={"phone": "9000000001"}, timeout=30).json()
    if "dev_code" not in r:
        raise SystemExit("OTP_MODE must be mock for the demo admin login")
    t = httpx.post(f"{API}/auth/otp/verify", json={"request_id": r["request_id"], "code": r["dev_code"], "language": "en"}, timeout=30).json()["token"]
    return {"Authorization": f"Bearer {t}"}


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get("CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    ctx = browser.new_context(**p.devices["Pixel 5"])  # 393x851 phone, touch, mobile user agent
    page = ctx.new_page()
    page.set_default_timeout(60_000)  # free-tier hosting can cold-start
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(WEB)
    page.get_by_role("radio", name=re.compile("English")).click()
    step("language", page)
    page.locator("button.btn-primary").first.click()
    page.wait_for_url("**/login")
    page.fill("#phone", f"95{random.randint(10**7, 10**8 - 1)}")
    expect(page.get_by_role("checkbox")).to_be_checked()
    page.locator("button.btn-primary").first.click()
    code = re.search(r"\d{6}", page.get_by_role("status").first.inner_text()).group()
    page.fill("#otp", code)
    step("otp", page)
    page.locator("button.btn-primary").first.click()
    page.wait_for_url("**/advisor")
    page.wait_for_selector("text=Thinking…", state="detached")

    for a in ["Shop or small service", "1-5 people", "Lucknow"]:
        tap(page, a)
    page.fill("input.field", "19EOGXH4115Y1ZL")
    page.get_by_role("button", name="Send").click()
    page.wait_for_timeout(150)
    page.wait_for_selector("text=Thinking…", state="detached")
    tap(page, "Home broadband")
    page.get_by_role("button", name="UPI and billing", exact=True).click()
    page.get_by_role("button", name=re.compile("^Done")).click()
    page.get_by_role("button", name="See my plan").wait_for()
    step("advisor", page)
    page.get_by_role("button", name="See my plan").click()
    page.wait_for_url("**/advisor/recommendation**")
    step("recommendation", page)
    page.get_by_role("button", name="See price and continue").click()
    page.wait_for_url("**/quote/**")
    step("quote", page)
    page.get_by_role("button", name=re.compile("Accept and order")).click()
    page.get_by_test_id("continue-kyc").click()
    page.wait_for_url("**/consent")
    oid = re.search(r"/order/([^/]+)/consent", page.url).group(1)
    page.get_by_test_id("notice").wait_for()
    page.get_by_test_id("agree").check()
    step("consent", page)
    page.get_by_test_id("consent-continue").click()
    page.wait_for_url("**/kyc")

    page.fill("#gstin", "19EOGXH4115Y1ZL")
    page.get_by_role("button", name="Check", exact=True).first.click()
    page.get_by_test_id("gstin-card").wait_for()
    step("gstin_found", page)
    page.get_by_test_id("kyc-next").click()
    for t in TYPES:
        page.get_by_test_id(f"file-{t}").set_input_files(str(DOCS / f"K02_{t}.png"))
        page.wait_for_selector(f"[data-testid=tile-{t}]:not([data-state=busy]):not([data-state=empty])", timeout=90_000)
    step("uploads", page)
    page.get_by_test_id("kyc-submit").click()
    page.wait_for_selector("[data-testid=kyc-result]:not([data-verdict=''])", timeout=90_000)
    assert page.get_by_test_id("kyc-result").get_attribute("data-verdict") == "verified"
    step("kyc_verified", page)

    page.goto(f"{WEB}/order/{oid}")
    page.get_by_test_id("headline").wait_for()
    expect(page.locator("main")).to_contain_text("Technician visit on")
    step("tracker_booked", page)

    adm = admin_headers()
    for st in ("INSTALLED", "LIVE"):
        r = httpx.post(f"{API}/admin/orders/{oid}/advance", json={"to_state": st}, headers=adm, timeout=30)
        assert r.status_code == 200, r.text
    page.reload()
    expect(page.get_by_test_id("headline")).to_contain_text("live", timeout=30_000)
    page.get_by_test_id("updates").wait_for()
    step("tracker_live", page)
    browser.close()

steps.append(f"page errors: {errors or 'none'}")
(OUT / "report.txt").write_text("\n".join(steps) + "\n")
print(steps[-1])
sys.exit(1 if errors else 0)
