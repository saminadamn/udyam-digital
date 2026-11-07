"""Phase 3 in a 360px browser: consent first, GSTIN lookup, 4 real uploads, results for a clean, a stale-bill and a mismatched applicant."""
import random
import re
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])
DB = sys.argv[2]
OUT.mkdir(parents=True, exist_ok=True)
DOCS = Path(__file__).resolve().parents[1] / "data" / "kyc_documents"
BASE = "http://localhost:3000"
TYPES = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]
RAW = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]")
report, problems = [], []


def layout(page, name):
    bad = page.evaluate("""() => {
      const out = [];
      if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push('horizontal overflow');
      for (const el of document.querySelectorAll('button, a, input[type=checkbox], label')) {
        const r = el.getBoundingClientRect();
        const lab = el.closest('label');
        if (lab && lab.getBoundingClientRect().height >= 44) continue;
        if (r.width && r.height && r.height < 44 && !el.classList.contains('sr-only') && el.offsetParent !== null && el.tagName !== 'LABEL') out.push(el.tagName + ' ' + (el.innerText || el.getAttribute('aria-label') || '').slice(0, 30) + ' ' + Math.round(r.height));
      }
      return out;
    }""")
    text = page.inner_text("body")
    if RAW.search(text):
        bad.append("raw GSTIN on screen: " + RAW.search(text).group())
    if bad:
        problems.append(f"{name}: {bad}")


def login_and_order(page, lang_label="English"):
    page.goto(BASE)
    page.get_by_role("radio", name=re.compile(lang_label)).click()
    page.locator("button.btn-primary").first.click()
    page.wait_for_url("**/login")
    page.fill("#phone", f"96{random.randint(10**7, 10**8 - 1)}")
    page.locator("button.btn-primary").first.click()
    code = re.search(r"\d{6}", page.get_by_role("status").first.inner_text()).group()
    page.fill("#otp", code)
    page.locator("button.btn-primary").first.click()
    page.wait_for_url("**/advisor")
    page.wait_for_selector("text=Thinking…", state="detached")


def advisor_micro(page):
    def tap(label):
        page.get_by_role("button", name=label, exact=True).click()
        page.wait_for_timeout(100)
        page.wait_for_selector("text=Thinking…", state="detached")

    page.get_by_role("button", name="Shop or small service", exact=True).wait_for()
    for a in ["Shop or small service", "1-5 people", "Lucknow", "No GST yet", "Mobile hotspot"]:
        tap(a)
    page.get_by_role("button", name="UPI and billing", exact=True).click()
    page.get_by_role("button", name=re.compile("^Done")).click()
    page.get_by_role("button", name="See my plan").click()
    page.wait_for_url("**/advisor/recommendation**")
    page.get_by_role("button", name="See price and continue").click()
    page.wait_for_url("**/quote/**")
    page.get_by_role("button", name=re.compile("Accept and order")).click()
    page.get_by_test_id("continue-kyc").click()
    page.wait_for_url("**/consent")


def consent(page, shot=None):
    page.get_by_test_id("notice").wait_for()
    page.get_by_test_id("consent-continue").click()
    assert page.locator("main ~ div [role=alert]").inner_text().strip(), "no warning without the tick"
    if shot:
        page.screenshot(path=OUT / shot, full_page=True)
        layout(page, shot)
    page.get_by_test_id("agree").check()
    page.get_by_test_id("consent-continue").click()
    page.wait_for_url("**/kyc")


def upload_all(page, applicant, shot=None):
    for t in TYPES:
        f = DOCS / f"{applicant}_{t}.png"
        page.get_by_test_id(f"file-{t}").set_input_files(str(f))
        page.wait_for_selector(f"[data-testid=tile-{t}]:not([data-state=busy]):not([data-state=empty])", timeout=30000)
    if shot:
        page.screenshot(path=OUT / shot, full_page=True)
        layout(page, shot)


def result(page, shot):
    page.get_by_test_id("kyc-submit").click()
    page.wait_for_selector("[data-testid=kyc-result]:not([data-verdict=''])", timeout=60000)
    page.wait_for_timeout(300)
    page.screenshot(path=OUT / shot, full_page=True)
    layout(page, shot)
    return page.get_by_test_id("kyc-result").get_attribute("data-verdict")


def order_state(page):
    oid = re.search(r"/order/([^/]+)/kyc", page.url).group(1)
    con = sqlite3.connect(DB)
    st = con.execute("select state from orders where id=?", (oid,)).fetchone()[0]
    esc = con.execute("select trigger, priority, required_skill from escalations e join kyc_cases k on k.id=e.kyc_case_id where k.order_id=? and e.status in ('open','assigned')", (oid,)).fetchall()
    consent = con.execute("select purpose, notice_version, granted_at from consents where order_id=?", (oid,)).fetchone()
    return oid, st, esc, consent


if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        errors = []

        ctx = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2)
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        login_and_order(page)
        advisor_micro(page)
        consent(page, "c6_consent.png")
        oid, st, esc, cons = order_state(page)
        report.append(f"K02: consent stored {cons}; order {st}")
        page.fill("#gstin", "19EOGXH4115Y1ZM")
        page.wait_for_timeout(100)
        page.screenshot(path=OUT / "c7a_gstin_checksum_error.png")
        page.fill("#gstin", "19EOGXH4115Y1ZL")
        page.get_by_role("button", name="Check", exact=True).first.click()
        page.get_by_test_id("gstin-card").wait_for()
        page.screenshot(path=OUT / "c7a_gstin_found.png", full_page=True)
        layout(page, "c7a_gstin_found.png")
        report.append("K02 GSTIN card: " + page.get_by_test_id("gstin-card").inner_text().replace("\n", " | "))
        page.get_by_test_id("kyc-next").click()
        upload_all(page, "K02", "c7b_uploads_k02.png")
        v = result(page, "c7c_verified_k02.png")
        oid, st, esc, _ = order_state(page)
        report.append(f"K02: verdict {v}, order {st}, escalations {esc}")
        assert v == "verified" and st == "INSTALL_BOOKED"
        ctx.close()

        ctx = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2)
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        login_and_order(page)
        advisor_micro(page)
        consent(page)
        page.get_by_role("button", name="I don't have my GSTIN handy").click()
        upload_all(page, "K11", "c7b_uploads_k11_stale_bill.png")
        report.append("K11 address tile on upload: " + page.get_by_test_id("tile-address_proof").inner_text().replace("\n", " | "))
        v = result(page, "c7c_reupload_k11.png")
        oid, st, esc, _ = order_state(page)
        report.append(f"K11: verdict {v}, order {st}, escalations {esc}")
        report.append("K11 fix list: " + page.get_by_test_id("fix-list").inner_text().replace("\n", " | "))
        assert v == "reupload" and st == "KYC_FLAGGED" and esc
        page.get_by_role("button", name=re.compile("^Re-upload")).click()
        page.wait_for_timeout(300)
        page.screenshot(path=OUT / "c7b_reupload_focus_k11.png", full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2)
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        login_and_order(page)
        advisor_micro(page)
        page.locator("header select").select_option("hi")
        page.get_by_test_id("notice").wait_for()
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "c6_consent_hi.png", full_page=True)
        layout(page, "c6_consent_hi.png")
        page.get_by_test_id("agree").check()
        page.get_by_test_id("consent-continue").click()
        page.wait_for_url("**/kyc")
        page.locator("#udyam").wait_for()
        page.locator("main button.btn-ghost").last.click()
        upload_all(page, "K06")
        v = result(page, "c7c_review_k06_hi.png")
        oid, st, esc, _ = order_state(page)
        report.append(f"K06 (Hindi): verdict {v}, order {st}, escalations {esc}")
        report.append("K06 banner: " + page.get_by_test_id("kyc-result").inner_text().split("\n")[0:3].__str__())
        assert v == "review" and st == "HUMAN_REVIEW" and esc[0][1] == "P1"
        ctx.close()
        browser.close()

    report.append(f"page errors: {errors or 'none'}")
    report.append(f"layout/masking problems: {problems or 'none'}")
    (OUT / "e2e_report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    sys.exit(1 if errors or problems else 0)
