import json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from demo import DEMO, markdown

B = Path(__file__).parent
ROOT = B.parent
d = json.load(open(B / "site_data.json"))
t = (B / "template.html").read_text()
ph = (B / "ph.js").read_text().split("=", 1)[1].strip().rstrip(";")
ph = re.sub(r'\["(p4_agent|p5_leads|p5_outbox)", ("[^"]*")\]', r'["\1", \2, 1]', ph)
src = json.load(open(B / "sources.json"))

html = (t.replace("__DATA__", json.dumps(d, ensure_ascii=False))
         .replace("__PHASES__", ph)
         .replace("__DEMO__", json.dumps(DEMO, ensure_ascii=False))
         .replace("__SOURCES__", json.dumps(src, ensure_ascii=False)))
(ROOT / "site" / "index.html").write_text(html)
(ROOT / "site" / "demo_script.md").write_text(markdown())
(ROOT / "site" / "vercel.json").write_text(json.dumps({"cleanUrls": True, "headers": [{"source": "/(.*)", "headers": [
    {"key": "X-Content-Type-Options", "value": "nosniff"}, {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"}]}]}, indent=2))

# artifact copy: no download links (files are not served there)
a = re.sub(r"<p class=\"small dl[^\"]*\"[^>]*>.*?</p>", "", html, flags=re.S)
a = re.sub(r'<p class="mt dl">.*?</p>', "", a, flags=re.S)
(ROOT / "artifact").mkdir(exist_ok=True); (ROOT / "artifact" / "img").mkdir(exist_ok=True)
(ROOT / "artifact" / "index.html").write_text(a)
for f in (ROOT / "site" / "img").glob("*"):
    if f.suffix in (".jpg", ".svg"):
        shutil.copy(f, ROOT / "artifact" / "img" / f.name)
print("ok", len(html))
