import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
c = root / "data" / "clean"
figs = root / "docs" / "figures"
figs.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, INK, INK2, MUTED, GRID, SURF = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SURF, "axes.facecolor": SURF,
                     "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left"})


def plain(df):
    df = df.astype({k: "object" for k in df.select_dtypes(["category", "string"]).columns})
    return df.astype({k: "float64" for k in df.select_dtypes(["Int8", "Int16", "Int32", "Int64", "Float64"]).columns})


L = plain(pd.read_parquet(c / "leads.parquet"))
A = plain(pd.read_parquet(c / "activated.parquet"))
L["act"] = (L.outcome == "Activated").astype(int)


def hbar(ax, labels, values, fmt, highlight=None, xlabel=None):
    y = np.arange(len(labels))[::-1]
    cols = [ORANGE if (highlight is not None and i in highlight) else BLUE for i in range(len(labels))]
    ax.barh(y, values, color=cols, height=0.62, edgecolor=SURF, linewidth=2)
    ax.set_yticks(y, labels)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    m = max(values)
    for yi, v in zip(y, values):
        ax.text(v + m * 0.015, yi, fmt(v), va="center", color=INK, fontsize=9)
    ax.set_xlim(0, m * 1.18)
    if xlabel:
        ax.set_xlabel(xlabel)


order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
counts = [int((L.stage_rank >= i).sum()) for i in range(6)]
fig, ax = plt.subplots(figsize=(8, 3.8))
lab = [f"{s}" for s in order]
hbar(ax, lab, counts, lambda v: f"{int(v):,}", highlight={3})
for i, (n, prev) in enumerate(zip(counts[1:], counts[:-1]), 1):
    ax.text(counts[0] * 1.17, 5 - i, f"{n/prev:.0%} pass", va="center", ha="right", color=INK2, fontsize=9)
ax.set_title("Funnel: 5,000 leads to 368 customers (Apr-Jun 2026)")
ax.set_xlabel("Leads reaching the stage (orange = weakest step: quote accepted, 44% pass)")
fig.tight_layout(); fig.savefig(figs / "fig1_funnel.png", dpi=180); plt.close(fig)

seg_order = ["Micro retail & services", "Professional offices", "Small multi-site businesses", "Small manufacturers"]
short = ["Micro retail", "Professional offices", "Multi-site", "Manufacturers"]
conv = [L[L.segment == s].act.mean() * 100 for s in seg_order]
val = [A[A.segment == s].monthly_bundle_value_inr.median() for s in seg_order]
cac = [L[L.segment == s].acquisition_cost_inr.sum() / L[L.segment == s].act.sum() for s in seg_order]
churn = [A[A.segment == s].churn.mean() * 100 for s in seg_order]
fig, axs = plt.subplots(2, 2, figsize=(9, 5.6))
for ax, vals, title, fmt in [(axs[0, 0], conv, "Lead-to-activation %", lambda v: f"{v:.1f}%"), (axs[0, 1], val, "Median bundle (Rs/month)", lambda v: f"{v:,.0f}"),
                             (axs[1, 0], cac, "Cost per activation (Rs)", lambda v: f"{v:,.0f}"), (axs[1, 1], churn, "6-month churn %", lambda v: f"{v:.1f}%")]:
    hbar(ax, short, vals, fmt, highlight={1})
    ax.set_title(title, fontsize=11)
fig.suptitle("Segments compared (orange = recommended launch segment)", x=0.02, ha="left", fontweight="bold", color=INK)
fig.tight_layout(); fig.savefig(figs / "fig2_segments.png", dpi=180); plt.close(fig)

bucket = {"Unreachable after 3 attempts": "Reach & speed", "Owner had no time for a visit": "Reach & speed", "Visit not scheduled by sales": "Reach & speed",
          "Quote took too long to arrive": "Reach & speed", "Installation delayed beyond 21 days": "Reach & speed", "Quote too complex to understand": "Understanding & price",
          "Price too high": "Understanding & price", "Competitor offered cheaper plan": "Understanding & price", "Only wanted a mobile plan": "Understanding & price",
          "Missing GST or Udyam document": "Paperwork", "Found paperwork too long": "Paperwork", "Authorised signatory not available": "Paperwork",
          "Document details did not match": "Paperwork"}
D = L[L.act == 0]
dr = D.drop_reason.value_counts()
fig, ax = plt.subplots(figsize=(8.5, 6))
labs = list(dr.index)
hl = {i for i, r in enumerate(labs) if bucket.get(r) == "Reach & speed"}
hbar(ax, [f"{r}  [{bucket.get(r, 'Other')}]" for r in labs], (dr.values / len(D) * 100).tolist(), lambda v: f"{v:.1f}%", highlight=hl)
fig.suptitle("Why 4,632 leads dropped (orange = reach & speed, 41.2% of all drops)", x=0.02, ha="left", fontweight="bold", color=INK, fontsize=12)
ax.set_xlabel("% of all dropped leads")
fig.tight_layout(); fig.savefig(figs / "fig3_drop_reasons.png", dpi=180); plt.close(fig)

src = L.groupby("lead_source").agg(leads=("act", "size"), conv=("act", "mean"), cost=("acquisition_cost_inr", "sum"), act=("act", "sum"))
src["cpa"] = src.cost / src.act
src = src.sort_values("cpa")
fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.4))
hbar(axs[0], list(src.index), (src.conv * 100).tolist(), lambda v: f"{v:.1f}%", highlight={list(src.index).index("Referral")})
axs[0].set_title("Lead-to-activation %", fontsize=11)
hbar(axs[1], list(src.index), src.cpa.tolist(), lambda v: f"Rs {v:,.0f}", highlight={list(src.index).index("Referral")})
axs[1].set_title("Cost per activation", fontsize=11)
fig.suptitle("Lead sources (orange = Referral: best conversion at near-lowest cost)", x=0.02, ha="left", fontweight="bold", color=INK)
fig.tight_layout(); fig.savefig(figs / "fig4_sources.png", dpi=180); plt.close(fig)

A["calls"] = A.customer_follow_up_calls.clip(upper=5).astype(int)
t = A.groupby("calls").agg(churn=("churn", "mean"), nps=("nps_score", "mean"), n=("churn", "size"))
fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.2))
for ax, col, title, fmt in [(axs[0], "churn", "6-month churn", lambda v: f"{v:.0%}"), (axs[1], "nps", "Average NPS score (0-10)", lambda v: f"{v:.1f}")]:
    x = np.arange(len(t))
    ax.bar(x, t[col], color=BLUE, width=0.6, edgecolor=SURF, linewidth=2)
    ax.set_xticks(x, [f"{i}{'+' if i == 5 else ''}\n(n={n})" for i, n in zip(t.index, t.n)])
    ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
    for xi, v in zip(x, t[col]):
        ax.text(xi, v * 1.02, fmt(v), ha="center", va="bottom", color=INK, fontsize=9)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("Status-chase calls by the customer")
    ax.set_ylim(0, t[col].max() * 1.2)
    if col == "churn":
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
fig.suptitle("More chasing, more churn and lower NPS (368 activated customers)", x=0.02, ha="left", fontweight="bold", color=INK)
fig.tight_layout(); fig.savefig(figs / "fig5_chase_calls.png", dpi=180); plt.close(fig)

fig, ax = plt.subplots(figsize=(6.5, 2.6))
buckets = ["High (top 20%)", "Medium (next 40%)", "Low (bottom 40%)"]
hbar(ax, buckets, [16.0, 9.0, 1.4], lambda v: f"{v:.1f}% convert", highlight={0})
ax.set_title("Propensity buckets on held-out test leads (1,250)")
ax.set_xlabel("Lead-to-activation % (overall average 7.4%)")
fig.tight_layout(); fig.savefig(figs / "fig6_propensity.png", dpi=180); plt.close(fig)

kyc = json.loads((root / "analysis" / "kyc" / "kyc_results.json").read_text())
v = pd.Series([r["verdict"] for r in kyc]).value_counts().reindex(["Verified", "Re-upload needed", "Human review", "Blocked"]).fillna(0)
fig, ax = plt.subplots(figsize=(6.5, 2.6))
hbar(ax, list(v.index), v.values.tolist(), lambda x: f"{int(x)} of 12", highlight={1, 2, 3})
ax.set_title("KYC checker verdicts for applicants K01-K12")
ax.set_xlabel("Applicants")
fig.tight_layout(); fig.savefig(figs / "fig7_kyc.png", dpi=180); plt.close(fig)
print(sorted(p.name for p in figs.glob("*.png")))
