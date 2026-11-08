"""Record the product demo from the running app, then cut it into one captioned 1080p demo.mp4 for the showcase site.

Needs the backend on :8000 (with SLA_SCAN_INTERVAL_SEC=5 so a late order escalates within seconds) and the frontend on :3000.

    python showcase/build/record_demo.py                 # records clips + builds showcase/site/demo.mp4
    python showcase/build/record_demo.py --compose-only  # rebuild demo.mp4 from the last clips

Four clips: phone journey -> admin makes the order late -> phone shows the delay -> staff side (agent, leads, outbox).
ffmpeg comes from the imageio-ffmpeg package (pip install imageio-ffmpeg) unless FFMPEG is set."""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
WEB = os.environ.get("DEMO_WEB", "http://localhost:3000").rstrip("/")
API = os.environ.get("DEMO_API", "http://localhost:8000/api/v1").rstrip("/")
WORK = Path(os.environ.get("DEMO_WORK", ROOT / "showcase" / "build" / "_demo_work"))
OUT = ROOT / "showcase" / "site" / "demo.mp4"
DOCS = ROOT / "data" / "kyc_documents"
TYPES = ["gst_certificate", "udyam_certificate", "signatory_id", "address_proof"]
AGENT_PHONE = {"Priya": "9000000101", "Arjun": "9000000102", "Meera": "9000000103", "Sanjay": "9000000104", "Kavya": "9000000105"}
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PHONE = {"viewport": {"width": 393, "height": 851}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True,
         "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"}
DESK = {"viewport": {"width": 1280, "height": 800}}


class Clip:
    """One recorded browser context plus the captions that go with it (seconds from the clip's start)."""

    def __init__(self, browser, name, kind, storage=None):
        opts = PHONE if kind == "phone" else DESK
        self.ctx = browser.new_context(**opts, storage_state=storage, record_video_dir=str(WORK / "raw"), record_video_size=opts["viewport"])
        # hide the Next.js dev-mode badge in the recording
        self.ctx.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
                                 "s.textContent='nextjs-portal{display:none!important}';document.head.appendChild(s)})")
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(90_000)
        self.t0 = time.time()
        self.name, self.kind, self.caps = name, kind, []

    def cap(self, title, body):
        self.caps.append({"t": round(time.time() - self.t0, 2), "title": title, "body": body})

    def hold(self, ms):
        self.page.wait_for_timeout(ms)

    def scroll(self, px, steps=6, pause=120):
        for _ in range(steps):
            self.page.evaluate(f"window.scrollBy(0, {px / steps})")
            self.page.wait_for_timeout(pause)

    def close(self):
        dur = round(time.time() - self.t0, 2)
        video = self.page.video
        state = self.ctx.storage_state()
        self.ctx.close()
        dst = WORK / f"{self.name}.webm"
        shutil.move(video.path(), dst)
        return {"name": self.name, "kind": self.kind, "file": dst.name, "dur": dur, "caps": self.caps}, state


def api_login(phone):
    r = httpx.post(f"{API}/auth/otp/request", json={"phone": phone}, timeout=30).json()
    if "dev_code" not in r:
        raise SystemExit("OTP_MODE must be mock to record the demo")
    return r


def staff_login(page, phone):
    page.goto(WEB + "/login")
    page.fill("#phone", phone)
    page.locator("button.btn-primary").first.click()
    code = re.search(r"\d{6}", page.get_by_role("status").first.inner_text()).group()
    page.fill("#otp", code)
    page.locator("button.btn-primary").first.click()
    page.wait_for_url(re.compile(r".*/admin/(escalations|leads)$"))


def tap(c, label, wait=900):
    c.page.get_by_role("button", name=label, exact=True).click()
    c.page.wait_for_timeout(150)
    c.page.wait_for_selector("text=Thinking…", state="detached")
    c.hold(wait)


def record():
    from playwright.sync_api import sync_playwright

    shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "raw").mkdir(parents=True)
    clips = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])

        # 1. the owner's journey on a phone
        c = Clip(browser, "c1_journey", "phone")
        pg = c.page
        pg.goto(WEB)
        pg.wait_for_load_state("networkidle")
        c.cap("A small business, a phone, no salesperson", "Accel Business converts 7 in 100 small-business leads; buying takes a visit, a slow quote, paper KYC and 17.6 days.")
        c.hold(3500)
        c.cap("Pick a language", "Eight Indian languages, voice included. We continue in English.")
        pg.get_by_role("radio", name=re.compile("English")).click()
        c.hold(1800)
        pg.locator("button.btn-primary").first.click()
        pg.wait_for_url("**/login")
        c.cap("Log in with a mobile number", "A one-time code, and an opt-in for WhatsApp updates.")
        pg.locator("#phone").press_sequentially(f"95{random.randint(10**7, 10**8 - 1)}", delay=90)
        c.hold(900)
        pg.locator("button.btn-primary").first.click()
        code = re.search(r"\d{6}", pg.get_by_role("status").first.inner_text()).group()
        c.hold(1200)
        pg.locator("#otp").press_sequentially(code, delay=110)
        c.hold(900)
        pg.locator("button.btn-primary").first.click()
        pg.wait_for_url("**/advisor")
        pg.wait_for_selector("text=Thinking…", state="detached")
        c.cap("The advisor asks at most six questions", "Tap an answer, type, or hold the mic and speak.")
        c.hold(2200)
        for a in ["Shop or small service", "1-5 people", "Lucknow"]:
            tap(c, a)
        c.cap("GSTIN checked as it is typed", "The rules engine, not the AI, decides what the business is eligible for.")
        pg.locator("input.field").press_sequentially("19EOGXH4115Y1ZL", delay=80)
        c.hold(800)
        pg.get_by_role("button", name="Send").click()
        pg.wait_for_timeout(150)
        pg.wait_for_selector("text=Thinking…", state="detached")
        c.hold(1500)
        tap(c, "Home broadband")
        pg.get_by_role("button", name="UPI and billing", exact=True).click()
        c.hold(700)
        pg.get_by_role("button", name=re.compile("^Done")).click()
        pg.get_by_role("button", name="See my plan").wait_for()
        c.hold(1800)
        pg.get_by_role("button", name="See my plan").click()
        pg.wait_for_url("**/advisor/recommendation**")
        pg.wait_for_load_state("networkidle")
        c.cap("A plan, with a reason for every item", "Picked by the rules engine. Add-ons for later are priced up front.")
        c.hold(2500)
        c.scroll(700, steps=10, pause=260)
        c.hold(2000)
        pg.get_by_role("button", name="See price and continue").click()
        pg.wait_for_url("**/quote/**")
        pg.wait_for_load_state("networkidle")
        c.cap("One monthly price", "Add-ons toggle and the total updates. It compares with what they pay today.")
        c.hold(2500)
        c.scroll(600, steps=10, pause=260)
        c.hold(2200)
        pg.get_by_role("button", name=re.compile("Accept and order")).click()
        pg.get_by_test_id("continue-kyc").wait_for()
        c.hold(1500)
        pg.get_by_test_id("continue-kyc").click()
        pg.wait_for_url("**/consent")
        oid = re.search(r"/order/([^/]+)/consent", pg.url).group(1)
        pg.get_by_test_id("notice").wait_for()
        c.cap("Consent before any document", "What we collect, why, for how long, and how to withdraw (DPDP Act).")
        c.hold(2000)
        c.scroll(500, steps=8, pause=250)
        pg.get_by_test_id("agree").check()
        c.hold(1200)
        pg.get_by_test_id("consent-continue").click()
        pg.wait_for_url("**/kyc")
        c.cap("Registry lookup pre-fills the details", "Legal name and address come from the GSTIN; the owner just confirms.")
        pg.locator("#gstin").press_sequentially("19EOGXH4115Y1ZL", delay=70)
        pg.get_by_role("button", name="Check", exact=True).first.click()
        pg.get_by_test_id("gstin-card").wait_for()
        c.hold(2800)
        pg.get_by_test_id("kyc-next").click()
        c.cap("Documents read and cross-checked on upload", "13 checks with readable reasons: a stale bill is caught now, not days later.")
        c.hold(1200)
        for t in TYPES:
            pg.get_by_test_id(f"file-{t}").set_input_files(str(DOCS / f"K02_{t}.png"))
            pg.wait_for_selector(f"[data-testid=tile-{t}]:not([data-state=busy]):not([data-state=empty])", timeout=90_000)
            c.hold(700)
        c.hold(1200)
        pg.get_by_test_id("kyc-submit").click()
        pg.wait_for_selector("[data-testid=kyc-result]:not([data-verdict=''])", timeout=90_000)
        c.cap("Verified. Installation books itself", "No visit, no paper. The technician slot is picked automatically.")
        c.hold(3500)
        pg.goto(f"{WEB}/order/{oid}")
        pg.get_by_test_id("headline").wait_for()
        display = pg.inner_text("main p").split("·")[-1].strip()
        c.cap("The owner sees dates instead of chasing", "Every step has an expected date, and the technician visit is on the tracker.")
        c.hold(2500)
        c.scroll(500, steps=8, pause=260)
        c.hold(2000)
        info, phone_state = c.close()
        clips.append(info)

        # 2. admin: the technician runs late
        c = Clip(browser, "c2_simulator", "desk")
        staff_login(c.page, "9000000001")
        c.page.goto(WEB + "/admin/simulator")
        c.page.wait_for_load_state("networkidle")
        c.cap("What if a step runs late?", "For the demo, the admin's order simulator makes this order 30 hours late.")
        c.hold(1800)
        c.page.get_by_role("button", name=re.compile(re.escape(display))).click()
        c.page.wait_for_selector(f"[data-testid=sim-panel] >> text={display}")
        c.hold(1500)
        c.page.fill("#late", "30")
        c.hold(800)
        c.page.get_by_test_id("make-late").click()
        c.cap("The SLA job escalates on its own", "To the least-loaded agent who speaks the customer's language. Nobody presses a button.")
        c.hold(7000)
        info, admin_state = c.close()
        clips.append(info)

        # 3. the owner's tracker after the escalation (polls until the SLA job has run)
        c = Clip(browser, "c3_delay", "phone", storage=phone_state)
        banner = ""
        for _ in range(40):
            c.page.goto(f"{WEB}/order/{oid}")
            c.page.get_by_test_id("timeline").wait_for()
            if c.page.get_by_test_id("human-banner").count():
                banner = c.page.get_by_test_id("human-message").inner_text()
                break
            c.page.wait_for_timeout(2000)
        if not banner:
            raise SystemExit("the SLA job did not escalate; start the API with SLA_SCAN_INTERVAL_SEC=5")
        c.t0 = time.time() - 0.5
        c.cap("The owner is told first", "The tracker names the person who will call, and a WhatsApp update goes out.")
        c.hold(4500)
        c.scroll(400, steps=8, pause=260)
        c.hold(2500)
        info, _ = c.close()
        clips.append(info)
        agent_first = banner.split()[0]

        # 4. staff side: agent console, leads, outbox
        c = Clip(browser, "c4_staff", "desk")
        pg = c.page
        staff_login(pg, AGENT_PHONE.get(agent_first, "9000000101"))
        pg.get_by_test_id("queue").wait_for()
        c.cap(f"{agent_first}'s queue", "People handle the exceptions: a P-priority with an SLA timer.")
        c.hold(2500)
        pg.get_by_role("link", name=re.compile(f"Late order · {re.escape(display)}")).click()
        pg.get_by_test_id("case-header").wait_for()
        c.cap("The whole case in one view", "Chat, quote, KYC and order timeline. No asking the customer to repeat anything.")
        c.hold(3000)
        c.scroll(900, steps=12, pause=260)
        c.hold(2500)
        info, _ = c.close()
        clips.append(info)

        # 5. admin again, reusing the session from clip 2 (OTP requests are rate-limited per number)
        c = Clip(browser, "c5_admin", "desk", storage=admin_state)
        pg = c.page
        pg.goto(WEB + "/admin/leads")
        pg.get_by_test_id("metric-strip").wait_for()
        pg.wait_for_load_state("networkidle")
        c.cap("Sales: every lead scored, with reasons", "The five pilot metrics are computed live from the database.")
        c.hold(3500)
        pg.get_by_test_id("preset-hot_uncontacted").click()
        pg.wait_for_load_state("networkidle")
        c.cap("One filter: high propensity, nobody has called", "A field agent starts with the leads most likely to close.")
        c.hold(3500)
        pg.goto(WEB + "/admin/notifications")
        pg.get_by_test_id("outbox").wait_for()
        c.cap("WhatsApp updates in the owner's language", "Quote accepted, KYC verified, install booked, and the delay with the agent's name.")
        c.hold(4500)
        c.cap("A plan in minutes. Live in 8 days, not 17.6", "15 judge scenarios and 192 tests pass. All data is synthetic.")
        c.hold(4000)
        info, _ = c.close()
        clips.append(info)
        browser.close()

    (WORK / "clips.json").write_text(json.dumps(clips, indent=2))
    print("recorded", [f"{x['name']} {x['dur']}s" for x in clips])


# ---------- composing ----------
W, H, FPS = 1920, 1080, 30
BG, INK, MUTED, RED = "0xf7f7f9", "0x16161a", "0x74747e", "0xe40000"


def ffmpeg_bin():
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def esc(s):
    return s.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def compose():
    clips = json.loads((WORK / "clips.json").read_text())
    for f in ("segoeui.ttf", "segoeuib.ttf"):
        shutil.copy(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / f, WORK / f)
    inputs, chains, labels, n, step = [], [], [], 0, 0
    elapsed, poster_t = 0.0, None
    for i, cl in enumerate(clips):
        inputs += ["-i", cl["file"]]
        # cut the blank lead-in (page loading, staff login) so each clip opens on its first caption
        off = max(0.0, cl["caps"][0]["t"] - 0.3)
        dur = round(cl["dur"] - off, 2)
        caps = [{**cp, "t": round(cp["t"] - off, 2)} for cp in cl["caps"]]
        if i == 0 and len(caps) > 5:
            poster_t = caps[5]["t"] + 2.5  # the recommendation screen
        elapsed += dur
        draw = []
        for j, cp in enumerate(caps):
            start = max(cp["t"], 0)
            end = caps[j + 1]["t"] if j + 1 < len(caps) else dur + 1
            en = f"between(t\\,{start}\\,{end})"
            tf, bf = f"cap_{i}_{j}_t.txt", f"cap_{i}_{j}_b.txt"
            step += 1
            if cl["kind"] == "phone":
                (WORK / tf).write_text(textwrap.fill(cp["title"], 26), encoding="utf-8", newline="\n")
                (WORK / bf).write_text(textwrap.fill(cp["body"], 44), encoding="utf-8", newline="\n")
                draw.append(f"drawtext=fontfile=segoeuib.ttf:textfile={tf}:fontsize=62:fontcolor={INK}:line_spacing=14:x=150:y=360:enable='{en}'")
                draw.append(f"drawtext=fontfile=segoeui.ttf:textfile={bf}:fontsize=36:fontcolor={MUTED}:line_spacing=16:x=150:y=620:enable='{en}'")
                draw.append(f"drawtext=fontfile=segoeuib.ttf:text='{step:02d}':fontsize=30:fontcolor={RED}:x=150:y=300:enable='{en}'")
            else:
                (WORK / tf).write_text(cp["title"], encoding="utf-8", newline="\n")
                (WORK / bf).write_text(cp["body"], encoding="utf-8", newline="\n")
                draw.append(f"drawtext=fontfile=segoeuib.ttf:textfile={tf}:fontsize=40:fontcolor={INK}:x=(w-text_w)/2:y=958:enable='{en}'")
                draw.append(f"drawtext=fontfile=segoeui.ttf:textfile={bf}:fontsize=28:fontcolor={MUTED}:x=(w-text_w)/2:y=1018:enable='{en}'")
        brand = (f"drawtext=fontfile=segoeuib.ttf:text='Udyam Digital':fontsize=30:fontcolor={INK}:x=60:y=44,"
                 f"drawtext=fontfile=segoeui.ttf:text='live demo · Accel Business':fontsize=26:fontcolor={MUTED}:x=280:y=48,"
                 f"drawbox=x=0:y=0:w={W}:h=8:color={RED}:t=fill")
        if cl["kind"] == "phone":
            ph_h, ph_w = 960, int(960 * 393 / 851) // 2 * 2
            x, y = 1280, (H - ph_h) // 2 + 20
            chains.append(f"[{i}:v]trim=start={off},setpts=PTS-STARTPTS,fps={FPS},scale={ph_w}:{ph_h},setsar=1[p{i}]")
            chains.append(f"color=c={BG}:s={W}x{H}:r={FPS}:d={dur},format=yuv420p,"
                          f"drawbox=x={x - 14}:y={y - 14}:w={ph_w + 28}:h={ph_h + 28}:color={INK}:t=fill[bg{i}]")
            chains.append(f"[bg{i}][p{i}]overlay={x}:{y}:shortest=1,{brand},{','.join(draw)}[v{i}]")
        else:
            vw, vh = 1440, 900
            x, y = (W - vw) // 2, 36
            chains.append(f"[{i}:v]trim=start={off},setpts=PTS-STARTPTS,fps={FPS},scale={vw}:{vh},setsar=1[p{i}]")
            chains.append(f"color=c={BG}:s={W}x{H}:r={FPS}:d={dur},format=yuv420p,"
                          f"drawbox=x={x - 2}:y={y - 2}:w={vw + 4}:h={vh + 4}:color=0xdcdce2:t=fill[bg{i}]")
            chains.append(f"[bg{i}][p{i}]overlay={x}:{y}:shortest=1,{','.join(draw)},drawbox=x=0:y=0:w={W}:h=8:color={RED}:t=fill[v{i}]")
        labels.append(f"[v{i}]")
        n += 1
    chains.append(f"{''.join(labels)}concat=n={n}:v=1:a=0,format=yuv420p[out]")
    (WORK / "filter.txt").write_text(";\n".join(chains), encoding="utf-8")
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", *inputs, "-/filter_complex", "filter.txt",
           "-map", "[out]", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "demo.mp4"]
    subprocess.run(cmd, cwd=WORK, check=True)
    # poster for the site's player, so it doesn't open on a blank frame before Play
    subprocess.run([ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-ss", str(poster_t or 5), "-i", "demo.mp4",
                    "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "4", "demo_poster.jpg"], cwd=WORK, check=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(WORK / "demo.mp4", OUT)
    shutil.copy(WORK / "demo_poster.jpg", OUT.with_name("demo_poster.jpg"))
    print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.1f} MB, {elapsed:.0f} s")


if __name__ == "__main__":
    if "--compose-only" not in sys.argv:
        record()
    compose()
