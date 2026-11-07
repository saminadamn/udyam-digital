import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:3000"
HI = json.load(open(Path(__file__).resolve().parents[1] / "backend" / "app" / "i18n" / "advisor_en_hi.json", encoding="utf-8"))["hi"]
report = []


def overflow(page, name):
    w = page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    report.append(f"{name}: scrollWidth={w[0]} viewport={w[1]} {'OK' if w[0] <= w[1] else 'OVERFLOW'}")
    small = page.evaluate("""() => [...document.querySelectorAll('button, a, input, select')]
        .filter(e => e.offsetParent && !e.disabled && e.type !== 'checkbox')
        .map(e => [e.innerText || e.getAttribute('aria-label') || e.type, Math.round(e.getBoundingClientRect().height)])
        .filter(([, h]) => h < 44)""")
    report.append(f"{name}: tap targets under 44px: {small or 'none'}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2, locale="hi-IN")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))

    page.goto(BASE)
    page.get_by_role("radio", name=re.compile("हिंदी")).click()
    page.wait_for_timeout(300)
    overflow(page, "C1 language")
    page.screenshot(path=OUT / "c1_language.png")
    page.get_by_role("button", name="आगे बढ़ें").click()

    page.wait_for_url("**/login")
    import random
    page.fill("#phone", f"98{random.randint(10**7, 10**8 - 1)}")
    overflow(page, "C2 login")
    page.screenshot(path=OUT / "c2_login_phone.png")
    page.get_by_role("button", name="OTP भेजें").click()
    banner = page.get_by_role("status").first
    banner.wait_for()
    code = re.search(r"\d{6}", banner.inner_text()).group()
    page.fill("#otp", code)
    page.screenshot(path=OUT / "c2_login_otp.png")
    page.get_by_role("button", name="पुष्टि करें और आगे बढ़ें").click()

    page.wait_for_url("**/advisor")
    page.get_by_role("button", name=HI["chips_type"][1]).wait_for()
    overflow(page, "C3 advisor (start)")
    page.screenshot(path=OUT / "c3_chat_start.png")

    def chip(label):
        page.get_by_role("button", name=label, exact=True).click()
        page.wait_for_timeout(150)
        page.wait_for_selector("text=सोच रहे हैं…", state="detached")

    chip(HI["chips_type"][1])
    chip(HI["chips_team"][1])
    chip("Pune")
    page.fill("input[aria-label]", "32TTNXB7384T1ZW")
    page.get_by_role("button", name="भेजें", exact=True).click()
    page.wait_for_selector("text=सोच रहे हैं…", state="detached")
    chip(HI["chips_internet"][2])
    page.get_by_role("button", name=HI["chips_needs"][3], exact=True).click()
    page.get_by_role("button", name=HI["chips_needs"][5], exact=True).click()
    page.get_by_role("button", name=HI["chips_needs"][7], exact=True).click()
    page.screenshot(path=OUT / "c3_chat_needs.png")
    page.get_by_role("button", name=re.compile(HI["chip_done"])).click()
    page.get_by_role("button", name="मेरा प्लान देखें").wait_for()
    overflow(page, "C3 advisor (done)")
    page.screenshot(path=OUT / "c3_chat_done.png", full_page=True)
    page.get_by_role("button", name="मेरा प्लान देखें").click()

    page.wait_for_url("**/advisor/recommendation**")
    page.get_by_text("आपके लिए सुझाया गया प्लान").wait_for()
    page.wait_for_selector("text=प्रति माह")
    overflow(page, "C4 recommendation")
    page.screenshot(path=OUT / "c4_recommendation.png", full_page=True)
    text = page.inner_text("main")
    report.append("C4 has product code: " + str(bool(re.search(r"\bP\d{2}\b", text))))
    report.append("C4 text excerpt: " + text[:400].replace("\n", " | "))

    page.goto(BASE)
    page.get_by_role("radio", name=re.compile("தமிழ்")).click()
    page.get_by_role("button", name="தொடரவும்").click()
    page.wait_for_url("**/advisor")
    page.wait_for_timeout(800)
    page.screenshot(path=OUT / "c3_tamil_resume.png")
    report.append("JS errors: " + (json.dumps(errors[:5], ensure_ascii=False) if errors else "none"))
    browser.close()

(OUT / "e2e_report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
