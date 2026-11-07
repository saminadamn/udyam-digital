import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "propensity.pkl"

LABELS = {
    "lead_source": "came via {v}",
    "segment": "{v} segment",
    "preferred_language": "prefers {v}",
    "current_internet": "currently on {v}",
    "annual_turnover_band": "turnover {v}",
    "has_gstin": {"Y": "has a GSTIN", "N": "no GSTIN"},
    "has_udyam": {"Y": "Udyam registered", "N": "no Udyam"},
    "city_tier": "tier {v} city",
    "num_sites": "{v} sites",
    "n_interest": "asked about {v} products",
    "log_spend": "telecom spend",
    "log_emp": "team size",
}


@lru_cache(maxsize=1)
def _load():
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def _frame(lead):
    interest = lead.get("products_of_interest") or ""
    if isinstance(interest, str):
        interest = [i for i in interest.split(";") if i]
    return pd.DataFrame([{
        "segment": lead["segment"],
        "lead_source": lead.get("lead_source", "Website form"),
        "preferred_language": lead.get("preferred_language", "Hindi"),
        "current_internet": lead.get("current_internet") or "Unknown",
        "annual_turnover_band": lead.get("annual_turnover_band", "40 lakh - 1.5 cr"),
        "has_gstin": "Y" if lead.get("has_gstin") in ("Y", True) else "N",
        "has_udyam": "Y" if lead.get("has_udyam") in ("Y", True) else "N",
        "city_tier": int(lead.get("city_tier", 1)),
        "num_sites": int(lead.get("num_sites", 1)),
        "n_interest": len(interest),
        "log_spend": float(np.log1p(lead.get("monthly_telecom_spend_inr", 2000))),
        "log_emp": float(np.log1p(lead.get("employee_count", 3))),
    }])


def _describe(feature, row):
    raw = feature.split("__", 1)[1]
    for key, label in LABELS.items():
        if raw == key or raw.startswith(key + "_"):
            v = raw[len(key) + 1:] if raw != key else row[key]
            if isinstance(label, dict):
                return label.get(str(v), f"{key} {v}")
            return label.format(v=v)
    return raw


def predict(lead: dict) -> dict:
    bundle = _load()
    pipe = bundle["model"]
    row = _frame(lead)
    score = float(pipe.predict_proba(row)[0, 1])
    bucket = "High" if score >= bundle["hi"] else "Medium" if score >= bundle["lo"] else "Low"
    pre, model = pipe.named_steps["pre"], pipe.named_steps["m"]
    x = pre.transform(row)
    x = x.toarray()[0] if hasattr(x, "toarray") else np.asarray(x)[0]
    contrib = x * model.coef_[0]
    names = pre.get_feature_names_out()
    order = np.argsort(-np.abs(contrib))
    reasons = []
    for i in order:
        if abs(contrib[i]) < 0.05:
            break
        sign = "+" if contrib[i] > 0 else "-"
        reasons.append(f"{sign} {_describe(names[i], row.iloc[0])}")
        if len(reasons) == 3:
            break
    return {"score": round(score, 3), "bucket": bucket, "top_3_reasons": reasons}


if __name__ == "__main__":
    print(predict({"segment": "Professional offices", "lead_source": "Referral", "preferred_language": "Hindi",
                   "has_gstin": "Y", "has_udyam": "Y", "city_tier": 1, "employee_count": 8, "num_sites": 1,
                   "current_internet": "Home broadband", "monthly_telecom_spend_inr": 4000, "products_of_interest": "P02;P16"}))
    print(predict({"segment": "Micro retail & services", "lead_source": "WhatsApp campaign", "preferred_language": "Tamil",
                   "has_gstin": "N", "has_udyam": "N", "city_tier": 2, "employee_count": 2, "num_sites": 1,
                   "current_internet": "Mobile hotspot", "monthly_telecom_spend_inr": 600, "annual_turnover_band": "< 40 lakh"}))


def predict_many(leads: list[dict]) -> list[dict]:
    bundle = _load()
    pipe = bundle["model"]
    frame = pd.concat([_frame(l) for l in leads], ignore_index=True)
    scores = pipe.predict_proba(frame)[:, 1]
    pre, model = pipe.named_steps["pre"], pipe.named_steps["m"]
    x = pre.transform(frame)
    x = x.toarray() if hasattr(x, "toarray") else np.asarray(x)
    contrib = x * model.coef_[0]
    names = pre.get_feature_names_out()
    out = []
    for i, score in enumerate(scores):
        order = np.argsort(-np.abs(contrib[i]))
        reasons = []
        for j in order:
            if abs(contrib[i, j]) < 0.05 or len(reasons) == 3:
                break
            reasons.append(f"{'+' if contrib[i, j] > 0 else '-'} {_describe(names[j], frame.iloc[i])}")
        bucket = "High" if score >= bundle["hi"] else "Medium" if score >= bundle["lo"] else "Low"
        out.append({"score": round(float(score), 3), "bucket": bucket, "top_3_reasons": reasons})
    return out
