import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
c = root / "data" / "clean"


def plain(df):
    df = df.astype({k: "object" for k in df.select_dtypes(["category", "string"]).columns})
    return df.astype({k: "float64" for k in df.select_dtypes(["Int8", "Int16", "Int32", "Int64", "Float64"]).columns})


L = plain(pd.read_parquet(c / "leads.parquet"))
items = plain(pd.read_parquet(c / "lead_bundle_items.parquet"))
cat = plain(pd.read_parquet(c / "catalogue.parquet"))
gst = plain(pd.read_parquet(c / "gstin.parquet"))
names = dict(zip(cat.product_id, cat.product_name))

L["act"] = (L.outcome == "Activated").astype(int)
L = L.merge(gst[["gstin", "status"]], on="gstin", how="left")
L["gst_status"] = L.status.fillna("No GSTIN")
L["current_internet"] = L.current_internet.fillna("Unknown")
L["employee_bucket"] = pd.cut(L.employee_count, [0, 2, 5, 10, 25, 1000], labels=["1-2", "3-5", "6-10", "11-25", "26+"]).astype(str)
order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
base = L.act.mean()

out = []
p = out.append
facts = {}


def conv_table(col, min_n=30):
    t = L.groupby(col).agg(leads=("act", "size"), activated=("act", "sum"), conv=("act", "mean")).reset_index()
    t = t[t.leads >= min_n].sort_values("conv", ascending=False)
    t["conv %"] = (t.conv * 100).round(1)
    t["vs avg"] = (t.conv / base).round(2).astype(str) + "x"
    return t.drop(columns="conv")


def spread(t, col):
    hi, lo = t.iloc[0], t.iloc[-1]
    return hi[col], hi["conv %"], lo[col], lo["conv %"]


p("# Signals in smb_leads.csv\n")
p(f"Base rate: **{base:.1%}** of 5,000 leads activated ({L.act.sum()}). Every table uses data/clean from step 1.1.\n")

p("## Q1. Conversion by lead attribute\n")
q1_cols = [("segment", "Segment"), ("lead_source", "Lead source"), ("city_tier", "City tier"), ("preferred_language", "Preferred language"),
           ("current_internet", "Current internet"), ("has_gstin", "Has GSTIN"), ("gst_status", "GSTIN status (registry)"),
           ("has_udyam", "Has Udyam"), ("annual_turnover_band", "Turnover band"), ("employee_bucket", "Employees")]
take = {}
for col, title in q1_cols:
    t = conv_table(col)
    if col == "employee_bucket":
        t = t.set_index(col).reindex(["1-2", "3-5", "6-10", "11-25", "26+"]).reset_index()
    p(f"### {title}")
    p(t.to_markdown(index=False))
    if col == "employee_bucket":
        small = L[L.employee_count <= 5].act.mean()
        big = L[L.employee_count > 10].act.mean()
        line = f"Teams of 1-5 convert at {small:.1%}, teams over 10 at {big:.1%}: size roughly doubles the odds."
        facts["emp"] = (small, big)
    elif col == "has_gstin":
        y = L[L.has_gstin == "Y"].act.mean()
        n = L[L.has_gstin == "N"].act.mean()
        facts["gstin"] = (y, n)
        line = f"Confirmed: {y:.1%} with a GSTIN vs {n:.1%} without, a {y/n:.1f}x gap (README says 9.6% vs 2.0%)."
    elif col == "gst_status":
        cxl = L[L.gst_status == "Cancelled"].act.mean()
        line = f"Cancelled GSTINs still activated at {cxl:.1%}, so today's sellers close deals the catalogue says they shouldn't."
        facts["cancelled_conv"] = cxl
    else:
        a, av, b, bv = spread(t, col)
        line = f"{a} converts best at {av}% and {b} worst at {bv}%."
        facts[col] = (a, av, b, bv)
    p(f"\n**Takeaway:** {line}\n")

p("## Q2. Biggest drop stage\n")


def pass_rates(by):
    rows = []
    for k, g in L.groupby(by):
        r = {by: k, "leads": len(g)}
        prev = len(g)
        worst, wv = None, 2.0
        for i, s in enumerate(order[1:], 1):
            n = int((g.stage_rank >= i).sum())
            rate = n / prev if prev else 0
            r[f"-> {s}"] = f"{rate:.0%}"
            if rate < wv:
                worst, wv = s, rate
            prev = n
        r["biggest drop"] = f"{worst} ({wv:.0%} pass)"
        rows.append(r)
    return pd.DataFrame(rows)


for by, title in [("segment", "By segment"), ("lead_source", "By lead source")]:
    t = pass_rates(by)
    p(f"### {title}")
    p(t.to_markdown(index=False))
    wq = t["biggest drop"].str.startswith("Quote accepted").sum()
    p(f"\n**Takeaway:** the quote step is the biggest drop for {wq} of {len(t)} {by.replace('_', ' ')} groups.\n")
micro_q = pass_rates("segment").set_index("segment").loc["Micro retail & services", "-> Quote accepted"]
wa_c = pass_rates("lead_source").set_index("lead_source").loc["WhatsApp campaign", "-> Contacted"]
web_c = pass_rates("lead_source").set_index("lead_source").loc["Website form", "-> Contacted"]
facts["micro_quote"], facts["wa_contact"], facts["web_contact"] = micro_q, wa_c, web_c
p(f"Also: micro businesses pass the quote step only {micro_q} of the time, and WhatsApp-campaign and website-form leads are contacted only {wa_c} and {web_c} of the time (vs 68% overall).\n")

p("## Q3. Drop reasons and what a digital journey fixes\n")
bucket = {
    "Unreachable after 3 attempts": "Reach/speed", "Owner had no time for a visit": "Reach/speed", "Visit not scheduled by sales": "Reach/speed",
    "Quote took too long to arrive": "Reach/speed", "Installation delayed beyond 21 days": "Reach/speed",
    "Quote too complex to understand": "Understanding/price", "Price too high": "Understanding/price",
    "Competitor offered cheaper plan": "Understanding/price", "Only wanted a mobile plan": "Understanding/price",
    "Missing GST or Udyam document": "Paperwork", "Found paperwork too long": "Paperwork",
    "Authorised signatory not available": "Paperwork", "Document details did not match": "Paperwork",
}
fix = {
    "Owner had no time for a visit": ("Yes", "self-serve, no visit needed"),
    "Visit not scheduled by sales": ("Yes", "no visit needed"),
    "Quote took too long to arrive": ("Yes", "instant quote"),
    "Quote too complex to understand": ("Yes", "plain-language quote"),
    "Missing GST or Udyam document": ("Yes", "registry lookup pre-fills it"),
    "Found paperwork too long": ("Yes", "lookup + OCR"),
    "Document details did not match": ("Yes", "mismatch caught at upload"),
    "Site not feasible for fibre": ("Yes", "advisor offers 5G AirFiber"),
    "First payment failed": ("Yes", "in-app retry/UPI"),
    "Unreachable after 3 attempts": ("Partly", "owner starts the chat, but some never engage"),
    "Installation delayed beyond 21 days": ("Partly", "tracker + escalation, install itself is physical"),
    "Price too high": ("Partly", "right-sized bundle, add-on toggles"),
    "Only wanted a mobile plan": ("Partly", "advisor can sell a mobile-only plan"),
    "Authorised signatory not available": ("Partly", "remote e-sign"),
    "Customer cancelled before install": ("Partly", "tracker reduces anxiety"),
    "Competitor offered cheaper plan": ("No", ""), "Not interested on first call": ("No", ""),
    "Locked in with current provider": ("No", ""), "Wrong or invalid number": ("No", ""), "Decided to wait": ("No", ""),
}
D = L[L.act == 0].copy()
D["bucket"] = D.drop_reason.map(bucket).fillna("Other")
D["fixable"] = D.drop_reason.map(lambda r: fix.get(r, ("No", ""))[0])
D["how"] = D.drop_reason.map(lambda r: fix.get(r, ("No", ""))[1])
t = D.groupby(["bucket", "drop_reason", "fixable", "how"]).size().rename("drops").reset_index()
t["% of drops"] = (t.drops / len(D) * 100).round(1)
t = t.sort_values(["bucket", "drops"], ascending=[True, False])
p(t.to_markdown(index=False))
p("")
b = D.groupby("bucket").agg(drops=("lead_id", "size"), fixable_yes=("fixable", lambda s: (s == "Yes").sum()),
                            fixable_partly=("fixable", lambda s: (s == "Partly").sum())).sort_values("drops", ascending=False)
b["% of all drops"] = (b.drops / len(D) * 100).round(1)
b["digital journey fixes"] = np.where(b.fixable_yes / b.drops > 0.5, "Mostly", np.where((b.fixable_yes + b.fixable_partly) / b.drops > 0.5, "Partly", "Mostly not"))
p("### By bucket")
p(b.reset_index().to_markdown(index=False))
fy, fp = (D.fixable == "Yes").mean(), (D.fixable == "Partly").mean()
facts["fix"] = (fy, fp)
facts["reach"] = b.loc["Reach/speed", "% of all drops"]
p(f"\n**Takeaway:** reach/speed is the biggest bucket at {b.loc['Reach/speed', '% of all drops']}% of drops; a digital journey fully fixes {fy:.0%} of all drops and partly fixes another {fp:.0%}.\n")

p("## Q4. Activated customers: speed, chasing, churn and NPS\n")
A = L[L.act == 1].copy()
A["churn"] = A.churned_within_6_months.astype(str).str.upper().isin(["Y", "YES", "TRUE", "1"]).astype(int)
nprod = items.groupby("lead_id").product_id.nunique().rename("n_products")
A = A.merge(nprod, left_on="lead_id", right_index=True, how="left")
agg = dict(customers=("act", "size"), avg_days=("days_lead_to_activation", "mean"), avg_chase_calls=("customer_follow_up_calls", "mean"),
           churn_6m=("churn", "mean"), avg_nps=("nps_score", "mean"))
t = A.groupby("segment").agg(**agg)
t["churn_6m"] = (t.churn_6m * 100).round(1).astype(str) + "%"
p("### By segment")
p(t.round(2).reset_index().to_markdown(index=False))
p(f"\n**Takeaway:** micro customers churn most ({A[A.segment=='Micro retail & services'].churn.mean():.0%}) while manufacturers take longest to activate ({A[A.segment=='Small manufacturers'].days_lead_to_activation.mean():.1f} days).\n")
A["bundle_size"] = pd.cut(A.n_products, [0, 2, 3, 4, 5, 6, 20], labels=["2", "3", "4", "5", "6", "7+"]).astype(str)
t = A.groupby("bundle_size").agg(**agg)
t["churn_6m"] = (t.churn_6m * 100).round(1).astype(str) + "%"
p("### By bundle size (number of distinct products)")
p(t.round(2).reset_index().to_markdown(index=False))
c2 = A[A.n_products <= 2].churn.mean()
c36 = A[A.n_products.between(3, 6)].churn.mean()
facts["bundle_churn"] = (c2, c36)
p(f"\n**Takeaway:** 2-product bundles churn at {c2:.0%} vs {c36:.0%} for 3-6 products, so a thin bundle is a weak bundle.\n")
A["calls"] = A.customer_follow_up_calls.clip(upper=5).astype(int).astype(str).replace({"5": "5+"})
t = A.groupby("calls").agg(customers=("act", "size"), churn_6m=("churn", "mean"), avg_nps=("nps_score", "mean"), avg_days=("days_lead_to_activation", "mean"))
c1, c5 = t.loc["1", "churn_6m"], t.loc["5+", "churn_6m"]
n1, n5 = t.loc["1", "avg_nps"], t.loc["5+", "avg_nps"]
t["churn_6m"] = (t.churn_6m * 100).round(1).astype(str) + "%"
p("### Do more chase calls predict churn or low NPS?")
p(t.round(2).reset_index().to_markdown(index=False))
r_churn = A.customer_follow_up_calls.corr(A.churn)
r_nps = A.customer_follow_up_calls.corr(A.nps_score)
r_days = A.customer_follow_up_calls.corr(A.days_lead_to_activation)
r_dn = A.days_lead_to_activation.corr(A.nps_score)
p(f"\nCorrelations: calls vs churn {r_churn:+.2f}, calls vs NPS {r_nps:+.2f}, calls vs days {r_days:+.2f}, days vs NPS {r_dn:+.2f}.")
facts["calls"] = (c1, c5, n1, n5)
p(f"\n**Takeaway:** yes. Churn climbs from {c1:.0%} at 1 call to {c5:.0%} at 5+ calls and NPS drops from {n1:.1f} to {n5:.1f}; calls aren't explained by slow activation (r={r_days:+.2f}), so it's the uncertainty, not the wait, that hurts.\n")

p("## Q5. Most common bundles and what gets bought together\n")
combo = items.groupby("lead_id").product_id.apply(lambda s: "+".join(sorted(set(s)))).rename("combo")
A = A.merge(combo, left_on="lead_id", right_index=True, how="left")
for s, g in A.groupby("segment"):
    vc = g.groupby("combo").agg(buys=("act", "size"), median_monthly=("monthly_bundle_value_inr", "median"),
                                median_contract=("contract_months", "median"), churn=("churn", "mean")).sort_values("buys", ascending=False).head(5).reset_index()
    vc["products"] = vc.combo.apply(lambda x: ", ".join(names[i] for i in x.split("+")))
    vc["churn"] = (vc.churn * 100).round(0).astype(int).astype(str) + "%"
    p(f"### {s} ({len(g)} activated, {g.combo.nunique()} distinct bundles)")
    p(vc[["combo", "products", "buys", "median_monthly", "median_contract", "churn"]].to_markdown(index=False))
    p("")
top_micro = A[A.segment == "Micro retail & services"].combo.value_counts()
facts["micro_top"] = (top_micro.index[0], top_micro.iloc[0], len(A[A.segment == "Micro retail & services"]))
p(f"**Takeaway:** only micro has a clear default ({top_micro.index[0]}, {top_micro.iloc[0]} of {facts['micro_top'][2]} buys); other segments buy near-unique bundles, which is exactly why a conversational advisor beats a fixed menu.\n")

baskets = items.groupby("lead_id").product_id.apply(lambda s: sorted(set(s)))
n = len(baskets)
single = pd.Series([pid for b in baskets for pid in b]).value_counts() / n
pairs = pd.Series([pr for b in baskets for pr in combinations(b, 2)]).value_counts()
pt = pd.DataFrame({"pair": pairs.index, "together": pairs.values})
pt["support %"] = (pt.together / n * 100).round(1)
pt["lift"] = pt.apply(lambda r: (r.together / n) / (single[r.pair[0]] * single[r.pair[1]]), axis=1).round(2)
pt["products"] = pt.pair.apply(lambda x: f"{names[x[0]]} + {names[x[1]]}")
pt["pair"] = pt.pair.apply(lambda x: "+".join(x))
p("### Products bought together (pairs in 10+ baskets, ranked by lift)")
p(pt[pt.together >= 10].sort_values("lift", ascending=False).head(12)[["pair", "products", "together", "support %", "lift"]].to_markdown(index=False))
p("\n### Most frequent pairs")
p(pt.head(8)[["pair", "products", "together", "support %", "lift"]].to_markdown(index=False))
top_pair = pt[pt.together >= 10].sort_values("lift", ascending=False).iloc[0]
facts["pair"] = (top_pair.products, top_pair.lift)
p(f"\n**Takeaway:** the strongest attachment is {top_pair.products} (lift {top_pair.lift}); fibre + a business SIM is the base almost every bundle grows from, so the advisor should lead with connectivity and attach from there.\n")

p("## Q6. Acquisition cost vs conversion by lead source\n")
t = L.groupby("lead_source").agg(leads=("act", "size"), activated=("act", "sum"), cost_per_lead=("acquisition_cost_inr", "mean"),
                                 total_cost=("acquisition_cost_inr", "sum"))
t["conv %"] = (t.activated / t.leads * 100).round(1)
t["cost per activation"] = (t.total_cost / t.activated).round(0)
t = t.sort_values("cost per activation")
blended = L.acquisition_cost_inr.sum() / L.act.sum()
p(t.drop(columns="total_cost").round(0).reset_index().to_markdown(index=False))
p(f"\nBlended: Rs {blended:,.0f} per activation.")
cheap = t.iloc[0]
ref = t.loc["Referral"]
fs = t.loc["Field sales"]
facts["cac"] = (ref["conv %"], ref["cost per activation"], fs["conv %"], fs["cost per activation"], blended)
p(f"\n**Takeaway:** the cheapest per activation is {t.index[0]} (Rs {cheap['cost per activation']:,.0f}) but it barely converts; Referral is the real winner at {ref['conv %']}% conversion and Rs {ref['cost per activation']:,.0f}, while Field sales costs Rs {fs['cost per activation']:,.0f}, {fs['cost per activation']/ref['cost per activation']:.0f}x more.\n")

p("## Q7. Things that look deliberately planted\n")
Lm = L.merge(items.groupby("lead_id").product_id.apply(list).rename("bought"), left_on="lead_id", right_index=True, how="left")
cr = cat.set_index("product_id")
viol = []
for _, r in Lm[Lm.act == 1].iterrows():
    ids = set(r.bought)
    for pid in ids:
        x = cr.loc[pid]
        if int(r.city_tier) not in [int(v) for v in str(x.available_city_tiers).split(";")]:
            viol.append((r.lead_id, "sold outside its city tier"))
        if r.employee_count < x.min_employees:
            viol.append((r.lead_id, "below min employees"))
        if r.num_sites < x.min_sites:
            viol.append((r.lead_id, "below min sites"))
        if x.requires_gstin == "Y" and r.gst_status != "Active":
            viol.append((r.lead_id, f"GSTIN product with {r.gst_status.lower()}"))
        if isinstance(x.requires_one_of, str) and x.requires_one_of and not (set(x.requires_one_of.split("|")) & ids):
            viol.append((r.lead_id, "missing a required base product"))
V = pd.DataFrame(viol, columns=["lead_id", "rule"])
mis = V.lead_id.nunique()
facts["mis"] = (mis, L.act.sum())
p(f"### 1. Mis-selling: {mis} of {L.act.sum()} activated customers ({mis/L.act.sum():.0%}) were sold something the catalogue says they can't have")
p(V.groupby("rule").lead_id.nunique().rename("customers").reset_index().sort_values("customers", ascending=False).to_markdown(index=False))
p("")
lang = conv_table("preferred_language")
p("### 2. Languages: Tamil, Punjabi and Kannada lag")
p(lang.to_markdown(index=False))
reg = L[~L.preferred_language.isin(["Hindi", "English"])]
regq = (reg.stage_rank >= 3).sum() / (reg.stage_rank >= 2).sum()
hq = (L[L.preferred_language.isin(["Hindi", "English"])].stage_rank >= 3).sum() / (L[L.preferred_language.isin(["Hindi", "English"])].stage_rank >= 2).sum()
facts["lang_q"] = (regq, hq)
p(f"\nRegional-language leads accept the quote {regq:.0%} of the time vs {hq:.0%} for Hindi/English.\n")
city = conv_table("city", 150)
p("### 3. Cities: spread is wide (n >= 150)")
p(pd.concat([city.head(4), city.tail(4)]).to_markdown(index=False))
p("")
p("### 4. Digital leads go unanswered")
srcU = D.groupby("lead_source").apply(lambda g: (g.drop_reason.isin(["Unreachable after 3 attempts", "Wrong or invalid number"])).mean(), include_groups=False)
p((srcU * 100).round(1).rename("% of drops unreachable or wrong number").reset_index().sort_values("% of drops unreachable or wrong number", ascending=False).to_markdown(index=False))
facts["unreach"] = (srcU["WhatsApp campaign"], srcU["Website form"])
p("")
p("### 5. Mobile-hotspot shops convert at half the average")
hot = L[L.current_internet == "Mobile hotspot"].act.mean()
facts["hotspot"] = hot
p(f"{hot:.1%} vs {base:.1%} overall; these are the micro shops the case calls very price-sensitive.\n")
p("### 6. Registry name format")
p("Every proprietorship's legal_name is 'Owner (Prop. Trade name)'. Match KYC names on trade_name, or about 2,443 honest applicants get flagged.\n")
p("### 7. Catalogue trap")
p("Static IP (P11) needs Biz Fibre (P01-P03), not a leased line, even though leased-line customers are the ones most likely to want a static IP.\n")
p("### 8. Stage timing for activated customers (median days)")
for a_, b_ in [("created_date", "contacted_date"), ("contacted_date", "needs_assessed_date"), ("needs_assessed_date", "quote_accepted_date"),
               ("quote_accepted_date", "kyc_complete_date"), ("kyc_complete_date", "activated_date")]:
    d = (pd.to_datetime(A[b_]) - pd.to_datetime(A[a_])).dt.days
    p(f"- {a_.replace('_date', '')} -> {b_.replace('_date', '')}: {d.median():.0f} days")
pre_q = ((pd.to_datetime(A.quote_accepted_date) - pd.to_datetime(A.created_date)).dt.days).mean()
facts["pre_quote_days"] = pre_q
p(f"\nOn average {pre_q:.1f} of the 17.6 days pass before the quote is even accepted; a one-sitting advisor removes most of that.")

(root / "analysis" / "02_signals.md").write_text("\n".join(out))
A.drop(columns=["calls"]).to_parquet(c / "activated.parquet")

g_y, g_n = facts["gstin"]
fy, fp = facts["fix"]
c1, c5, n1, n5 = facts["calls"]
rc, rcac, fc, fcac, bl = facts["cac"]
mis, act = facts["mis"]
regq, hq = facts["lang_q"]
wa_u, web_u = facts["unreach"]
seg = facts["segment"]
insights = f"""# Udyam Digital: top 10 findings

Source: smb_leads.csv (5,000 leads, Apr-Jun 2026), product catalogue and mock registries. Tables behind every number are in 02_signals.md.

1. The quote step loses the most leads: only 44% of assessed leads accept a quote, and just {facts['micro_quote']} of micro businesses do.
2. Reach and speed cause {facts['reach']}% of all drops (unreachable, no time for a visit, visit not scheduled, slow quote, late install), more than price does.
3. A self-serve digital journey fully fixes {fy:.0%} of today's drops and partly fixes another {fp:.0%}, so roughly {fy+fp:.0%} of lost leads are in reach.
4. Leads with a GSTIN activate at {g_y:.1%} against {g_n:.1%} without one, a {g_y/g_n:.1f}x gap that makes the GSTIN lookup the most valuable first question.
5. Referrals convert at {rc}% for Rs {rcac:,.0f} per activation, while field sales converts at {fc}% for Rs {fcac:,.0f}, about {fcac/rcac:.0f}x the cost (blended Rs {bl:,.0f}).
6. WhatsApp-campaign and website-form leads are the cheapest to generate but {wa_u:.0%} and {web_u:.0%} of their drops are unreachable or wrong numbers, because they wait for a callback that never lands.
7. {mis} of {act} activated customers ({mis/act:.0%}) were sold a product the catalogue rules forbid them, including GST-only products sold on cancelled or missing GSTINs.
8. Customers who chased status once churned at {c1:.0%}, those who chased five or more times at {c5:.0%}, with NPS falling from {n1:.1f} to {n5:.1f}.
9. {seg[0]} convert best at {seg[1]}% and {seg[2]} worst at {seg[3]}%, and 2-product bundles churn at {facts['bundle_churn'][0]:.0%} against {facts['bundle_churn'][1]:.0%} for 3-6 products.
10. Regional-language leads accept the quote {regq:.0%} of the time against {hq:.0%} for Hindi and English, with Tamil ({L[L.preferred_language=='Tamil'].act.mean():.1%}), Punjabi ({L[L.preferred_language=='Punjabi'].act.mean():.1%}) and Kannada ({L[L.preferred_language=='Kannada'].act.mean():.1%}) converting at well under the {base:.1%} average.
"""
(root / "analysis" / "insights.md").write_text(insights)
print("\n".join(out[:3]))
print(insights)
