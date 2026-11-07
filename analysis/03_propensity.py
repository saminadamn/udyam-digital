import sys
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
import lightgbm as lgb

root = Path(sys.argv[1])
c = root / "data" / "clean"
L = pd.read_parquet(c / "leads.parquet")
L = L.astype({k: "object" for k in L.select_dtypes(["category", "string"]).columns})
L = L.astype({k: "float64" for k in L.select_dtypes(["Int8", "Int16", "Int32", "Float64"]).columns})
gst = pd.read_parquet(c / "gstin.parquet").astype("object")[["gstin", "status"]]
L = L.merge(gst, on="gstin", how="left")
L["gst_status"] = L.status.fillna("None")
L["n_interest"] = L.products_of_interest.fillna("").str.split(";").apply(lambda x: len([i for i in x if i]))
L["current_internet"] = L.current_internet.fillna("Unknown")
y = (L.outcome == "Activated").astype(int).values

cat_cols = ["segment", "lead_source", "preferred_language", "current_internet", "annual_turnover_band", "has_gstin", "has_udyam"]
num_cols = ["city_tier", "employee_count", "num_sites", "monthly_telecom_spend_inr", "n_interest"]
X = L[cat_cols + num_cols].copy()
X["log_spend"] = np.log1p(X.monthly_telecom_spend_inr)
X["log_emp"] = np.log1p(X.employee_count)
num_cols2 = ["city_tier", "num_sites", "n_interest", "log_spend", "log_emp"]

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=7)

pre = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore", min_frequency=20), cat_cols), ("n", StandardScaler(), num_cols2)])
lr = Pipeline([("pre", pre), ("m", LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced"))])
lr.fit(Xtr, ytr)
p_lr = lr.predict_proba(Xte)[:, 1]

Xg = X.copy()
for col in cat_cols:
    Xg[col] = Xg[col].astype("category")
gb_cols = cat_cols + num_cols2
Xgtr, Xgte = Xg.loc[Xtr.index, gb_cols], Xg.loc[Xte.index, gb_cols]
gbm = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8, subsample_freq=1,
                         colsample_bytree=0.8, reg_lambda=2.0, verbose=-1, random_state=7)
gbm.fit(Xgtr, ytr)
p_gb = gbm.predict_proba(Xgte)[:, 1]


def top_k(pred, yv, frac=0.2):
    k = int(len(pred) * frac)
    idx = np.argsort(-pred)[:k]
    return yv[idx].mean(), yv[idx].sum() / yv.sum()


out = ["# Propensity model\n",
       "Target: outcome == Activated. Features (all known when the lead is created): " + ", ".join(cat_cols + ["city_tier", "employee_count (log)", "num_sites", "monthly_telecom_spend_inr (log)", "number of products_of_interest"]) + ".",
       "Left out on purpose: stage dates, drop_reason, follow-up calls, bundle and value fields (leakage), and GSTIN registry status (past sellers closed deals on cancelled GSTINs, so the model would learn to reward a compliance problem).",
       "", f"Stratified split: train {len(Xtr)}, test {len(Xte)}, base rate {y.mean():.1%}", ""]
for name, pr in [("Logistic regression", p_lr), ("LightGBM", p_gb)]:
    prec, rec = top_k(pr, yte)
    out.append(f"- {name}: AUC {roc_auc_score(yte, pr):.3f}; top 20% of scored leads convert at {prec:.1%} (vs {yte.mean():.1%} base) and contain {rec:.0%} of all activations")
cv = cross_val_predict(lr, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=1), method="predict_proba")[:, 1]
out.append(f"- Logistic regression 5-fold CV AUC: {roc_auc_score(y, cv):.3f}")
out.append("")

chosen = lr if roc_auc_score(yte, p_lr) >= roc_auc_score(yte, p_gb) - 0.01 else None
out.append(f"Chosen for the app: {'logistic regression (as good, and each reason is explainable)' if chosen is lr else 'LightGBM'}")
lr.fit(X, y)
full = lr.predict_proba(X)[:, 1]
hi, lo = np.quantile(full, 0.8), np.quantile(full, 0.4)
te_lr = Pipeline([("pre", pre), ("m", LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced"))]).fit(Xtr, ytr).predict_proba(Xte)[:, 1]
tb = pd.Series(np.where(te_lr >= np.quantile(te_lr, 0.8), "High", np.where(te_lr >= np.quantile(te_lr, 0.4), "Medium", "Low")))
tt = pd.DataFrame({"bucket": tb, "y": yte}).groupby("bucket").y.agg(["size", "mean"]).reindex(["High", "Medium", "Low"])
tt.columns = ["test leads", "conv"]
tt["conv"] = (tt.conv * 100).round(1)
out.append("Buckets on the held-out test set (top 20% = High, next 40% = Medium, bottom 40% = Low):")
out.append(tt.to_markdown())
out.append("")
L["score"] = full
L["bucket"] = np.where(full >= hi, "High", np.where(full >= lo, "Medium", "Low"))
t = L.groupby("bucket").agg(leads=("lead_id", "size"), conv=("outcome", lambda s: (s == "Activated").mean())).reindex(["High", "Medium", "Low"])
t["conv"] = (t.conv * 100).round(1)
out.append(f"Final model refit on all 5,000 leads. Thresholds: High >= {hi:.3f}, Medium >= {lo:.3f}")
out.append(t.to_markdown())
out.append("")

names = lr.named_steps["pre"].get_feature_names_out()
coefs = pd.Series(lr.named_steps["m"].coef_[0], index=names).sort_values()
out.append("## Strongest drivers (logistic coefficients)")
out.append("Raises odds: " + ", ".join(f"{k.split('__')[1]} ({v:+.2f})" for k, v in coefs.tail(10)[::-1].items()))
out.append("")
out.append("Lowers odds: " + ", ".join(f"{k.split('__')[1]} ({v:+.2f})" for k, v in coefs.head(10).items()))

L[["lead_id", "score", "bucket"]].to_csv(root / "analysis" / "lead_scores.csv", index=False)
models = root / "backend" / "models"
models.mkdir(parents=True, exist_ok=True)
with open(models / "propensity.pkl", "wb") as f:
    pickle.dump({"model": lr, "cat_cols": cat_cols, "num_cols": num_cols2, "hi": float(hi), "lo": float(lo)}, f)
(root / "analysis" / "03_propensity.md").write_text("\n".join(out))
print("\n".join(out))
