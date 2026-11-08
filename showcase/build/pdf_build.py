"""Themed A4 PDF (same look as the showcase site): approach, competitive analysis, impact, privacy."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

B = Path(__file__).parent
SITE = B.parent / "site"
sys.path.insert(0, str(B))
from pdf_sources import SOURCES  # noqa: E402

d = json.load(open(B / "site_data.json"))
fmt = lambda n: f"{n:,}"
RED, RED2, RED3, RED4, GREY, INK, INK2, MUTED, LINE = "#e40000", "#f26b6b", "#f7a6a6", "#fbd0d0", "#d5d5da", "#16161a", "#3d3d45", "#74747e", "#ececf0"
ARCH = (SITE / "img" / "architecture.svg").read_text()
ARCH = ARCH[ARCH.index("<svg"):]
LOGO = '<svg class="logo" viewBox="0 0 32 32"><rect width="32" height="32" rx="9" fill="#e40000"/><path d="M10 9.5v7.5a6 6 0 0 0 12 0v-1.5" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round"/><circle cx="22" cy="10" r="2.3" fill="#fff"/></svg>'


def hbar(rows, w=330, lw=105, h=20, gap=6, vw=95):
    m = max(r[1] for r in rows)
    H = len(rows) * (h + gap)
    o = [f'<svg viewBox="0 0 {w} {H}" width="100%" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    pw = w - lw - vw
    for i, (lab, v, c, t) in enumerate(rows):
        y = i * (h + gap); bw = max(3, v / m * pw)
        o.append(f'<text x="{lw-8}" y="{y+h/2+4}" text-anchor="end" font-size="10.5" fill="{INK2}">{lab}</text>')
        o.append(f'<rect x="{lw}" y="{y+2}" width="{bw}" height="{h-4}" rx="5" fill="{c}"/>')
        o.append(f'<text x="{lw+bw+6}" y="{y+h/2+4}" font-size="10.5" font-weight="600" fill="{INK}">{t}</text>')
    o.append("</svg>")
    return "".join(o)


def dumbbell():
    M = [("Lead-to-activation", 7.4, 11, "%", 15), ("Days, lead to live", 17.6, 8, " d", 20), ("CAC per activation", 15.053, 8, "k", 16),
         ("6-month churn", 15.2, 11, "%", 20), ("Chase calls / customer", 3.0, 0.5, "", 3.5)]
    w, lw, pr, rh = 520, 150, 26, 32
    H = len(M) * rh + 6
    f = lambda v, u: f"Rs {round(v*1000):,}" if u == "k" else f"{v:g}{u}"
    o = [f'<svg viewBox="0 0 {w} {H}" width="100%" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    for i, (l, b, t, u, mx) in enumerate(M):
        y = i * rh + 20; X = lambda v: lw + v / mx * (w - lw - pr)
        o += [f'<text x="{lw-10}" y="{y+4}" text-anchor="end" font-size="10.5" fill="{INK2}">{l}</text>',
              f'<line x1="{lw}" x2="{w-pr}" y1="{y}" y2="{y}" stroke="{LINE}" stroke-width="2"/>',
              f'<line x1="{X(b)}" x2="{X(t)}" y1="{y}" y2="{y}" stroke="{RED}" stroke-width="3"/>',
              f'<circle cx="{X(b)}" cy="{y}" r="5" fill="#fff" stroke="{MUTED}" stroke-width="2"/>',
              f'<circle cx="{X(t)}" cy="{y}" r="6" fill="{RED}" stroke="#fff" stroke-width="2"/>',
              f'<text x="{X(b)}" y="{y-9}" text-anchor="middle" font-size="9.5" fill="{MUTED}">{f(b,u)}</text>',
              f'<text x="{X(t)}" y="{y-9}" text-anchor="middle" font-size="9.5" font-weight="700" fill="{INK}">{f(t,u)}</text>']
    o.append("</svg>")
    return "".join(o)


funnel = hbar([(f["stage"], f["n"], RED if f["stage"] == "Quote accepted" else [RED2, RED2, RED2, RED, RED3, RED3][i], fmt(f["n"]) + (f" · {f['pass']}%" if f["pass"] else "")) for i, f in enumerate(d["funnel"])])
GC = {"Reach & speed": RED, "Understanding & price": RED2, "Paperwork": RED3, "Other": GREY}
drops = hbar([(g["group"], g["n"], GC[g["group"]], f"{fmt(g['n'])} · {g['pct']}%") for g in d["drop_groups"]], lw=120)
chase = hbar([(f"{c['calls']} call{'s' if c['calls'] != '1' else ''}", c["churn"], [RED4, RED3, RED3, RED2, RED][i], f"{c['churn']}% churn · NPS {c['nps']}") for i, c in enumerate(d["chase"])], vw=135, lw=60)


def impact(L):
    a0, a1 = round(L * .074), round(L * .11)
    k0, k1 = a0 * (1 - .152), a1 * (1 - .11)
    return dict(a0=a0, a1=a1, extra=a1 - a0, rev=(k1 - k0) * 6900 * 12, spend0=a0 * 15053, spend1=a1 * 8000, calls0=round(a0 * 3.0), calls1=round(a1 * .5), kept=round(k1 - k0))


I5, I50 = impact(5000), impact(50000)
cr = lambda v: f"Rs {v/1e7:.2f} crore" if v >= 1e7 else f"Rs {v/1e5:.1f} lakh"

F, P, N, U = ('<span class="dot full"></span>', '<span class="dot part"></span>', '<span class="dot none"></span>', '<span class="dot np"></span>')
CMP = [("Self-serve purchase, start to finish", F, N, P, N, N, P, N), ("Guided discovery that ends in a bundle", F, P, N, P, U, N, N),
       ("Eligibility rules enforced at sale", F, N, U, U, U, U, N), ("Instant, transparent quote with add-ons", F, N, P, N, U, P, N),
       ("Digital KYC with GSTIN / Udyam checks", F, N, U, U, U, P, F), ("Live order tracker with expected dates", F, N, P, U, U, P, N),
       ("Vernacular voice in the buying journey", F, N, U, P, P, N, N), ("Named person on exceptions, full context", F, P, P, P, P, N, N),
       ("Lead scoring for the sales team", F, N, U, U, U, U, N)]
cmp_rows = "".join(f"<tr><td>{r[0]}</td>" + "".join(f'<td class="c{" us" if i == 0 else ""}">{v}</td>' for i, v in enumerate(r[1:])) + "</tr>" for r in CMP)
VC = {"Verified": "mint", "Re-upload": "butter", "Manual": "lilac", "Human": "lilac", "Blocked": "rose", "Needs": "butter"}
kyc_rows = "".join(f"<div class='kc'><b>{k['id']}</b><span class='ok'>{'✓' if k['match'] else '✗'}</span><br><i class='vp {VC[k['verdict'].split()[0]]}'>{k['verdict']}</i></div>" for k in d["kyc"])
sc_rows = "".join(f"<tr><td>{s['id'][3:].replace('_',' ')}</td><td>{s['lang']}</td><td>{s['bundle'].split(':')[0]}</td><td class='n'>{s['monthly']}</td><td>{'—' if s['refused']=='-' else s['refused'].split(':')[0]}</td></tr>" for s in d["scenarios"])
PLAN = {"Professional offices": ("Wave 1", "rose"), "Small multi-site businesses": ("Wave 1 · assisted", "rose"), "Micro retail & services": ("Wave 2 · self-serve", "peach"), "Small manufacturers": ("Assisted", "sky")}
seg_rows = "".join(f"<tr><td><b>{s['segment']}</b></td><td class='n'>{s['share']}%</td><td class='n'><b style='color:{RED if s['conv']>10 else MUTED}'>{s['conv']}%</b></td><td class='n'>Rs {fmt(s['bundle'])}</td><td class='n'>{s['churn']}%</td><td class='n'>Rs {fmt(s['cac'])}</td><td class='n'>{s['gstin']}%</td><td><i class='vp {PLAN[s['segment']][1]}'>{PLAN[s['segment']][0]}</i></td></tr>" for s in d["segments"])
src_html = "".join(f'<li><a href="{u}">{t}</a></li>' for t, u in SOURCES)
STEPS = ["Pick a language", "OTP login, WhatsApp opt-in", "Six questions to the advisor", "A rules-checked plan", "One monthly price", "DPDP consent", "GSTIN registry lookup", "Four documents, checked on upload", "Verified, install booked", "Tracker with the visit", "Live, every update listed"]
steps_html = "".join(f'<span class="st{" h" if i in (2, 7, 9) else ""}"><b>{i+1}</b>{s}</span>' for i, s in enumerate(STEPS))
PIPE = [("Notice &amp; consent", "Plain notice in 8 languages (kyc-v1.0): what, why, how long, how to withdraw. No upload without it.", "Login collects: phone, language, WhatsApp yes/no"),
        ("Collect the minimum", "Each step asks only what it needs. Voice audio becomes text and is discarded.", "Advisor: type, size, city, needs; GSTIN optional"),
        ("Verify", "GSTIN / Udyam lookups, OCR and 13 cross-checks, used only for KYC.", "KYC: GSTIN, Udyam, 4 documents"),
        ("Encrypt &amp; mask", "Fernet on PII columns and every file; phone as a keyed hash; IDs masked in UI and logs.", "Shown as 27•••••••••1Z5 · ••••••4321"),
        ("Access by role", "Customer sees own data; agent only assigned cases; admin the rest.", "Every view is audit-logged"),
        ("Retain", "Kept only while the purpose runs. Cases under review are held until decided.", "90 days after verify · 30 if abandoned"),
        ("Delete", "Hourly purge job. Withdrawal cancels the case and deletes files at once.", "One tap in the app")]
pipe_html = "".join(f'<div class="node"><span class="nn">{i+1}</span><h4>{t}</h4><p>{x}</p><div class="col">{c}</div></div>' for i, (t, x, c) in enumerate(PIPE))

import random
_r = random.Random(7)
BIN = "".join(f'<text x="{_r.randint(430,590)}" y="{_r.randint(10,70)}">{_r.choice(["1 0 1","0 1","1","0 0 1"])}</text>' for i in range(12))
_unused = "".join(f'<text x="{(i*53)%600}" y="{(i*37)%840}" >{"1 0 1" if i%3==0 else ("0 1" if i%3==1 else "1")}</text>' for i in range(90))


def page(num, kick, body, cls=""):
    return f'<section class="page {cls}"><div class="wm" aria-hidden="true"><svg viewBox="0 0 600 840" xmlns="http://www.w3.org/2000/svg"><g font-family="monospace" font-size="15" fill="#e40000" fill-opacity=".05">{BIN}</g></svg></div><p class="k"><b>{num}</b> {kick}</p>{body}<footer>{LOGO}<span><b>udyam</b>digital · Approach, competitive analysis &amp; impact</span><span class="pn"></span></footer></section>'


css = f"""
@page {{ size: A4; margin: 0 }}
* {{ box-sizing: border-box }}
body {{ margin:0; font: 9.6pt/1.5 Poppins, Inter, system-ui, sans-serif; color:{INK}; counter-reset: pg; -webkit-print-color-adjust: exact; print-color-adjust: exact }}
.page {{ width:210mm; height:297mm; padding:15mm 15mm 20mm; position:relative; overflow:hidden; page-break-after:always; counter-increment: pg; background:#fff }}
.page:last-child {{ page-break-after:auto }}
.wm {{ position:absolute; inset:0; pointer-events:none }} .wm svg {{ width:100%; height:100% }}
.page:not(.cover) > *:not(.wm):not(footer) {{ position:relative }}
footer {{ position:absolute; left:15mm; right:15mm; bottom:9mm; display:flex; align-items:center; gap:7pt; font-size:7.5pt; color:{MUTED}; border-top:1px solid {LINE}; padding-top:6pt }}
footer .logo {{ width:12pt; height:12pt }} footer b {{ color:{INK}; font-weight:700 }}
footer .pn {{ margin-left:auto; font-weight:600; color:{INK} }} footer .pn::before {{ content: counter(pg, decimal-leading-zero) }}
h1,h2,h3,h4 {{ margin:0; letter-spacing:-.01em }}
h2 {{ font-size:18.5pt; line-height:1.18; font-weight:700; margin:0 0 7pt; max-width:165mm }} h2 em {{ font-style:normal; color:{RED} }}
h3 {{ font-size:11.5pt; font-weight:600; margin:12pt 0 5pt }}
.k {{ display:flex; align-items:center; gap:6pt; font-size:7.5pt; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:{RED}; margin:0 0 6pt }}
.k::before {{ content:""; width:16pt; height:2.5pt; border-radius:2pt; background:{RED} }} .k b {{ font-weight:700 }}
p {{ margin:0 0 6pt }} .muted {{ color:{MUTED} }} .lede {{ font-size:10.8pt; color:{INK2} }} .small {{ font-size:8pt }}
.stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8pt; margin:9pt 0 }}
.stat {{ border-left:3pt solid {RED}; padding:2pt 0 2pt 9pt }} .stat b {{ display:block; font-size:16pt; font-weight:700; color:{RED}; line-height:1.15 }} .stat span {{ font-size:8pt; color:{INK2}; display:block; margin-top:2pt }}
.two {{ display:grid; grid-template-columns:1fr 1fr; gap:12pt }} .three {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10pt }}
.box {{ background:#fff; border:1px solid #ececf0; border-radius:12pt; padding:10pt 11pt; break-inside:avoid; box-shadow:0 3pt 12pt rgba(20,20,30,.04) }}
.box h4 {{ margin:0 0 5pt; font-size:10pt; display:flex; justify-content:space-between; gap:6pt; align-items:center }}
.box ul {{ margin:2pt 0 0 }}
table {{ border-collapse:separate; border-spacing:0; width:100%; font-size:8.2pt }} tr {{ break-inside:avoid }}
th,td {{ text-align:left; padding:4pt 6pt; border-bottom:1px solid {LINE}; vertical-align:top }}
th {{ background:{RED}; color:#fff; font-weight:600; font-size:7.8pt }} th:first-child {{ border-top-left-radius:7pt }} th:last-child {{ border-top-right-radius:7pt }}
tr:nth-child(even) td {{ background:#fbfbfc }}
td.c,th.c {{ text-align:center }} td.n,th.n {{ text-align:right; white-space:nowrap }}
th.us {{ background:#b50000 }} td.us {{ background:#fff1f1 !important }} th.today {{ background:#8a8a93 }}
.dot {{ display:inline-block; width:9pt; height:9pt; border-radius:50%; vertical-align:middle }}
.dot.full {{ background:{RED} }} .dot.part {{ background:linear-gradient(90deg,{RED2} 50%,#ffe1e1 50%) }} .dot.none {{ border:1.3px solid #c9c9cf }} .dot.np {{ border:1.3px dashed #b5b5bf }}
ul,ol {{ margin:3pt 0 6pt; padding-left:14pt }} li {{ margin:2pt 0 }} li::marker {{ color:{RED} }}
.take {{ border-left:3pt solid {RED}; background:#fff1f1; border-radius:0 8pt 8pt 0; padding:6pt 9pt; color:{INK}; font-weight:500; margin:6pt 0 }}
.callout {{ border-left:3.5pt solid {RED}; background:#fff1f1; border-radius:0 10pt 10pt 0; padding:9pt 12pt; font-weight:600; font-size:10.5pt; line-height:1.45; margin:8pt 0 }}
.pill,.vp {{ display:inline-block; font-style:normal; font-size:7pt; font-weight:600; letter-spacing:.04em; padding:2pt 7pt; border-radius:999px; color:{INK2}; white-space:nowrap }}
.rose {{ background:#ffe6e6 }} .peach {{ background:#fff3ec }} .mint {{ background:#eef7f2 }} .lilac {{ background:#f3f0fa }} .butter {{ background:#fff9e8 }} .sky {{ background:#edf4fb }} .grey {{ background:#f1f1f3 }}
.legend span {{ margin-right:10pt; font-size:8pt; color:{INK2} }} .legend i {{ display:inline-block; width:8pt; height:8pt; border-radius:2pt; margin-right:4pt; vertical-align:-1pt }}
.src li {{ font-size:8pt; margin:2pt 0 }} .src a {{ color:{RED}; text-decoration:none }}
.kg {{ display:grid; grid-template-columns:repeat(6,1fr); gap:5pt }} .kc {{ border:1px solid {LINE}; border-radius:8pt; padding:5pt 6pt; font-size:8pt }} .kc .ok {{ float:right; color:{RED}; font-weight:700 }}
.princ {{ display:grid; grid-template-columns:repeat(5,1fr); gap:7pt; margin:6pt 0 }}
.princ div {{ border:1px solid #ececf0; border-top:2.5pt solid {RED}; border-radius:10pt; padding:8pt; font-size:7.8pt; color:{INK2}; line-height:1.45 }} .princ b {{ display:block; color:{INK}; font-size:8.8pt; margin-bottom:3pt }}
.steps {{ display:flex; flex-wrap:wrap; gap:5pt }} .st {{ display:inline-flex; align-items:center; gap:5pt; border:1px solid #ececf0; border-radius:999px; padding:3pt 9pt 3pt 3pt; font-size:8pt; font-weight:500 }}
.st b {{ width:14pt; height:14pt; border-radius:50%; background:{RED}; color:#fff; display:grid; place-items:center; font-size:7pt }} .st.h b {{ background:#ffd6d6; color:#b50000 }}
.arch {{ border:1px solid #ececf0; border-radius:12pt; padding:6pt; background:#fff }} .arch svg {{ width:100%; height:auto; display:block }}
.keys {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8pt 14pt; margin-top:10pt }} .key {{ display:grid; grid-template-columns:12pt 1fr; gap:7pt; font-size:8.4pt; color:{INK2} }} .key i {{ width:11pt; height:11pt; border-radius:3pt; margin-top:2pt }} .key b {{ color:{INK} }}
.pipe {{ display:grid; grid-template-columns:repeat(7,1fr); gap:6pt; margin:8pt 0 }}
.node {{ position:relative; border:1px solid #ececf0; border-top:2.5pt solid {RED}; border-radius:10pt; padding:7pt; font-size:7.4pt; line-height:1.4; color:{INK2} }}
.node .nn {{ width:15pt; height:15pt; border-radius:50%; background:{RED}; color:#fff; display:grid; place-items:center; font-weight:700; font-size:7.5pt }}
.node h4 {{ margin:5pt 0 3pt; font-size:8.6pt; color:{INK} }} .node p {{ margin:0 }} .node .col {{ margin-top:5pt; padding-top:4pt; border-top:1px dashed {LINE}; color:{MUTED}; font-size:7pt }}
.node:not(:last-child)::after {{ content:"›"; position:absolute; right:-6pt; top:6pt; color:{RED}; font-weight:700; font-size:11pt }}
.rails span {{ display:inline-block; margin:0 4pt 5pt 0; background:#fff1f1; border-radius:999px; padding:3pt 9pt; font-size:8pt }} .rails span::before {{ content:"●"; color:{RED}; margin-right:4pt; font-size:6pt; vertical-align:1pt }}

table.tight td, table.tight th {{ padding:2.6pt 5pt; font-size:7.6pt }}
.tightp .box {{ padding:8pt 10pt }} .tightp .box p {{ font-size:8.5pt; margin-bottom:4pt }} .tightp h3 {{ margin-top:9pt }}
/* cover */
.cover {{ background:#0b0b0d; color:#fff; padding:0; counter-increment:none }}
.cover .bg {{ position:absolute; inset:0 }} .cover .bg svg {{ width:100%; height:100% }}
.cover .inner {{ position:absolute; inset:0; padding:22mm 18mm 18mm; display:flex; flex-direction:column }}
.cover .brand {{ display:flex; align-items:center; gap:8pt; font-size:13pt }} .cover .brand .logo {{ width:24pt; height:24pt }} .cover .brand span {{ color:rgba(255,255,255,.6) }} .cover .brand b {{ color:#fff }}
.cover .kc2 {{ color:#ff6b6b; font-size:8.5pt; font-weight:600; letter-spacing:.16em; text-transform:uppercase; margin:60mm 0 8pt; display:flex; align-items:center; gap:8pt }} .cover .kc2::before {{ content:""; width:18pt; height:2.5pt; background:{RED}; border-radius:2pt }}
.cover h1 {{ font-size:60pt; font-weight:800; line-height:.95; letter-spacing:-.03em; color:#fff }} .cover h1 span {{ display:block; color:{RED} }}
.cover .tag {{ font-size:16pt; font-weight:500; margin-top:12pt }} .cover .tag b {{ color:#ff6b6b }}
.cover .sub {{ color:rgba(255,255,255,.72); font-size:10.5pt; margin-top:6pt; max-width:120mm }}
.cover .chips {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8pt; margin-top:16mm }}
.cover .chips div {{ border:1px solid rgba(255,90,90,.4); background:rgba(228,0,0,.1); border-radius:12pt; padding:9pt }} .cover .chips b {{ display:block; font-size:15pt; color:#fff }} .cover .chips span {{ font-size:7.8pt; color:rgba(255,255,255,.7) }}
.cover .toc {{ margin-top:auto; display:grid; grid-template-columns:repeat(4,1fr); gap:4pt 10pt; font-size:8.2pt; color:rgba(255,255,255,.75); border-top:1px solid rgba(255,255,255,.12); padding-top:9pt }} .cover .toc b {{ color:#ff6b6b; margin-right:5pt }}
.cover .fine {{ font-size:7.2pt; color:rgba(255,255,255,.4); margin-top:8pt }}
.globe {{ position:absolute; right:-14mm; top:40mm; width:120mm; opacity:.95 }}
"""

GLOBE = """<svg class="globe" viewBox="0 0 400 400"><defs><radialGradient id="gg" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#ff4d4d" stop-opacity=".5"/><stop offset=".55" stop-color="#8a0000" stop-opacity=".32"/><stop offset="1" stop-color="#1a0000" stop-opacity=".08"/></radialGradient></defs>
<circle cx="200" cy="200" r="150" fill="url(#gg)" stroke="#ff3b3b" stroke-opacity=".6"/><g fill="none" stroke="#ff4d4d" stroke-opacity=".38"><ellipse cx="200" cy="200" rx="150" ry="52"/><ellipse cx="200" cy="200" rx="150" ry="104"/><ellipse cx="200" cy="200" rx="52" ry="150"/><ellipse cx="200" cy="200" rx="104" ry="150"/><line x1="50" y1="200" x2="350" y2="200"/><line x1="200" y1="50" x2="200" y2="350"/></g>
<g fill="none" stroke="#ff6b6b" stroke-width="1.6" stroke-dasharray="4 5"><path d="M120 160 Q200 80 290 150"/><path d="M110 250 Q210 320 300 240"/><path d="M150 120 Q250 200 160 290"/></g>
<g fill="#fff"><circle cx="120" cy="160" r="5"/><circle cx="290" cy="150" r="5"/><circle cx="110" cy="250" r="4"/><circle cx="300" cy="240" r="5"/><circle cx="150" cy="120" r="4"/><circle cx="160" cy="290" r="5"/><circle cx="215" cy="205" r="7" fill="#ff3b3b"/></g></svg>"""
COVER_BIN = "".join(f'<text x="{_r.randint(0,590)}" y="{_r.randint(0,835)}" fill-opacity="{_r.choice([.08,.12,.18,.25,.35])}">{_r.choice(["0","1"])}</text>' for i in range(170))
_unused2 = "".join(f'<text x="{(i*41)%600}" y="{(i*29)%840}" fill-opacity="{0.08 + (i%5)*0.05:.2f}">{"1" if i%2 else "0"}</text>' for i in range(220))

cover = f"""<section class="page cover"><div class="bg"><svg viewBox="0 0 600 840" preserveAspectRatio="xMidYMid slice"><g font-family="monospace" font-size="14" fill="#e40000">{COVER_BIN}</g></svg></div>{GLOBE}
<div class="inner"><div class="brand">{LOGO}<span><b>udyam</b>digital</span></div>
<p class="kc2">Airtel Sync 2026 · Digital Track</p>
<h1>Udyam<span>Digital</span></h1>
<p class="tag">Small businesses go digital <b>in one sitting</b>.</p>
<p class="sub">Approach, competitive analysis and impact of a phone-first journey for Accel Business: a voice advisor in 8 languages, one monthly price, KYC in minutes, a live tracker and a person on every exception.</p>
<div class="chips"><div><b>7.4% → 11%</b><span>lead-to-activation, baseline → pilot target</span></div><div><b>17.6 → 8</b><span>days from lead to live</span></div><div><b>192 / 192</b><span>automated tests pass</span></div><div><b>0</b><span>ineligible bundles (15% today)</span></div></div>
<div class="toc"><span><b>01</b>Executive summary</span><span><b>02</b>Problem &amp; evidence</span><span><b>03</b>Approach</span><span><b>04</b>Build &amp; architecture</span><span><b>05</b>Results</span><span><b>06</b>Competitive analysis</span><span><b>07</b>Impact</span><span><b>08</b>Privacy &amp; next steps</span></div>
<p class="fine">Accel Telecom and Accel Business are the case's fictional operator. Project figures are computed from the supplied synthetic dataset and the project's own analysis and test runs; market facts are cited to public sources on the last page.</p></div></section>"""

pages = [cover]
pages.append(page("01", "Executive summary", f"""
<h2>A phone-first journey where <em>rules decide, AI explains,</em> and people handle exceptions.</h2>
<p class="lede">Small businesses buying from Accel today wait for a call, make time for a visit, get a slow quote full of product codes, collect paper documents and then chase installation. Only 7.4% of leads become customers, after 17.6 days and 3 status calls each.</p>
<div class="stats"><div class="stat"><b>7.4%</b><span>of 5,000 leads become customers</span></div><div class="stat"><b>17.6 days</b><span>from lead to live</span></div><div class="stat"><b>Rs 15,053</b><span>to acquire one customer</span></div><div class="stat"><b>3.0</b><span>status-chase calls each</span></div></div>
<div class="two">
<div class="box"><h4>What we built</h4><ul>
<li>An AI advisor (text or voice, 8 languages) that asks at most 6 questions and returns a <b>rules-checked</b> bundle in plain words.</li>
<li>An instant quote with add-on toggles and dependency locks: one monthly price.</li>
<li>Smart KYC: DPDP consent first, live GSTIN/Udyam lookups, OCR on 4 documents and 13 cross-checks with specific fixes.</li>
<li>A live tracker with expected dates, WhatsApp updates and automatic escalation to a named, language-matched agent.</li>
<li>An admin dashboard: propensity-ranked leads, Call with outcome, and the 5 pilot metrics computed live.</li></ul></div>
<div class="box"><h4>Why it wins</h4><ul>
<li><b>Aimed at the data.</b> 41.2% of drops are about reach and speed; the quote passes only 43.6%. The journey removes the visit and the wait.</li>
<li><b>Proven, not promised.</b> 192/192 tests, 15/15 judge-style scenarios, 12/12 KYC verdicts, a clean phone run from language to live.</li>
<li><b>Different from rivals.</b> Jio, Vi, Tata Tele and BSNL sell to MSMEs, but buying still runs through a callback, an assessment or a booking-then-wait.</li>
<li><b>Measurable.</b> At one quarter's 5,000 leads the pilot targets mean about {fmt(I5['extra'])} more customers and {cr(I5['spend0']-I5['spend1'])} less acquisition spend.</li></ul></div></div>
<div class="callout">Recommendation: launch self-serve with professional offices (11.1% conversion, lowest CAC at Rs 10,695, 86% have a GSTIN) and run multi-site businesses as an assisted track from day one. Measure the five metrics weekly against the Apr–Jun 2026 baseline.</div>"""))

pages.append(page("02", "Problem &amp; evidence", f"""
<h2>Two-thirds of losses happen <em>before anyone sees a price</em>.</h2>
<div class="callout" style="font-size:9.6pt">The case: design and build a digital-first journey that lets a small business owner discover the right bundle, buy it and get it activated with minimal human effort, on a phone, in their preferred language.</div>
<div class="two">
<div><h3>The funnel: 5,000 leads, Apr–Jun 2026</h3>{funnel}<p class="take">The largest loss is first contact (1,594); the lowest pass rate is the quote (43.6%, 32% for micro).</p></div>
<div><h3>Why {fmt(d['drop_total'])} leads dropped</h3><div class="legend">{"".join(f'<span><i style="background:{c}"></i>{g}</span>' for g, c in GC.items())}</div>{drops}<p class="take">Reach and speed cause 41.2% of drops; paperwork only 5.9%.</p></div></div>
<div class="two">
<div><h3>Chasing status predicts churn</h3>{chase}<p class="take">Churn rises from 5.9% at one chase call to 27.9% at five or more: the tracker is a retention feature.</p></div>
<div><h3>Other findings that shaped the design</h3><ul>
<li><b>Mis-selling:</b> 56 of 368 customers (15%) bought bundles the catalogue forbids.</li>
<li><b>GSTIN matters:</b> {d['gstin_conv']['Y']}% conversion with a GSTIN vs {d['gstin_conv']['N']}% without; it gates 10 of 25 products, so the advisor asks for it at question 3.</li>
<li><b>Digital leads go unanswered:</b> 45% of website-form and 59% of WhatsApp leads are never contacted.</li>
<li><b>Lead scoring works:</b> the top 20% of scored leads hold {d['top20_share']}% of activations.</li>
<li><b>KYC needs a safety net:</b> 6 of 12 sample applicants had planted problems; 2 need a person.</li></ul></div></div>"""))

pages.append(page("03", "Approach", f"""
<h2>Win the segments that already convert, and keep micro shops <em>self-serve</em>.</h2>
<table><tr><th>Segment</th><th class="n">Share</th><th class="n">Converts</th><th class="n">Median bundle</th><th class="n">6-mo churn</th><th class="n">CAC</th><th class="n">Has GSTIN</th><th>Plan</th></tr>{seg_rows}</table>
<h3>Design principles: AI handles acquisition, people handle exceptions</h3>
<div class="princ"><div><b>Rules decide, AI explains</b>Eligibility, quantities and prices come only from code; LLM output naming an unlisted product or price is discarded.</div><div><b>People on exceptions</b>KYC judgement calls, late steps, a stuck chat or "talk to a person" go to a named agent.</div><div><b>Consent first</b>DPDP consent before any document; minimum data; IDs encrypted and masked.</div><div><b>Status, not chasing</b>Expected dates from catalogue install days, a live tracker and WhatsApp updates.</div><div><b>Field force included</b>Scored leads and an assisted mode, so sales and partners close more, not less.</div></div>
<h3>The product decision: a hybrid of AI and people</h3>
<table><tr><th>Criterion</th><th class="n">Weight</th><th class="c">A · AI-first self-serve</th><th class="c us">B · Hybrid AI + human</th><th class="c">C · Agent tool</th></tr>
<tr><td>Fit to the case (phone, language, field-force role)</td><td class="n">25%</td><td class="c">4</td><td class="c us">5</td><td class="c">2</td></tr>
<tr><td>Addresses the observed drop causes</td><td class="n">25%</td><td class="c">3</td><td class="c us">5</td><td class="c">3</td></tr>
<tr><td>Feasible within the hackathon</td><td class="n">20%</td><td class="c">4</td><td class="c us">3</td><td class="c">4</td></tr>
<tr><td>Business value (CAC, conversion, churn)</td><td class="n">15%</td><td class="c">4</td><td class="c us">5</td><td class="c">3</td></tr>
<tr><td>Risk (dead-ends, compliance, adoption)</td><td class="n">15%</td><td class="c">2</td><td class="c us">4</td><td class="c">3</td></tr>
<tr><td><b>Weighted total (out of 5)</b></td><td></td><td class="c"><b>3.45</b></td><td class="c us"><b style="color:{RED}">4.45</b></td><td class="c"><b>2.95</b></td></tr></table>
<p class="muted small" style="margin-top:4pt">Scores are the team's judgement from the evidence. A dead-ends on exceptions (half the KYC sample needed a fix or review); C keeps the visit that causes 827 drops and the Rs 20–24k channel cost.</p>
<h3>The journey: 11 screens on a phone</h3><div class="steps">{steps_html}</div><p class="muted small" style="margin-top:5pt">Pink steps are where a named agent can take over with full context.</p>"""))

pages.append(page("04", "Build", """
<h2>A working prototype, built and tested <em>phase by phase</em>.</h2>
<table><tr><th style="width:23%">Phase</th><th>What was built</th><th style="width:28%">What it proved</th></tr>
<tr><td><b>1 · Core advisor</b></td><td>OTP login, 8 languages, rules engine with a reason for every refusal, 6-question advisor with live GSTIN checksum, guarded LLM explanations, recommendation card</td><td>10/10 profiles valid; 31 rule checks; no product codes on screen</td></tr>
<tr><td><b>2 · Instant quote</b></td><td>Pricing rule (micro at minimum, others at midpoint), toggles, steppers, dependency locks with reasons, "vs what you pay now", accept → order</td><td>Rs 1,597 and Rs 6,055 reference bundles match the analysis</td></tr>
<tr><td><b>3 · Smart KYC</b></td><td>Versioned consent in 8 languages, GSTIN checksum and registry, Udyam lookup, OCR with watermark removal, deskew and blur checks, 13 cross-checks, verdicts that move the order</td><td>12/12 verdicts match the planted problems; 0 raw IDs on screen or in logs</td></tr>
<tr><td><b>4 · Tracker &amp; escalation</b></td><td>Order state machine, automatic install booking, SLA job, least-loaded language-matched assignment, callbacks inside working hours, agent console, order simulator</td><td>Late orders escalate unaided to the right agent</td></tr>
<tr><td><b>5 · Voice, WhatsApp, dashboard</b></td><td>Browser speech plus Sarvam/Bhashini adapters, short spoken replies; WhatsApp updates on 7 events + 24 h KYC reminder; propensity lead dashboard with Call and outcome; live metrics strip</td><td>Full Hindi voice chat; replies ≤ 180 characters; baselines reproduced live</td></tr>
<tr><td><b>6 · Hardening &amp; deploy</b></td><td>15 judge-style scenarios, unit tests, Playwright happy path on a phone viewport, security pass (PII-safe logs, retention purge, rate limits, secrets), Docker + Render + Vercel configs</td><td>192/192 tests; 0 page errors on the phone run</td></tr></table>
<h3>Stack</h3>
<div class="three">
<div class="box"><h4>Frontend</h4><p class="small" style="margin:0">Next.js 15 and Tailwind, mobile-first, 8 languages (hi, en, mr, ta, bn, kn, gu, te), Web Speech for voice.</p></div>
<div class="box"><h4>Backend</h4><p class="small" style="margin:0">FastAPI, SQLAlchemy and SQLite, Tesseract OCR, scikit-learn propensity model, background SLA and notification jobs.</p></div>
<div class="box"><h4>Providers</h4><p class="small" style="margin:0">LLM, GSTIN/Udyam registries, Twilio WhatsApp and Sarvam/Bhashini speech, each behind one interface with a mock for the demo.</p></div></div>
<div class="callout" style="font-size:9.6pt;margin-top:12pt">Demo: a 3-minute run from language to live on a phone, with a Hindi voice advisor, quote, KYC, tracker, an automatic escalation and the leads dashboard. The shot list and voiceover are in docs/demo_script.md.</div>"""))

pages.append(page("04", "Build · architecture", f"""
<h2>One API, six services, one database, and <em>a person in the loop</em>.</h2>
<div class="arch">{ARCH}</div>
<div class="keys">
<div class="key"><i style="background:#fff1f1;border:1.5px dashed {RED}"></i><span><b>Personal data protected.</b> The API masks IDs in responses and logs; KYC encrypts documents and ID numbers; SQLite encrypts PII columns; documents auto-delete.</span></div>
<div class="key"><i style="background:#fff3ec;border:1.5px solid #f0b48a"></i><span><b>A person steps in.</b> KYC review, late installs, a stuck advisor or "talk to a person" land in the agent queue with full context.</span></div>
<div class="key"><i style="background:#f4f4f6;border:1.5px dashed #b5b5bf"></i><span><b>Swappable providers.</b> LLM, registries, Twilio and Sarvam/Bhashini sit behind one interface each; mocks run the demo.</span></div>
<div class="key"><i style="background:#eaf2fd;border:1.5px solid #6c9bd2"></i><span><b>Main flows.</b> Owner → customer app → API → advisor, pricing, KYC, orders; staff → admin console; updates go out on WhatsApp to opted-in owners.</span></div></div>"""))

pages.append(page("05", "Results", f"""
<h2>Every claim is <em>tested</em>, including the judges' scenarios.</h2>
<div class="stats"><div class="stat"><b>192 / 192</b><span>automated tests pass</span></div><div class="stat"><b>15 / 15</b><span>judge-style advisor scenarios</span></div><div class="stat"><b>12 / 12</b><span>KYC verdicts correct</span></div><div class="stat"><b>0</b><span>page errors, language → live on a phone</span></div></div>
<h3>15 advisor scenarios, typed the way a judge would</h3>
<table class="tight"><tr><th>Scenario</th><th>Lang</th><th>Bundle</th><th class="n">Monthly</th><th>Refused (with reason)</th></tr>{sc_rows}</table>
<h3>Smart KYC on the 12 sample applicants</h3><div class="kg">{kyc_rows}</div><p class="muted small" style="margin-top:4pt">✓ = verdict matches the planted problem: 6 verified, 3 re-upload, 2 human review, 1 blocked.</p>
<div class="two" style="margin-top:4pt"><div><h3>Pilot baselines reproduce exactly</h3><p class="small">The admin dashboard recomputes the five metrics from the database: 7.4% conversion, 17.6 days, Rs 15,053 CAC, 15.2% churn and 3.0 chase calls, matching the Phase 1 analysis to the decimal.</p>
<p class="small">The suite also checks that logs never contain raw GSTIN, Udyam, PAN or phone numbers, that uploads need consent, and that the API refuses to start without real secrets.</p></div><div><h3>Phone run, language to live</h3><p class="small">A Playwright run on a Pixel 5 viewport completes all 11 screens with real uploads and no page errors, against a production-like backend.</p></div></div>"""))

pages.append(page("06", "Competitive analysis", f"""
<h2>Everyone sells to small businesses. <em>Nobody sells the whole journey.</em></h2>
<div class="stats"><div class="stat"><b>8.84 crore</b><span>enterprises on the Udyam portals, 30 Jun 2026 [1]</span></div><div class="stat"><b>12%</b><span>of MSMEs fully digitally mature (DMI 58.0) [2]</span></div><div class="stat"><b>&lt; 3%</b><span>SME adoption of enterprise digital services vs 75–90% for large firms [3]</span></div><div class="stat"><b>INR 954 bn</b><span>enterprise telecom opportunity through FY2030 [4]</span></div></div>
<p>The market is large, formalising fast and still mostly undigitised, which is why every Indian operator now runs an MSME programme. The question is how a business actually buys. From public information, the purchase still runs through a callback, an assessment or a booking followed by a wait; verification vendors sell components, not journeys.</p>
<div class="three" style="margin:8pt 0"><div class="box"><h4>Accel Telecom</h4><p class="small" style="margin:0">The case's fictional operator (a top-2 telco).</p></div><div class="box"><h4>Accel Business</h4><p class="small" style="margin:0">Its B2B arm and the seller; today one product at a time through field sales.</p></div><div class="box" style="border-color:{RED};background:#fff1f1"><h4>Udyam Digital = our product</h4><p class="small" style="margin:0">The digital journey Accel Business launches.</p></div></div>
<h3>Capability comparison</h3>
<table><tr><th>Capability</th><th class="c us">Udyam Digital</th><th class="c today">Accel Business today</th><th class="c">JioBusiness</th><th class="c">Vi Business</th><th class="c">Tata Tele</th><th class="c">BSNL / ACT</th><th class="c">KYC vendors</th></tr>{cmp_rows}</table>
<p class="muted small" style="margin-top:5pt">{F} yes, publicly evidenced · {P} partly · {N} not offered · {U} not public. Assessed from public sources, not from inside each product, so competitor ratings may understate unpublicised features.</p>"""))

pages.append(page("06", "Competitive analysis · profiles", """<div class="tightp">
<h2>Competitor profiles</h2>
<div class="two">
<div class="box"><h4>JioBusiness <span class="pill rose">high threat on price</span></h4>
<p><b>Offer.</b> Fibre plus productivity tools; seven plans from Rs 901 to Rs 10,001 at launch [5], now Business Broadband Max plans from Rs 801 with JioMeet and attendance tools [6].</p>
<p><b>How SMBs buy.</b> Register interest and wait for an executive [7]; the page still leads with "Want a callback?", and the app manages accounts after purchase [8].</p>
<p style="margin:0"><b>Our edge.</b> Purchase and KYC finish in one session; the price is transparent and rules-checked.</p></div>
<div class="box"><h4>Vi Business <span class="pill peach">advisory leader</span></h4>
<p><b>Offer.</b> Ready for Next: a free 10-minute digital maturity assessment with Dun &amp; Bradstreet [9]; 1.9 lakh MSMEs assessed by Feb 2025 [10]; state MoUs with local-language training [11][12].</p>
<p><b>Gap.</b> Diagnoses needs without turning them into a priced, eligible bundle.</p>
<p style="margin:0"><b>Our edge.</b> Six questions end in a plan with one monthly price the owner can buy immediately.</p></div>
<div class="box"><h4>Tata Tele Business <span class="pill rose">closest strategic rival</span></h4>
<p><b>Offer.</b> 100% SMB-focused [13]; Smartflo cloud communications and a WhatsApp Business platform [14].</p>
<p><b>Direction.</b> July 2026: a unified AI stack with Tata Communications, including voice agents and a digital B2B exchange [15].</p>
<p style="margin:0"><b>Our edge.</b> A working journey today, with KYC, tracking and an 8-language voice layer.</p></div>
<div class="box"><h4>BSNL &amp; ACT Fibernet <span class="pill mint">low threat on experience</span></h4>
<p><b>Offer.</b> BSNL takes bookings online or via WhatsApp "Hi" with document upload; an engineer calls within 3–7 days [16][17]. ACT sells city-specific SME plans [18].</p>
<p style="margin:0"><b>Our edge.</b> Bundle advice, an instant quote, expected dates and a live tracker.</p></div>
<div class="box"><h4>IDfy · Signzy · HyperVerge <span class="pill sky">partners, not rivals</span></h4>
<p><b>Offer.</b> GSTN and Udyam verification, OCR and video KYC as APIs [19][20][21].</p>
<p style="margin:0"><b>Our position.</b> KYC checks sit behind one interface, so a vendor API replaces the mock registry without changing the journey.</p></div>
<div class="box"><h4>The status quo <span class="pill grey">the real competitor</span></h4>
<p>A visit, a hand-made quote, paper KYC and 17.6 days; 15% of sold bundles break catalogue rules; customers chase status 3 times.</p>
<p style="margin:0"><b>Our edge.</b> Every leak in the data has a feature aimed at it and a metric to prove it.</p></div></div>
<h3>Positioning</h3>
<table><tr><th></th><th>Advice before buying</th><th>How the purchase happens</th><th>After purchase</th></tr>
<tr><td><b>Operators (Jio, Vi, Tata Tele)</b></td><td>Plan pages; Vi's maturity assessment</td><td>Callback, sales executive or partner</td><td>Self-care apps and portals</td></tr>
<tr><td><b>Fixed-line ISPs (BSNL, ACT)</b></td><td>City plan lists</td><td>Online booking, then an engineer visit</td><td>Self-care portal</td></tr>
<tr><td class="us"><b>Udyam Digital</b></td><td class="us">6-question advisor, eligible bundle with reasons</td><td class="us">Instant quote, consent, KYC checked on upload, one session</td><td class="us">Live tracker, WhatsApp updates, named agent when late</td></tr></table>
<h3>How rivals could respond, and our defence</h3>
<ul class="small"><li><b>Price cuts (Jio).</b> Speed and clarity drive more drops (41.2%) than price (23.9%), and micro customers already get catalogue-minimum pricing.</li>
<li><b>AI agents (Tata).</b> Our moat is the deterministic rules engine and the KYC and escalation plumbing behind the conversation.</li>
<li><b>Advisory reach (Vi).</b> Route assessment-style traffic straight into the advisor so diagnosis ends in a purchase.</li></ul></div>"""))

pages.append(page("07", "Impact", f"""
<h2>What a 6-month pilot could change, <em>per quarter of leads</em>.</h2>
<p class="lede">Targets come from the data: professional offices already convert at 11.1%, referrals at 14.8%, and core installs take 5 days. They are pilot proposals, not results.</p>
<h3>The five pilot metrics: baseline (Apr–Jun 2026) → 6-month target</h3>{dumbbell()}
<h3>What the targets mean in numbers</h3>
<table><tr><th>Per quarter</th><th class="n">Today, 5,000 leads</th><th class="n">Pilot targets, 5,000 leads</th><th class="n">Pilot targets, 50,000 leads</th></tr>
<tr><td>Activations</td><td class="n">{fmt(I5['a0'])}</td><td class="n"><b>{fmt(I5['a1'])}</b> (+{fmt(I5['extra'])})</td><td class="n"><b>{fmt(I50['a1'])}</b> (+{fmt(I50['extra'])})</td></tr>
<tr><td>Acquisition spend</td><td class="n">{cr(I5['spend0'])}</td><td class="n"><b>{cr(I5['spend1'])}</b></td><td class="n"><b>{cr(I50['spend1'])}</b> (vs {cr(I50['spend0'])})</td></tr>
<tr><td>Status-chase calls</td><td class="n">{fmt(I5['calls0'])}</td><td class="n"><b>{fmt(I5['calls1'])}</b></td><td class="n"><b>{fmt(I50['calls1'])}</b> (vs {fmt(I50['calls0'])})</td></tr>
<tr><td>Extra customers still paying at 6 months</td><td class="n">—</td><td class="n"><b>+{fmt(I5['kept'])}</b></td><td class="n"><b>+{fmt(I50['kept'])}</b></td></tr>
<tr><td>Added yearly revenue from them (× Rs 6,900)</td><td class="n">—</td><td class="n"><b>{cr(I5['rev'])}</b></td><td class="n"><b>{cr(I50['rev'])}</b></td></tr></table>
<p class="muted small" style="margin-top:4pt">Arithmetic on the stated targets and the dataset's baselines (7.4%, Rs 15,053, 3.0 calls, 15.2% churn, Rs 6,900 median bundle).</p>
<div class="two">
<div class="box"><h4>Proven in the build <span class="pill mint">now</span></h4><ul class="small">
<li>Zero ineligible bundles: checked by 30 rule tests and 25 advisor scenarios.</li><li>One-session journey on a phone, language to live, with real uploads.</li><li>Bad documents caught at upload with a specific fix.</li><li>Late steps escalate unaided to the right agent.</li></ul></div>
<div class="box"><h4>To validate in the pilot <span class="pill peach">next</span></h4><ul class="small">
<li>Share of drops recovered: 32% (directly addressable) to 69% (including partly).</li><li>A 50/50 self-serve / assisted mix, assisted deals 40% cheaper.</li><li>KYC completion 68.3% → 85%; first response to escalations within 4 business hours.</li><li>Whether vernacular voice closes the quote gap (40% regional vs 45%).</li></ul></div></div>
<h3>Beyond the numbers</h3>
<div class="three"><div class="box"><h4>For owners</h4><p class="small" style="margin:0">No visit, no wait for a quote, one clear price in their language, and a date to check instead of calling.</p></div><div class="box"><h4>For Accel Business</h4><p class="small" style="margin:0">Higher conversion and lower CAC with zero ineligible sales and reproducible decisions.</p></div><div class="box"><h4>For the field force</h4><p class="small" style="margin:0">Time on multi-site deals, KYC exceptions and High-propensity leads, with credit for app-completed sales.</p></div></div>"""))

pages.append(page("08", "Privacy, security &amp; next steps", f"""
<h2>Collect the minimum, protect it, and <em>delete it when the purpose ends</em>.</h2>
<h3>The personal-data pipeline</h3><div class="pipe">{pipe_html}</div>
<div class="two">
<div><h3>Controls on every step</h3><div class="rails"><span>HTTPS only</span><span>Fernet-encrypted PII and files</span><span>Phone as keyed hash</span><span>Masked IDs in UI and logs</span><span>Role-based access</span><span>Audit log of every view</span><span>Rate limits</span><span>Secrets from env only</span></div></div>
<div><h3>Maps to the DPDP Act 2023 <span class="muted small" style="font-weight:400">· our reading, not legal advice</span></h3><table class="tight"><tr><th>Choice</th><th>DPDP point</th></tr>
<tr><td>Notice and explicit consent before KYC</td><td>s.5 notice, s.6 consent</td></tr><tr><td>KYC used only for verification</td><td>Purpose limitation</td></tr><tr><td>Per-step minimisation</td><td>Only data necessary (s.6(1))</td></tr><tr><td>One-tap withdrawal with deletion</td><td>s.6(4), erasure (s.12)</td></tr><tr><td>Auto-deletion after the purpose ends</td><td>s.8(7)</td></tr><tr><td>Encryption, masking, access control, audit</td><td>Security safeguards (s.8(5))</td></tr><tr><td>Owner sees status and data; can ask for help</td><td>s.11, grievance (s.13)</td></tr></table></div></div>
<h3>Next steps</h3>
<div class="three">
<div class="box" style="border-top:2.5pt solid {RED}"><h4>0–3 months · Pilot</h4><ul class="small" style="margin:0"><li>Professional offices in 2 tier-1 cities</li><li>Real GSTN / Udyam lookups via a GSP or KYC vendor</li><li>DigiLocker documents, Aadhaar e-sign</li><li>Grievance officer and published notice</li></ul></div>
<div class="box" style="border-top:2.5pt solid {RED2}"><h4>3–6 months · Scale</h4><ul class="small" style="margin:0"><li>WhatsApp Business API and real SMS OTP</li><li>Postgres with keys in a cloud KMS</li><li>Partner and field-force portal with shared credit</li><li>Micro-retail wave, lean bundle</li></ul></div>
<div class="box" style="border-top:2.5pt solid {RED3}"><h4>6+ months · Later</h4><ul class="small" style="margin:0"><li>DPDP consent manager integration</li><li>Voice-first flow on WhatsApp</li><li>Retrain propensity on live outcomes; bias checks</li><li>Single bill and one support number</li></ul></div></div>"""))

pages.append(page("09", "Sources", f"""
<h2>Sources</h2>
<p>Project figures: the supplied synthetic dataset (smb_leads.csv, product_catalogue.csv, mock GSTIN and Udyam registries, 47 KYC images) and the project's analysis, test and end-to-end outputs (docs/kyc_results.md, docs/advisor_scenarios.md, the 192-test suite). Market and competitor facts:</p>
<ol class="src">{src_html}</ol>
<div class="callout" style="margin-top:14pt">Interactive version: the Udyam Digital showcase website, with the demo video, live charts, the impact calculator and the architecture diagram.</div>""", "src"))

html = f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Udyam Digital — Approach, Competitive Analysis and Impact</title><style>{css}</style></head><body>{"".join(pages)}</body></html>'
(B / "pdf.html").write_text(html, encoding="utf-8")
out = SITE / "Udyam_Digital_Approach_Competition_Impact.pdf"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 794, "height": 1123})
    pg.goto((B / "pdf.html").as_uri()); pg.wait_for_timeout(400)
    over = pg.evaluate("""[...document.querySelectorAll('.page')].map((p,i)=>{const f=p.querySelector('footer');let m=0;[...p.children].forEach(c=>{if(c.tagName!=='FOOTER'&&!c.classList.contains('wm')&&!c.classList.contains('bg')&&!c.classList.contains('globe')&&!c.classList.contains('inner')){m=Math.max(m,c.getBoundingClientRect().bottom)}});return [i+1, f? Math.round(f.getBoundingClientRect().top - m):null]})""")
    print("gap above footer (px, negative = overflow):", over)
    pg.pdf(path=str(out), print_background=True, prefer_css_page_size=True)
    b.close()
print(out, out.stat().st_size)
