import sys
from pathlib import Path
import pandas as pd

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
data = root / "data"
clean = data / "clean"
clean.mkdir(exist_ok=True)

lead_dtypes = {
    "lead_id": "string", "lead_source": "category", "business_name": "string", "business_type": "category",
    "segment": "category", "city": "category", "city_tier": "Int8", "state": "category", "preferred_language": "category",
    "employee_count": "Int32", "num_sites": "Int16", "annual_turnover_band": "category", "has_gstin": "category",
    "gstin": "string", "has_udyam": "category", "udyam_number": "string", "current_internet": "category",
    "current_provider": "category", "monthly_telecom_spend_inr": "Float64", "products_of_interest": "string",
    "contact_name": "string", "contact_role": "category", "stage_reached": "category", "outcome": "category",
    "drop_reason": "category", "days_lead_to_activation": "Float64", "customer_follow_up_calls": "Int16",
    "bundle_products": "string", "monthly_bundle_value_inr": "Float64", "one_time_setup_inr": "Float64",
    "contract_months": "Float64", "churned_within_6_months": "category", "nps_score": "Float64",
    "acquisition_cost_inr": "Float64",
}
cat_dtypes = {
    "product_id": "string", "category": "category", "product_name": "string", "description": "string", "unit": "category",
    "price_min_inr_per_month": "Int32", "price_max_inr_per_month": "Int32", "one_time_setup_inr": "Int32",
    "min_contract_months": "Int16", "available_city_tiers": "string", "min_employees": "Int16", "min_sites": "Int16",
    "requires_gstin": "category", "requires_one_of": "string", "typical_install_days": "Int16", "target_segments": "string",
}
gst_dtypes = {"gstin": "string", "legal_name": "string", "trade_name": "string", "constitution": "category",
              "principal_place_of_business": "string", "state": "category", "status": "category"}
udy_dtypes = {"udyam_number": "string", "enterprise_name": "string", "enterprise_type": "category", "major_activity": "category",
              "nic_description": "string", "state": "category", "city": "category"}

leads = pd.read_csv(data / "smb_leads.csv", dtype=lead_dtypes)
cat = pd.read_csv(data / "product_catalogue.csv", dtype=cat_dtypes)
gst = pd.read_csv(data / "mock_gstin_registry.csv", dtype=gst_dtypes)
udy = pd.read_csv(data / "mock_udyam_registry.csv", dtype=udy_dtypes)

for df in (leads, gst, udy):
    for col in [c for c in df.columns if c.endswith("_date") or c.startswith("date_of")]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

leads["interest_list"] = leads.products_of_interest.fillna("").str.split(";").apply(lambda x: [i.strip() for i in x if i.strip()])


def parse_bundle(s):
    if pd.isna(s) or not str(s).strip():
        return []
    pairs = []
    for part in str(s).split(";"):
        pid, _, q = part.strip().partition("x")
        pairs.append((pid, int(q)))
    return pairs


leads["bundle_pairs"] = leads.bundle_products.apply(parse_bundle)
cat["tiers_list"] = cat.available_city_tiers.str.split(";").apply(lambda x: [int(t) for t in x])
cat["requires_list"] = cat.requires_one_of.fillna("").str.split("|").apply(lambda x: [i for i in x if i])
cat["segments_list"] = cat.target_segments.str.split(";")

out = []
p = out.append
flags = []

p("# Data profile\n")
for name, df in [("smb_leads", leads), ("product_catalogue", cat), ("gstin_registry", gst), ("udyam_registry", udy)]:
    lists = [c for c in df.columns if c.endswith(("_list", "_pairs"))]
    base = df.drop(columns=lists)
    p(f"## {name}: {len(df):,} rows x {base.shape[1]} cols")
    nn = base.isna().sum()
    p("| column | dtype | nulls |\n|---|---|---|")
    for col in base.columns:
        p(f"| {col} | {base[col].dtype} | {nn[col]} |")
    dup = base.duplicated().sum()
    p(f"\nDuplicate rows: {dup}")
    if dup:
        flags.append(f"{name}: {dup} duplicate rows")
    p("")

for col, df, key in [("lead_id", leads, "smb_leads"), ("product_id", cat, "catalogue"), ("gstin", gst, "gstin registry"), ("udyam_number", udy, "udyam registry")]:
    d = df[col].duplicated().sum()
    if d:
        flags.append(f"{key}: {d} duplicate {col}")

order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
date_for = {"Contacted": "contacted_date", "Needs assessed": "needs_assessed_date", "Quote accepted": "quote_accepted_date",
            "KYC complete": "kyc_complete_date", "Activated": "activated_date"}
rank = {s: i for i, s in enumerate(order)}
leads["stage_rank"] = leads.stage_reached.astype(str).map(rank)

checks = {
    "has_gstin=Y but gstin blank": (leads.has_gstin == "Y") & leads.gstin.isna(),
    "has_gstin=N but gstin present": (leads.has_gstin == "N") & leads.gstin.notna(),
    "has_udyam=Y but udyam blank": (leads.has_udyam == "Y") & leads.udyam_number.isna(),
    "has_udyam=N but udyam present": (leads.has_udyam == "N") & leads.udyam_number.notna(),
    "gstin not 15 chars": leads.gstin.notna() & (leads.gstin.str.len() != 15),
    "udyam not UDYAM-XX-00-NNNNNNN": leads.udyam_number.notna() & ~leads.udyam_number.str.match(r"^UDYAM-[A-Z]{2}-00-\d{7}$", na=False),
    "city_tier not 1 or 2": ~leads.city_tier.isin([1, 2]),
    "employee_count < 1": leads.employee_count < 1,
    "num_sites < 1": leads.num_sites < 1,
    "negative telecom spend": leads.monthly_telecom_spend_inr < 0,
    "negative acquisition cost": leads.acquisition_cost_inr < 0,
    "nps outside 0-10": leads.nps_score.notna() & ~leads.nps_score.between(0, 10),
    "stage_reached not a known stage": leads.stage_rank.isna(),
    "Activated without activated_date": (leads.outcome == "Activated") & leads.activated_date.isna(),
    "Activated with a drop_reason": (leads.outcome == "Activated") & leads.drop_reason.notna(),
    "Dropped without drop_reason": (leads.outcome == "Dropped") & leads.drop_reason.isna(),
    "Dropped with activation fields filled": (leads.outcome == "Dropped") & leads.bundle_products.notna(),
    "Activated without bundle": (leads.outcome == "Activated") & (leads.bundle_pairs.str.len() == 0),
    "products_of_interest has unknown product": leads.interest_list.apply(lambda x: any(i not in set(cat.product_id) for i in x)),
    "bundle has unknown product": leads.bundle_pairs.apply(lambda x: any(pid not in set(cat.product_id) for pid, _ in x)),
    "bundle qty < 1": leads.bundle_pairs.apply(lambda x: any(q < 1 for _, q in x)),
    "days_lead_to_activation != activated - created": (leads.outcome == "Activated") & ((leads.activated_date - leads.created_date).dt.days != leads.days_lead_to_activation),
}
prev = "created_date"
for s in order[1:]:
    col = date_for[s]
    checks[f"{col} before {prev}"] = leads[col].notna() & leads[prev].notna() & (leads[col] < leads[prev])
    checks[f"reached {s} but {col} blank"] = (leads.stage_rank >= rank[s]) & leads[col].isna()
    checks[f"{col} filled but stage not reached"] = (leads.stage_rank < rank[s]) & leads[col].notna()
    prev = col
checks["catalogue: price_min > price_max"] = pd.Series(False, index=leads.index)
bad_price = (cat.price_min_inr_per_month > cat.price_max_inr_per_month).sum()
bad_dep = cat.requires_list.apply(lambda x: any(i not in set(cat.product_id) for i in x)).sum()

p("## Consistency checks")
p("| check | rows |\n|---|---|")
for k, mask in checks.items():
    if k.startswith("catalogue"):
        continue
    n = int(mask.fillna(False).sum())
    p(f"| {k} | {n} |")
    if n:
        flags.append(f"{k}: {n}")
p(f"| catalogue: price_min > price_max | {bad_price} |")
p(f"| catalogue: requires_one_of points to unknown product | {bad_dep} |")
p("")
p(f"- created_date range: {leads.created_date.min().date()} to {leads.created_date.max().date()}")
p(f"- employee_count {leads.employee_count.min()}-{leads.employee_count.max()}, num_sites {leads.num_sites.min()}-{leads.num_sites.max()}, "
  f"spend Rs {leads.monthly_telecom_spend_inr.min():,.0f}-{leads.monthly_telecom_spend_inr.max():,.0f}")
p(f"- outcome: {leads.outcome.value_counts().to_dict()}")
p(f"- leads with current_internet blank: {leads.current_internet.isna().sum()} (treat as Unknown)")
p("")

p("## Funnel (leads that reached at least this stage)")
p("| stage | leads | expected | % of previous | match |\n|---|---|---|---|---|")
expected = [5000, 3406, 1974, 861, 588, 368]
prev_n, all_ok = None, True
for s, e in zip(order, expected):
    n = int((leads.stage_rank >= rank[s]).sum())
    ok = n == e
    all_ok &= ok
    p(f"| {s} | {n:,} | {e:,} | {'-' if prev_n is None else f'{n/prev_n:.0%}'} | {'OK' if ok else 'MISMATCH'} |")
    prev_n = n
p(f"\n**Funnel matches README: {'YES' if all_ok else 'NO'}**\n")

g = leads.merge(gst, on="gstin", how="left", suffixes=("", "_reg"), indicator="gst_join")
wg = g[g.gstin.notna()]
found = wg[wg.gst_join == "both"]
norm = lambda s: s.fillna("").str.lower().str.replace(r"[^a-z0-9 ]", "", regex=True).str.split().str.join(" ")
legal_diff = norm(found.business_name) != norm(found.legal_name)
trade_diff = norm(found.business_name) != norm(found.trade_name)
prop = found.legal_name.str.contains(r"\(Prop\.", na=False)
p("## Leads -> GSTIN registry")
p(f"- Leads with a GSTIN: {len(wg):,}; found in registry: {len(found):,}; not found: {len(wg) - len(found):,}")
st = found.status.value_counts()
p(f"- Registry status: Active {st.get('Active', 0):,}, Cancelled {st.get('Cancelled', 0):,}, Suspended {st.get('Suspended', 0):,}")
p(f"- business_name differs from legal_name: {legal_diff.sum():,} (of which {(legal_diff & prop).sum():,} are proprietorships stored as 'Owner (Prop. Trade name)')")
p(f"- business_name differs from trade_name: {trade_diff.sum():,}")
if trade_diff.sum():
    p("  examples: " + "; ".join(f"{a} vs {b}" for a, b in found.loc[trade_diff, ["business_name", "trade_name"]].head(5).values))
p(f"- Lead state differs from registry state: {(found.state.astype(str) != found.state_reg.astype(str)).sum()}")
p(f"- GSTIN state code vs registry state: first 2 digits checked against state below")
sc = found.assign(code=found.gstin.str[:2]).groupby("code").state_reg.nunique()
p(f"  state codes mapping to more than one state: {(sc > 1).sum()}")
p(f"- Activated leads with Cancelled/Suspended GSTIN: {((found.outcome == 'Activated') & found.status.isin(['Cancelled', 'Suspended'])).sum()}")
p(f"- Constitution: {found.constitution.value_counts().to_dict()}")
p("")

u = leads.merge(udy, on="udyam_number", how="left", suffixes=("", "_reg"), indicator="u_join")
wu = u[u.udyam_number.notna()]
fu = wu[wu.u_join == "both"]
p("## Leads -> Udyam registry")
p(f"- Leads with a Udyam number: {len(wu):,}; found in registry: {len(fu):,}; not found: {len(wu) - len(fu):,}")
p(f"- business_name differs from enterprise_name: {(norm(fu.business_name) != norm(fu.enterprise_name)).sum():,}")
p(f"- city differs: {(fu.city.astype(str) != fu.city_reg.astype(str)).sum()}, state differs: {(fu.state.astype(str) != fu.state_reg.astype(str)).sum()}")
p(f"- enterprise_type: {fu.enterprise_type.value_counts().to_dict()}")
p(f"- Leads with Udyam but no GSTIN: {((leads.has_udyam == 'Y') & (leads.has_gstin == 'N')).sum()}")
p("")

p("## Registry coverage")
p(f"- GSTIN registry rows not linked to any lead: {(~gst.gstin.isin(leads.gstin)).sum()}")
p(f"- Udyam registry rows not linked to any lead: {(~udy.udyam_number.isin(leads.udyam_number)).sum()}")
p("")

p("## Flags")
p("\n".join(f"- {f}" for f in flags) if flags else "- Nothing odd found. All consistency checks returned 0.")

leads["interest_list"] = leads.interest_list.apply(lambda x: ";".join(x))
interest = leads[["lead_id", "products_of_interest"]].assign(product_id=leads.products_of_interest.fillna("").str.split(";")).explode("product_id")
interest = interest[interest.product_id.fillna("") != ""][["lead_id", "product_id"]]
bundle = leads[["lead_id", "bundle_pairs"]].explode("bundle_pairs").dropna()
bundle = pd.DataFrame({"lead_id": bundle.lead_id.values, "product_id": [x[0] for x in bundle.bundle_pairs], "qty": [x[1] for x in bundle.bundle_pairs]})

leads.drop(columns=["bundle_pairs", "interest_list"]).to_parquet(clean / "leads.parquet")
interest.to_parquet(clean / "lead_interest.parquet")
bundle.to_parquet(clean / "lead_bundle_items.parquet")
cat.drop(columns=["tiers_list", "requires_list", "segments_list"]).to_parquet(clean / "catalogue.parquet")
gst.to_parquet(clean / "gstin.parquet")
udy.to_parquet(clean / "udyam.parquet")
p("")
p("## Saved")
p(f"- data/clean/leads.parquet ({len(leads):,}), lead_interest.parquet ({len(interest):,} lead-product rows), "
  f"lead_bundle_items.parquet ({len(bundle):,} lead-product-qty rows), catalogue.parquet, gstin.parquet, udyam.parquet")

(root / "analysis" / "01_profile.md").write_text("\n".join(out))
print("\n".join(out))
