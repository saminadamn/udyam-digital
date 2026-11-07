import json
import sys
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "analysis"))
sys.argv = [sys.argv[0], str(root)]
import validate_bundles as vb

c = root / "data" / "clean"


def plain(df):
    df = df.astype({k: "object" for k in df.select_dtypes(["category", "string"]).columns})
    return df.astype({k: "float64" for k in df.select_dtypes(["Int8", "Int16", "Int32", "Int64", "Float64"]).columns})


L = plain(pd.read_parquet(c / "leads.parquet"))
A = plain(pd.read_parquet(c / "activated.parquet"))
cat = vb.CAT
names = cat.product_name.to_dict()
L["act"] = (L.outcome == "Activated").astype(int)
share = {"Micro retail & services": 0.55, "Professional offices": 0.25, "Small multi-site businesses": 0.15, "Small manufacturers": 0.05}

out = []
p = out.append
p("# Segments, starter bundles and success metrics\n")
p("Built from smb_leads.csv and product_catalogue.csv. Every bundle below is checked by `analysis/validate_bundles.py` against the catalogue rules.\n")

rows = []
for s in share:
    g, a = L[L.segment == s], A[A.segment == s]
    conv, val, churn = g.act.mean(), a.monthly_bundle_value_inr.median(), a.churn.mean()
    cac = g.acquisition_cost_inr.sum() / g.act.sum()
    rows.append({"segment": s, "share of base": share[s], "conversion": conv, "median bundle Rs/mo": val, "6m churn": churn,
                 "score": share[s] * conv * val / churn, "CAC per activation": cac, "payback (months)": cac / val,
                 "leads in data": len(g), "activated": int(g.act.sum())})
R = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
R["rank"] = R.index + 1
R["score (index, top=100)"] = (R.score / R.score.max() * 100).round(0).astype(int)
show = R[["rank", "segment", "share of base", "conversion", "median bundle Rs/mo", "6m churn", "score (index, top=100)", "CAC per activation", "payback (months)"]].copy()
show["share of base"] = (show["share of base"] * 100).astype(int).astype(str) + "%"
show["conversion"] = (show.conversion * 100).round(1).astype(str) + "%"
show["6m churn"] = (show["6m churn"] * 100).round(1).astype(str) + "%"
show["median bundle Rs/mo"] = show["median bundle Rs/mo"].map("{:,.0f}".format)
show["CAC per activation"] = show["CAC per activation"].map("{:,.0f}".format)
show["payback (months)"] = show["payback (months)"].round(1)
p("## 1. Segment ranking\n")
p("Score = share of base × conversion × median monthly bundle value × 1 / 6-month churn (shown as an index, top segment = 100).\n")
p(show.to_markdown(index=False))
prof = R.set_index("segment").loc["Professional offices"]
multi = R.set_index("segment").loc["Small multi-site businesses"]
micro = R.set_index("segment").loc["Micro retail & services"]
p("")
p("### Launch first: Professional offices (clinics, CA firms, coaching centres)\n")
p(f"1. Multi-site tops the formula (index 100 vs {round(prof['score'] / multi['score'] * 100)}), but its bundle needs SD-WAN across {int(A[A.segment=='Small multi-site businesses'].num_sites.median())} sites and 14-day installs, so it can't close without a human; it runs alongside as the field-assisted track.")
p(f"2. Professional offices are the best self-serve fit: {prof['conversion']:.1%} conversion, the lowest CAC of any segment (Rs {prof['CAC per activation']:,.0f}), {prof['payback (months)']:.1f}-month payback, one site and 5-day installs.")
p(f"3. They give the advisor and Smart KYC a clean proving ground ({A[A.segment=='Professional offices'].gst_status.eq('Active').mean():.0%} have an active GSTIN), before scaling to micro, which is {micro['share of base']:.0%} of the base but converts at {micro['conversion']:.1%} with an {micro['payback (months)']:.0f}-month payback today.\n")

spec = json.loads((root / "analysis" / "bundles.json").read_text())
res = vb.validate(spec)
neg = vb.negative_tests()
p("## 2. Starter bundles\n")
p(f"Quantity rule: {spec['quantity_rule']}  ")
p(f"Pricing rule: {spec['pricing_rule']}\n")
for b in spec["bundles"]:
    a = A[A.segment == b["segment"]]
    p(f"### {b['name']} ({b['segment']})\n")
    p(f"*Why these products:* {b['basis']}\n")
    p("| item | product | qty | Rs/unit/mo | setup/unit | install days | GSTIN? |")
    p("|---|---|---|---|---|---|---|")
    typical = b["profiles"][0]
    items = vb.scale(b["core"], typical, set(b.get("per_site", [])), set(b.get("per_user", [])))
    adds = vb.scale(b["addons"], typical, set(b.get("per_site", [])), set(b.get("per_user", [])))
    for tag, group in [("core", items), ("add-on", adds), ("add-on, GSTIN only", [tuple(x) for x in b.get("gstin_only_addons", [])])]:
        for pid, q in group:
            r = cat.loc[pid]
            lo, hi = int(r.price_min_inr_per_month), int(r.price_max_inr_per_month)
            unit = lo if b["key"] == "micro" else round((lo + hi) / 2)
            p(f"| {tag} | {pid} {names[pid]} | {q} | {unit:,} (range {lo:,}-{hi:,}) | {int(r.one_time_setup_inr):,} | {r.typical_install_days} | {r.requires_gstin} |")
    p("")
    p("| profile | variant | monthly | setup | contract | install | rule check |")
    p("|---|---|---|---|---|---|---|")
    for r in [x for x in res if x["bundle"] == b["name"]]:
        check = "PASS" if r["offered"] else "blocked: " + "; ".join(r["errors"])
        money = (f"Rs {r['monthly']:,}", f"Rs {r['setup']:,}", f"{r['contract']} mo", f"{r['install_days']} days") if r["offered"] else ("-", "-", "-", "-")
        p(f"| {r['profile']} | {r['variant']} | {money[0]} | {money[1]} | {money[2]} | {money[3]} | {check} |")
    p(f"\nWhat this segment pays today (activated customers): median Rs {a.monthly_bundle_value_inr.median():,.0f}/mo, median setup Rs {a.one_time_setup_inr.median():,.0f}, median contract {a.contract_months.median():.0f} months.")
    if b.get("fallback"):
        p(f"Fallback: if {b['fallback']['when']}, swap {b['fallback']['swap'][0]} for {b['fallback']['swap'][1]} ({names[b['fallback']['swap'][1]]}).")
    if b.get("tier1_upgrade"):
        p(f"Upgrade: {b['tier1_upgrade']['note']}.")
    p("")
p("### Rule checks the advisor must refuse\n")
p("| case | blocked because | result |\n|---|---|---|")
for n in neg:
    p(f"| {n['case']} | {'; '.join(n['errors'])} | {'PASS' if n['ok'] else 'FAIL'} |")
failures = sum(not r["ok"] for r in res) + sum(not n["ok"] for n in neg)
p(f"\n**Validation: {len(res)} bundle checks and {len(neg)} negative checks, {failures} failures.**\n")

conv_base = L.act.mean()
days_base = A.days_lead_to_activation.mean()
cac_base = L.acquisition_cost_inr.sum() / L.act.sum()
churn_base = A.churn.mean()
calls_base = A.customer_follow_up_calls.mean()
pre_quote = (pd.to_datetime(A.quote_accepted_date) - pd.to_datetime(A.created_date)).dt.days.mean()
quote_kyc = (pd.to_datetime(A.kyc_complete_date) - pd.to_datetime(A.quote_accepted_date)).dt.days.mean()
kyc_act = (pd.to_datetime(A.activated_date) - pd.to_datetime(A.kyc_complete_date)).dt.days.mean()
ref_conv = L[L.lead_source == "Referral"].act.mean()
churn_1call = A[A.customer_follow_up_calls <= 1].churn.mean()
churn_2call = A[A.customer_follow_up_calls == 2].churn.mean()
digital = L[L.lead_source.isin(["Website form", "WhatsApp campaign"])]
digital_cpl = digital.acquisition_cost_inr.mean()
install_core = {b["name"]: max(int(cat.loc[pid].typical_install_days) for pid, _ in b["core"]) for b in spec["bundles"]}
target_conv, target_days, target_churn, target_calls = 0.11, 8, 0.11, 0.5
self_serve_cac = digital_cpl / target_conv
fp = L[L.lead_source.isin(["Field sales", "Channel partner"])]
assisted_cac = fp.acquisition_cost_inr.sum() / fp.act.sum()
blend = 0.5 * self_serve_cac + 0.5 * assisted_cac * 0.6
target_cac = int(round(blend / 500) * 500)

p("## 3. Success metrics\n")
p("| # | metric | baseline (Apr-Jun 2026) | 6-month pilot target | how we get there |")
p("|---|---|---|---|---|")
p(f"| 1 | Lead-to-activation conversion | {conv_base:.1%} | {target_conv:.0%} | Professional offices already convert at {prof['conversion']:.1%} and referrals at {ref_conv:.1%}; removing the visit and the slow quote attacks the 41% of drops caused by reach and speed. |")
p(f"| 2 | Days from lead to activation | {days_base:.1f} | {target_days} | {pre_quote:.1f} days pass before the quote is accepted today and {quote_kyc:.1f} more for KYC; one session plus instant lookups removes most of that, leaving install time (core bundles: {install_core['Dukaan Digital']} days micro, {install_core['Office Pro']} days professional). |")
p(f"| 3 | CAC per activation | Rs {cac_base:,.0f} | Rs {target_cac:,} | Digital leads cost Rs {digital_cpl:,.0f} each; at {target_conv:.0%} conversion that's about Rs {self_serve_cac:,.0f} per self-serve activation. Field and partner deals cost Rs {assisted_cac:,.0f} today; if they cost 40% less because the app does discovery and KYC, a 50/50 self-serve/assisted mix gives Rs {blend:,.0f}. |")
p(f"| 4 | 6-month churn | {churn_base:.1%} | {target_churn:.0%} | Customers who chased once churned {churn_1call:.0%} and twice {churn_2call:.0%}; the tracker and WhatsApp updates cut chasing, and the rules engine stops thin or mis-sold bundles. |")
p(f"| 5 | Status-chase calls per customer | {calls_base:.1f} | under {target_calls} | Live tracker with expected dates from typical_install_days, proactive WhatsApp updates, and automatic escalation to a named agent when a step runs late. |")
p("")
p("### Baselines by segment\n")
seg = []
for s in share:
    g, a = L[L.segment == s], A[A.segment == s]
    seg.append({"segment": s, "conversion": f"{g.act.mean():.1%}", "days to activate": round(a.days_lead_to_activation.mean(), 1),
                "CAC per activation": f"Rs {g.acquisition_cost_inr.sum() / g.act.sum():,.0f}", "6m churn": f"{a.churn.mean():.1%}",
                "chase calls": round(a.customer_follow_up_calls.mean(), 2)})
p(pd.DataFrame(seg).to_markdown(index=False))
p("\nTrack these weekly on the admin dashboard, split by segment and by channel (self-serve vs assisted), so the pilot can show the digital journey beating the baseline on the same segment.")

(root / "analysis" / "bundles_and_metrics.md").write_text("\n".join(out))
print("\n".join(out))
sys.exit(1 if failures else 0)
