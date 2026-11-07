import re
import sys
from pathlib import Path

doc = Path(sys.argv[1]).read_text()


def section(start, end):
    a = doc.index(start)
    b = doc.index(end, a) if end else len(doc)
    return doc[a:b]


d2 = section("# D2. Database schema", "# D3. API contracts")
d3 = section("# D3. API contracts", "# D4. Order state machine")
d71 = section("## D7.1 Screen", "## D7.2")

tables = re.findall(r"^\*\*([a-z_]+)\*\*", d2, re.M)
tables = [t for t in tables if t not in {"Rules"}]
ep_re = r"`(GET|POST|PATCH|PUT|DELETE) (/[^`\s]+)`"
d3_eps = set()
for line in d3.splitlines():
    if line.startswith("### ") or line.startswith("| `"):
        d3_eps |= {f"{m} {p}" for m, p in re.findall(ep_re, line)}
screen_eps = {f"{m} {p}" for m, p in re.findall(ep_re, d71.split("Endpoints with no screen")[0])}
backend_only = {f"{m} {p}" for m, p in re.findall(ep_re, d71.split("Endpoints with no screen")[1])}

used = set()
for line in d3.splitlines():
    if line.startswith("Tables:") or line.startswith("| `"):
        for t in tables:
            if re.search(rf"`{t}`", line) or re.search(rf"\b{t}\b", line.split("|")[-2] if line.startswith("|") else line):
                used.add(t)

problems = []
for e in sorted(screen_eps - d3_eps):
    problems.append(f"screen endpoint not specified in D3: {e}")
for e in sorted(backend_only - d3_eps):
    problems.append(f"backend-only endpoint not specified in D3: {e}")
for e in sorted(d3_eps - screen_eps - backend_only):
    problems.append(f"D3 endpoint not mapped to a screen or listed as backend-only: {e}")
for t in tables:
    if t not in used:
        problems.append(f"table never used by an endpoint: {t}")
no_tables = []
blocks = re.split(r"^### ", d3, flags=re.M)[1:]
for b in blocks:
    head = b.splitlines()[0]
    if "Tables:" not in b:
        no_tables.append(head)
for h in no_tables:
    problems.append(f"endpoint block without a Tables line: {h}")

print(f"Tables in D2: {len(tables)} -> {', '.join(tables)}")
print(f"Endpoints in D3: {len(d3_eps)}; mapped to screens: {len(screen_eps)}; backend-only: {len(backend_only)}")
print(f"Tables used by endpoints: {len(used)}/{len(tables)}")
print("RESULT: PASS" if not problems else "RESULT: FAIL")
for p in problems:
    print(" -", p)
sys.exit(1 if problems else 0)
