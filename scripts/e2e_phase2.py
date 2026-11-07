import random
import re
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])
DB = sys.argv[2]
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:3000"
report = []


def total(page) -> int:
    return int(re.sub(r"\D", "", page.get_by_test_id("monthly-total").inner_text().split("per")[0]))


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2)
    ctx.add_init_script("""
      const realFetch = window.fetch.bind(window);
      window.__delayItems = 0;
      window.fetch = async (input, init) => {
        const url = typeof input === 'string' ? input : input.url;
        if (window.__delayItems && /\/quotes\/[^/]+\/items\//.test(url)) await new Promise(r => setTimeout(r, window.__delayItems));
        return realFetch(input, init);
      };
    """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(BASE)
    page.get_by_role("radio", name=re.compile("English")).click()
    page.get_by_role("button", name="Continue").click()
    page.wait_for_url("**/login")
    page.fill("#phone", f"97{random.randint(10**7, 10**8 - 1)}")
    page.get_by_role("button", name="Send OTP").click()
    code = re.search(r"\d{6}", page.get_by_role("status").first.inner_text()).group()
    page.fill("#otp", code)
    page.get_by_role("button", name="Verify and continue").click()
    page.wait_for_url("**/advisor")

    def answer(label=None, typed=None):
        if typed:
            page.fill("input[aria-label]", typed)
            page.get_by_role("button", name="Send", exact=True).click()
        else:
            page.get_by_role("button", name=label, exact=True).click()
        page.wait_for_timeout(100)
        page.wait_for_selector("text=Thinking…", state="detached")

    page.get_by_role("button", name="Clinic or office", exact=True).wait_for()
    answer("Clinic or office")
    answer("6-20 people")
    answer("Pune")
    answer(typed="32TTNXB7384T1ZW")
    answer("Business broadband")
    page.get_by_role("button", name="Business email", exact=True).click()
    page.get_by_role("button", name="Data backup", exact=True).click()
    page.get_by_role("button", name=re.compile("^Done")).click()
    page.get_by_role("button", name="See my plan").click()
    page.wait_for_url("**/advisor/recommendation**")
    page.get_by_role("button", name="See price and continue").click()
    page.wait_for_url("**/quote/**")
    page.get_by_test_id("monthly-total").wait_for()
    page.wait_for_timeout(300)
    page.screenshot(path=OUT / "c5_quote_start.png")
    t0 = total(page)
    report.append(f"Quote opened: Rs {t0}/month")

    addon_label = page.locator("[role=switch][aria-checked=false]").first.get_attribute("aria-label")
    ms = page.evaluate("""() => new Promise(resolve => {
      window.__delayItems = 1500;
      const el = document.querySelector('[data-testid=monthly-total]');
      const before = el.innerText;
      const t0 = performance.now();
      document.querySelector('[role=switch][aria-checked=false]').click();
      const tick = () => el.innerText !== before ? resolve(performance.now() - t0) : (performance.now() - t0 > 1400 ? resolve(-1) : requestAnimationFrame(tick));
      requestAnimationFrame(tick);
    })""")
    t1 = total(page)
    report.append(f"Toggled '{addon_label}': total {t0} -> {t1} on screen after {ms:.0f} ms (measured in the browser) while the server reply was held back 1.5 s")
    page.wait_for_selector("text=Updating price…", state="detached", timeout=5000)
    report.append(f"After server confirmed: Rs {total(page)} (matches instant value: {total(page) == t1})")
    page.evaluate("() => { window.__delayItems = 0; }")

    page.get_by_role("button", name=re.compile("^Can.t remove")).first.click()
    reason = page.get_by_role("alert").first.inner_text()
    report.append(f"Tried to remove the locked connection -> shown: '{reason}'")
    page.screenshot(path=OUT / "c5_quote_locked_reason.png")

    plus = page.get_by_role("group", name=re.compile("Quantity: Cloud Email")).get_by_role("button", name="+")
    before = total(page)
    if plus.is_enabled():
        plus.click()
        page.wait_for_timeout(50)
        report.append(f"Email seats +1: total {before} -> {total(page)} instantly")
    page.wait_for_selector("text=Updating price…", state="detached", timeout=5000)

    page.get_by_role("button", name="₹2,500", exact=True).click()
    page.wait_for_timeout(400)
    cmp_text = page.locator("section", has_text="Compared with what you pay now").inner_text().replace("\n", " ")
    report.append(f"Compare line: {cmp_text}")
    page.screenshot(path=OUT / "c5_quote_ready.png", full_page=True)

    final_total = total(page)
    page.get_by_role("button", name="Accept and order").click()
    page.get_by_text("Order placed").wait_for()
    order_no = re.search(r"UD-\d{4}-\d{4}", page.inner_text("main")).group()
    page.screenshot(path=OUT / "c5_order_placed.png", full_page=True)
    report.append(f"Accepted: order {order_no} shown on screen")
    report.append("JS errors: " + (str(errors[:3]) if errors else "none"))
    browser.close()

con = sqlite3.connect(DB)
row = con.execute("select o.id, o.state, q.status, q.monthly_total_inr from orders o join quotes q on q.id = o.quote_id where o.display_id = ?", (order_no,)).fetchone()
items = con.execute("select product_id, qty, line_monthly_inr from quote_items where quote_id = (select quote_id from orders where display_id = ?) and selected = 1", (order_no,)).fetchall()
events = con.execute("select from_state, to_state, actor from order_events where order_id = ?", (row[0],)).fetchall()
report.append(f"DB order row: state={row[1]}, quote status={row[2]}, monthly={row[3]} (screen showed {final_total})")
report.append(f"DB selected quote_items: {items}")
report.append(f"DB order_events: {events}")
(OUT / "e2e_phase2_report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report))
