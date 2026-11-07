"""One layout, two outputs: a slide-ready SVG (then PNG) and an editable draw.io file of the Udyam Digital architecture."""
from html import escape
from pathlib import Path

W, H = 1600, 900
OUT = Path("/home/claude/arch")
STYLE = {  # fill, stroke, dashed, text
    "user": ("#eaf2fc", "#2a78d6", False, "#0d2f5c"),
    "core": ("#ffffff", "#9a978e", False, "#141414"),
    "pii": ("#fff5f6", "#c8102e", True, "#141414"),
    "human": ("#fff3df", "#b8780a", False, "#3d2a00"),
    "ext": ("#f3f1eb", "#aaa79e", True, "#4d4c48"),
}
# id: (x, y, w, h, kind, title, [lines], badge)
N = {
    "own": (30, 130, 200, 96, "user", "Business owner", ["Mobile web · text + voice", "8 languages"], None),
    "wa": (30, 380, 200, 76, "user", "WhatsApp", ["Opt-in status updates"], None),
    "staff": (30, 610, 200, 76, "user", "Staff", ["Agents · admin"], None),
    "app": (275, 112, 210, 132, "core", "Customer app", ["Advisor · quote · consent", "KYC · tracker", "Web Speech API (voice)"], "SHOWS MASKED IDs ONLY"),
    "con": (275, 592, 210, 112, "core", "Admin console", ["Leads · escalations", "Outbox · simulator"], "AUDIT-LOGGED VIEWS"),
    "api": (530, 300, 190, 200, "pii", "API · FastAPI", ["HTTPS + JWT roles", "Rate limits", "PII-scrubbed logs", "Masked responses"], "MASKS IDs"),
    "adv": (785, 112, 210, 112, "core", "Advisor", ["LLM explains", "Rules engine decides"], None),
    "pri": (1020, 112, 200, 112, "core", "Pricing", ["One monthly price", "Dependency locks"], None),
    "kyc": (785, 250, 210, 112, "pii", "Smart KYC", ["Consent first", "GSTIN / Udyam lookup", "OCR → 13 checks"], "ENCRYPTS DOCS + IDs"),
    "notf": (1020, 250, 200, 112, "core", "Notifications", ["8-language templates", "Opt-in enforced"], None),
    "ord": (785, 388, 210, 112, "core", "Orders & tracker", ["State machine · dates", "SLA escalation job"], None),
    "adm": (1020, 388, 200, 112, "core", "Admin analytics", ["Propensity model", "Live pilot metrics"], None),
    "q": (785, 592, 435, 112, "human", "Agent queue: humans step in", ["KYC review · late install · advisor stuck · \"talk to a person\"", "Assigned to the least-loaded agent who speaks the customer's language"], None),
    "db": (1290, 112, 280, 132, "pii", "SQLite", ["PII columns encrypted (Fernet)", "Phone stored as keyed hash", "Events · consents · audit log"], "ENCRYPTED AT REST"),
    "fs": (1290, 290, 280, 112, "pii", "Document store", ["Each file encrypted", "Deleted 90 days after verify", "(30 if abandoned)"], "AUTO-DELETED"),
    "llm": (1290, 470, 132, 60, "ext", "LLM", ["explains only"], None),
    "reg": (1438, 470, 132, 60, "ext", "GSTIN / Udyam", ["registries (mock)"], None),
    "tw": (1290, 548, 132, 60, "ext", "Twilio", ["or mock outbox"], None),
    "sp": (1438, 548, 132, 60, "ext", "Speech API", ["Sarvam / Bhashini"], None),
}
GROUPS = [  # x, y, w, h, label, fill, stroke
    (765, 72, 475, 446, "SERVICES", "#faf9f6", "#d9d6cd"),
    (765, 552, 475, 170, "HUMANS", "#fffaf0", "#e6c27a"),
    (1272, 72, 316, 348, "DATA", "#fdf6f7", "#e8b4bd"),
    (1272, 440, 316, 186, "SWAPPABLE PROVIDERS", "#faf9f6", "#d9d6cd"),
]
# edges: points, label, dashed
E = [
    ([(230, 178), (275, 178)], None, False),
    ([(230, 648), (275, 648)], None, False),
    ([(485, 178), (507, 178), (507, 360), (530, 360)], None, False),
    ([(485, 648), (507, 648), (507, 440), (530, 440)], None, False),
    ([(720, 400), (765, 400)], None, False),
    ([(995, 168), (1020, 168)], None, False),
    ([(1240, 178), (1272, 178)], "read / write", False),
    ([(995, 306), (1008, 306), (1008, 236), (1258, 236), (1258, 346), (1290, 346)], None, False),
    ([(1240, 470), (1272, 470)], None, True),
    ([(985, 518), (985, 592)], "flag · late · stuck", False),
    ([(785, 680), (740, 680), (740, 676), (485, 676)], "picked up with full context", False),
    ([(1356, 608), (1356, 860), (15, 860), (15, 418), (30, 418)], "WhatsApp updates to opted-in owners", True),
]


def text_block(x, y, w, h, title, lines, color):
    cx = x + w / 2
    n = len(lines)
    total = 20 + n * 17
    ty = y + h / 2 - total / 2 + 15
    out = [f'<text x="{cx}" y="{ty}" text-anchor="middle" font-size="15" font-weight="700" fill="{color}">{escape(title)}</text>']
    for i, l in enumerate(lines):
        out.append(f'<text x="{cx}" y="{ty + 21 + i * 17}" text-anchor="middle" font-size="12.5" fill="{color}" opacity=".85">{escape(l)}</text>')
    return out


def svg():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif">',
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#6f6d66"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         '<text x="30" y="46" font-size="24" font-weight="700" fill="#141414">Udyam Digital · system architecture</text>',
         '<text x="30" y="70" font-size="13.5" fill="#6f6d66">AI handles acquisition; humans handle exceptions. Rules decide eligibility; the LLM only explains.</text>']
    for x, y, w, h, lab, fill, stroke in GROUPS:
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}"/>')
        o.append(f'<text x="{x + 14}" y="{y + 22}" font-size="11" font-weight="700" letter-spacing="1.4" fill="#85837c">{lab}</text>')
    for pts, label, dashed in E:
        d = "M" + " L".join(f"{px},{py}" for px, py in pts)
        o.append(f'<path d="{d}" fill="none" stroke="#6f6d66" stroke-width="1.6" {"stroke-dasharray=\"6 4\"" if dashed else ""} marker-end="url(#a)"/>')
        if label:
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            if len(pts) > 3 and label.startswith("WhatsApp"):
                mx, my = 700, 852
            elif label.startswith("picked"):
                mx, my = 612, 668
            elif label.startswith("flag"):
                mx, my = 993, 560
            else:
                mx, my = (x1 + x2) / 2, min(y1, y2) - 8
            anchor = "start" if label.startswith("flag") else "middle"
            o.append(f'<text x="{mx}" y="{my}" text-anchor="{anchor}" font-size="11.5" fill="#4d4c48" font-style="italic">{escape(label)}</text>')
    for k, (x, y, w, h, kind, title, lines, badge) in N.items():
        fill, stroke, dashed, color = STYLE[kind]
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="{2 if kind in ("pii", "human") else 1.4}" {"stroke-dasharray=\"7 4\"" if dashed else ""}/>')
        o += text_block(x, y, w, h, title, lines, color)
        if badge:
            bw = len(badge) * 6.6 + 16
            bc = "#c8102e" if kind == "pii" else "#4d4c48"
            o.append(f'<rect x="{x + w - bw - 8}" y="{y - 10}" width="{bw}" height="19" rx="9.5" fill="{bc}"/>')
            o.append(f'<text x="{x + w - bw / 2 - 8}" y="{y + 3.5}" text-anchor="middle" font-size="10" font-weight="700" letter-spacing=".6" fill="#fff">{badge}</text>')
    # legend
    lx, ly = 30, 748
    items = [("pii", "Personal data protected here (masked / encrypted)"), ("human", "A person steps in"), ("ext", "Swappable provider (mock in demo)"), ("user", "People")]
    o.append(f'<text x="{lx}" y="{ly - 4}" font-size="11" font-weight="700" letter-spacing="1.4" fill="#85837c">LEGEND</text>')
    for i, (k, t) in enumerate(items):
        fill, stroke, dashed, _ = STYLE[k]
        yy = ly + 10 + i * 24
        o.append(f'<rect x="{lx}" y="{yy}" width="28" height="16" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="2" {"stroke-dasharray=\"5 3\"" if dashed else ""}/>')
        o.append(f'<text x="{lx + 38}" y="{yy + 12.5}" font-size="12.5" fill="#4d4c48">{t}</text>')
    o.append('<text x="1570" y="888" text-anchor="end" font-size="11" fill="#85837c">IDs shown as 27•••••••••1Z5 · ••••••4321 · consent before any document (DPDP Act 2023)</text>')
    o.append("</svg>")
    return "\n".join(o)


def drawio():
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    i = 2
    for x, y, w, h, lab, fill, stroke in GROUPS:
        cells.append(f'<mxCell id="g{i}" value="{lab}" style="rounded=1;arcSize=4;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};verticalAlign=top;align=left;spacingLeft=12;spacingTop=4;fontSize=11;fontStyle=1;fontColor=#85837c;" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        i += 1
    for k, (x, y, w, h, kind, title, lines, badge) in N.items():
        fill, stroke, dashed, color = STYLE[kind]
        val = f"<b>{escape(title)}</b><br><font style='font-size:11px'>{'<br>'.join(escape(l) for l in lines)}</font>"
        if badge:
            val += f"<br><font color='{stroke}' style='font-size:9px'><b>{badge}</b></font>"
        st = (f"rounded=1;arcSize=10;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontColor={color};fontSize=13;"
              f"strokeWidth={2 if kind in ('pii', 'human') else 1};" + ("dashed=1;" if dashed else "") + ("shape=cylinder3;boundedLbl=1;size=10;" if k in ("db", "fs") else ""))
        cells.append(f'<mxCell id="{k}" value="{escape(val, quote=True)}" style="{st}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    for j, (pts, label, dashed) in enumerate(E):
        (sx, sy), (tx, ty) = pts[0], pts[-1]
        mids = "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in pts[1:-1])
        st = "edgeStyle=none;html=1;endArrow=block;endFill=1;strokeColor=#6f6d66;fontSize=11;fontStyle=2;" + ("dashed=1;" if dashed else "")
        cells.append(f'<mxCell id="e{j}" value="{escape(label or "")}" style="{st}" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="{sx}" y="{sy}" as="sourcePoint"/><mxPoint x="{tx}" y="{ty}" as="targetPoint"/>{"<Array as=\"points\">" + mids + "</Array>" if mids else ""}</mxGeometry></mxCell>')
    cells.append('<mxCell id="title" value="&lt;b&gt;Udyam Digital · system architecture&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:12px&quot; color=&quot;#6f6d66&quot;&gt;AI handles acquisition; humans handle exceptions. Rules decide eligibility; the LLM only explains.&lt;/font&gt;" style="text;html=1;align=left;fontSize=20;" vertex="1" parent="1"><mxGeometry x="30" y="20" width="900" height="56" as="geometry"/></mxCell>')
    leg = "<b>Legend</b><br>Red dashed: personal data masked / encrypted<br>Amber: a person steps in<br>Grey dashed: swappable provider (mock in demo)<br>Blue: people"
    cells.append(f'<mxCell id="legend" value="{escape(leg, quote=True)}" style="text;html=1;align=left;verticalAlign=top;fontSize=12;fontColor=#4d4c48;" vertex="1" parent="1"><mxGeometry x="30" y="740" width="420" height="110" as="geometry"/></mxCell>')
    return (f'<mxfile host="app.diagrams.net"><diagram id="udyam-arch" name="Architecture"><mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" '
            f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{W}" pageHeight="{H}" math="0" shadow="0"><root>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>')


(OUT / "architecture.svg").write_text(svg(), encoding="utf-8")
(OUT / "architecture.drawio").write_text(drawio(), encoding="utf-8")
print("ok")
