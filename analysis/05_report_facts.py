import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
c = root / "data" / "clean"


def plain(df):
    df = df.astype({k: "object" for k in df.select_dtypes(["category", "string"]).columns})
    return df.astype({k: "float64" for k in df.select_dtypes(["Int8", "Int16", "Int32", "Int64", "Float64"]).columns})


L = plain(pd.read_parquet(c / "leads.parquet"))
A = plain(pd.read_parquet(c / "activated.parquet"))
items = plain(pd.read_parquet(c / "lead_bundle_items.parquet"))
interest = plain(pd.read_parquet(c / "lead_interest.parquet"))
cat = plain(pd.read_parquet(c / "catalogue.parquet"))
gst = plain(pd.read_parquet(c / "gstin.parquet"))
names = dict(zip(cat.product_id, cat.product_name))
L["act"] = (L.outcome == "Activated").astype(int)
L = L.merge(gst[["gstin", "status"]], on="gstin", how="left")
L["gst_status"] = L.status.fillna("No GSTIN")
sys.path.insert(0, str(root / "analysis"))
_argv = sys.argv; sys.argv = [sys.argv[0], str(root)]
import validate_bundles as vb
sys.argv = _argv
A = A.drop(columns=[x for x in ["mis_sold"] if x in A.columns]).merge(L[["lead_id", "gst_status"]].rename(columns={"gst_status": "gs"}), on="lead_id", how="left")
bought = items.groupby("lead_id").apply(lambda g: list(zip(g.product_id, g.qty.astype(int))), include_groups=False)
A["mis_sold"] = A.apply(lambda r: bool(vb.rule_errors({"city_tier": int(r.city_tier), "employees": r.employee_count, "sites": r.num_sites,
                                                       "gst_status": "Active" if r.gs == "Active" else r.gs}, bought[r.lead_id])), axis=1)
order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
out = []
p = out.append

p("# Supplementary facts for the Phase 1 report\n")

p("## Funnel with drop-off counts")
prev = None
rows = []
for i, s in enumerate(order):
    n = int((L.stage_rank >= i).sum())
    rows.append({"stage": s, "leads": n, "conv_from_prev": None if prev is None else round(n / prev * 100, 1),
                 "lost_at_this_step": None if prev is None else prev - n, "share_of_all_lost": None if prev is None else round((prev - n) / (5000 - 368) * 100, 1)})
    prev = n
F = pd.DataFrame(rows)
p(F.to_markdown(index=False))
p("")

p("## Mis-sold vs clean bundles (activated)")
p(A.groupby("mis_sold").agg(customers=("lead_id", "size"), churn=("churn", "mean"), nps=("nps_score", "mean"), calls=("customer_follow_up_calls", "mean")).round(3).to_markdown())
p("")
p("## Segment profiles")
seg_rows = []
for s, g in L.groupby("segment"):
    a = A[A.segment == s]
    d = g[g.act == 0]
    it = items[items.lead_id.isin(a.lead_id)]
    top_prod = it.groupby("product_id").lead_id.nunique().sort_values(ascending=False).head(3)
    top_int = interest[interest.lead_id.isin(g.lead_id)].product_id.value_counts().head(3)
    seg_rows.append({
        "segment": s, "leads": len(g), "share_%": round(len(g) / 50, 1), "conv_%": round(g.act.mean() * 100, 1),
        "top_source": f"{g.lead_source.value_counts().index[0]} ({g.lead_source.value_counts(normalize=True).iloc[0]:.0%})",
        "median_emp": g.employee_count.median(), "median_sites": g.num_sites.median(),
        "median_spend": g.monthly_telecom_spend_inr.median(),
        "gstin_%": round((g.has_gstin == "Y").mean() * 100, 1),
        "tier1_%": round((g.city_tier == 1).mean() * 100, 1),
        "top_interest": ", ".join(f"{k} {names[k]}" for k in top_int.index),
        "top_bought": ", ".join(f"{k} {names[k]} ({v/len(a):.0%})" for k, v in top_prod.items()),
        "median_bundle": a.monthly_bundle_value_inr.median(), "mean_bundle": round(a.monthly_bundle_value_inr.mean()),
        "churn_%": round(a.churn.mean() * 100, 1), "nps": round(a.nps_score.mean(), 2),
        "main_drop": f"{d.drop_reason.value_counts().index[0]} ({d.drop_reason.value_counts(normalize=True).iloc[0]:.0%})",
        "cac_per_activation": round(g.acquisition_cost_inr.sum() / g.act.sum()), "cost_per_lead": round(g.acquisition_cost_inr.mean()),
        "days": round(a.days_lead_to_activation.mean(), 1), "calls": round(a.customer_follow_up_calls.mean(), 2),
        "top_business_types": ", ".join(g.business_type.value_counts().head(4).index),
    })
S = pd.DataFrame(seg_rows)
for _, r in S.iterrows():
    p(f"### {r.segment}")
    for k, v in r.items():
        if k != "segment":
            p(f"- {k}: {v}")
    p("")

p("## Lead source quality")
src = []
for s, g in L.groupby("lead_source"):
    a = A[A.lead_source == s]
    src.append({"source": s, "leads": len(g), "share_%": round(len(g) / 50, 1), "conv_%": round(g.act.mean() * 100, 1),
                "cost_per_lead": round(g.acquisition_cost_inr.mean()), "total_cost": round(g.acquisition_cost_inr.sum()),
                "cost_per_activation": round(g.acquisition_cost_inr.sum() / g.act.sum()),
                "never_contacted_%": round((g.stage_rank == 0).mean() * 100, 1),
                "dropoff_%": round((1 - g.act.mean()) * 100, 1),
                "churn_%": round(a.churn.mean() * 100, 1), "nps": round(a.nps_score.mean(), 2),
                "median_bundle": a.monthly_bundle_value_inr.median(), "days": round(a.days_lead_to_activation.mean(), 1),
                "mis_sold_%": round(a.mis_sold.mean() * 100, 1) if "mis_sold" in a else None})
SRC = pd.DataFrame(src).sort_values("cost_per_activation")
p(SRC.to_markdown(index=False))
p(f"\nShare of total acquisition spend: " + ", ".join(f"{r.source} {r.total_cost / L.acquisition_cost_inr.sum():.0%}" for r in SRC.itertuples()))
p(f"Share of activations: " + ", ".join(f"{s} {n / L.act.sum():.0%}" for s, n in L[L.act == 1].lead_source.value_counts().items()))
p("")

p("## Customer experience")
p("### Languages")
lg = L.groupby("preferred_language").agg(leads=("act", "size"), conv=("act", "mean")).sort_values("leads", ascending=False)
lg["share_%"] = (lg.leads / 50).round(1)
lg["conv_%"] = (lg.conv * 100).round(1)
p(lg.drop(columns="conv").to_markdown())
p(f"\nHindi+English share: {(L.preferred_language.isin(['Hindi', 'English'])).mean():.1%}; regional share: {(~L.preferred_language.isin(['Hindi', 'English'])).mean():.1%}")
p("\n### Language by state (top language per state)")
p(L.groupby("state").preferred_language.agg(lambda s: f"{s.value_counts().index[0]} ({s.value_counts(normalize=True).iloc[0]:.0%})").to_markdown())
p("\n### Business types (top 15)")
bt = L.groupby(["business_type", "segment"]).agg(leads=("act", "size"), conv=("act", "mean")).reset_index().sort_values("leads", ascending=False).head(15)
bt["conv_%"] = (bt.conv * 100).round(1)
p(bt.drop(columns="conv").to_markdown(index=False))
p("\n### Employee count")
p(L.employee_count.describe().round(1).to_markdown())
p("\n### Current internet and provider")
ci = L.assign(ci=L.current_internet.fillna("Unknown")).groupby("ci").agg(leads=("act", "size"), conv=("act", "mean"), spend=("monthly_telecom_spend_inr", "median"))
ci["conv_%"] = (ci.conv * 100).round(1)
p(ci.drop(columns="conv").to_markdown())
p("")
p(L.current_provider.fillna("Unknown").value_counts().to_markdown())
pv = L.assign(pr=L.current_provider.fillna("Unknown")).groupby("pr").agg(leads=("act", "size"), conv=("act", "mean"))
pv["conv_%"] = (pv.conv * 100).round(1)
p("\nConversion by current provider:")
p(pv.drop(columns="conv").to_markdown())
acc = L.current_provider.isin(["Accel", "Accel (mobile only)"])
p(f"Existing Accel customers: {acc.sum()} leads ({acc.mean():.1%}), conversion {L[acc].act.mean():.1%} vs {L[~acc].act.mean():.1%} for everyone else")
p("\n### Telecom spend by segment (median, Rs/month)")
sp = L.groupby("segment").monthly_telecom_spend_inr.describe()[["25%", "50%", "75%"]]
p(sp.to_markdown())
both = A.copy()
both["ratio"] = both.monthly_bundle_value_inr / both.monthly_telecom_spend_inr
p(f"\nActivated customers: median bundle value / prior telecom spend = {both.ratio.median():.2f}")
p(both.groupby("segment").ratio.median().round(2).to_markdown())
p("\n### Products of interest (top 10)")
pi = interest.product_id.value_counts().head(10)
p(pd.DataFrame({"product": [f"{k} {names[k]}" for k in pi.index], "leads": pi.values, "share_of_leads_%": (pi.values / 50).round(1)}).to_markdown(index=False))
conv_by_int = interest.merge(L[["lead_id", "act"]], on="lead_id").groupby("product_id").act.agg(["size", "mean"]).query("size>=150").sort_values("mean", ascending=False)
p("\nConversion by product asked about (n>=150): " + ", ".join(f"{k} {names[k]} {v:.1%}" for k, v in conv_by_int["mean"].items()))
p("\n### Follow-up calls distribution (activated)")
p(A.customer_follow_up_calls.value_counts().sort_index().to_markdown())
p(f"\n% of activated customers who chased 3+ times: {(A.customer_follow_up_calls >= 3).mean():.0%}")
p("\n### Activation duration")
p(A.days_lead_to_activation.describe().round(1).to_markdown())
p(f"% activated within 14 days: {(A.days_lead_to_activation <= 14).mean():.0%}; over 21 days: {(A.days_lead_to_activation > 21).mean():.0%}")
p("\n### NPS distribution (activated)")
nps = A.nps_score
prom, det = (nps >= 9).mean(), (nps <= 6).mean()
p(f"Promoters (9-10): {prom:.0%}, passives (7-8): {((nps >= 7) & (nps <= 8)).mean():.0%}, detractors (0-6): {det:.0%}, NPS-style score = {(prom - det) * 100:.0f}; mean score {nps.mean():.2f}")
p(f"Churn among detractors: {A[nps <= 6].churn.mean():.0%}, among promoters: {A[nps >= 9].churn.mean():.0%}")
p("")

p("## Persona slices")
personas = {
    "Micro shop on mobile hotspot": (L.segment == "Micro retail & services") & (L.current_internet == "Mobile hotspot"),
    "Micro shop with broadband": (L.segment == "Micro retail & services") & (L.current_internet != "Mobile hotspot"),
    "Professional office": L.segment == "Professional offices",
    "Multi-site chain": L.segment == "Small multi-site businesses",
    "Small manufacturer": L.segment == "Small manufacturers",
}
for name, m in personas.items():
    g = L[m]
    a = A[A.lead_id.isin(g.lead_id)]
    d = g[g.act == 0]
    p(f"### {name}: {len(g)} leads ({len(g)/50:.1f}%)")
    p(f"- conv {g.act.mean():.1%}; median employees {g.employee_count.median():.0f}; median sites {g.num_sites.median():.0f}; median spend Rs {g.monthly_telecom_spend_inr.median():,.0f}; GSTIN {(g.has_gstin=='Y').mean():.0%}; tier 1 {(g.city_tier==1).mean():.0%}")
    p(f"- languages: " + ", ".join(f"{k} {v:.0%}" for k, v in g.preferred_language.value_counts(normalize=True).head(3).items()))
    p(f"- top business types: " + ", ".join(g.business_type.value_counts().head(4).index))
    p(f"- top sources: " + ", ".join(f"{k} {v:.0%}" for k, v in g.lead_source.value_counts(normalize=True).head(3).items()))
    p(f"- top interests: " + ", ".join(f"{names[k]} {v/len(g):.0%}" for k, v in interest[interest.lead_id.isin(g.lead_id)].product_id.value_counts().head(4).items()))
    p(f"- top drop reasons: " + ", ".join(f"{k} {v:.0%}" for k, v in d.drop_reason.value_counts(normalize=True).head(3).items()))
    p(f"- contact role: " + ", ".join(f"{k} {v:.0%}" for k, v in g.contact_role.value_counts(normalize=True).head(2).items()))
    if len(a):
        p(f"- activated {len(a)}: median bundle Rs {a.monthly_bundle_value_inr.median():,.0f}, churn {a.churn.mean():.0%}, NPS {a.nps_score.mean():.1f}, calls {a.customer_follow_up_calls.mean():.1f}, days {a.days_lead_to_activation.mean():.1f}")
    p("")

p("## KYC-stage baselines")
qa = (L.stage_rank >= 3).sum()
kc = (L.stage_rank >= 4).sum()
docmis = (L.drop_reason == "Document details did not match").sum()
paper = L.drop_reason.isin(["Missing GST or Udyam document", "Found paperwork too long", "Authorised signatory not available", "Document details did not match"]).sum()
p(f"- KYC completion rate (quote accepted -> KYC complete): {kc}/{qa} = {kc/qa:.1%}")
p(f"- Leads lost at the KYC step: {qa - kc}; of these, paperwork reasons: {paper} ({paper/(qa-kc):.0%})")
p(f"- 'Document details did not match' drops: {docmis} = {docmis/qa:.1%} of quote-accepted leads, {docmis/(qa-kc):.0%} of KYC-step losses")
p(f"- Drop reasons at the KYC step: " + ", ".join(f"{k} {v}" for k, v in L[L.stage_reached == 'Quote accepted'].drop_reason.value_counts().items()))
p(f"- Leads lost after KYC (KYC complete -> not activated): {kc - 368}; reasons: " + ", ".join(f"{k} {v}" for k, v in L[L.stage_reached == 'KYC complete'].drop_reason.value_counts().items()))
p(f"- No escalation-time field exists in the data; the 'chase calls' field (mean {A.customer_follow_up_calls.mean():.2f}) is the closest proxy for unresolved status.")
p("")

p("## Catalogue facts")
p(f"- Products: {len(cat)}; categories: " + ", ".join(f"{k} {v}" for k, v in cat.category.value_counts().items()))
p(f"- requires_gstin=Y: {(cat.requires_gstin=='Y').sum()} products: " + ", ".join(cat[cat.requires_gstin == 'Y'].product_id))
p(f"- has requires_one_of: {cat.requires_one_of.notna().sum()} products: " + ", ".join(cat[cat.requires_one_of.notna()].product_id))
p(f"- tier 1 only: " + ", ".join(cat[cat.available_city_tiers == '1'].product_id))
p(f"- min_employees > 1: " + ", ".join(f"{r.product_id} ({int(r.min_employees)})" for r in cat[cat.min_employees > 1].itertuples()))
p(f"- min_sites > 1: " + ", ".join(f"{r.product_id} ({int(r.min_sites)})" for r in cat[cat.min_sites > 1].itertuples()))
p(f"- setup fee > 0: {(cat.one_time_setup_inr > 0).sum()} products; contract range {int(cat.min_contract_months.min())}-{int(cat.min_contract_months.max())} months; install range {int(cat.typical_install_days.min())}-{int(cat.typical_install_days.max())} days")
mp = items.groupby("product_id").lead_id.nunique().sort_values(ascending=False).head(10)
p("- Most purchased (share of activated customers): " + ", ".join(f"{k} {names[k]} {v/368:.0%}" for k, v in mp.items()))
p(f"- Activated: median setup Rs {A.one_time_setup_inr.median():,.0f}, mean Rs {A.one_time_setup_inr.mean():,.0f}; contracts: " + ", ".join(f"{int(k)} mo {v}" for k, v in A.contract_months.value_counts().sort_index().items()))

(root / "analysis" / "05_report_facts.md").write_text("\n".join(out))
print("\n".join(out))
