# Propensity model

Target: outcome == Activated. Features (all known when the lead is created): segment, lead_source, preferred_language, current_internet, annual_turnover_band, has_gstin, has_udyam, city_tier, employee_count (log), num_sites, monthly_telecom_spend_inr (log), number of products_of_interest.
Left out on purpose: stage dates, drop_reason, follow-up calls, bundle and value fields (leakage), and GSTIN registry status (past sellers closed deals on cancelled GSTINs, so the model would learn to reward a compliance problem).

Stratified split: train 3750, test 1250, base rate 7.4%

- Logistic regression: AUC 0.731; top 20% of scored leads convert at 16.0% (vs 7.4% base) and contain 43% of all activations
- LightGBM: AUC 0.688; top 20% of scored leads convert at 11.6% (vs 7.4% base) and contain 32% of all activations
- Logistic regression 5-fold CV AUC: 0.706

Chosen for the app: logistic regression (as good, and each reason is explainable)
Buckets on the held-out test set (top 20% = High, next 40% = Medium, bottom 40% = Low):
| bucket   |   test leads |   conv |
|:---------|-------------:|-------:|
| High     |          250 |   16   |
| Medium   |          500 |    9   |
| Low      |          500 |    1.4 |

Final model refit on all 5,000 leads. Thresholds: High >= 0.629, Medium >= 0.363
| bucket   |   leads |   conv |
|:---------|--------:|-------:|
| High     |    1000 |   15.9 |
| Medium   |    2000 |    8.7 |
| Low      |    2000 |    1.8 |

## Strongest drivers (logistic coefficients)
Raises odds: lead_source_Referral (+0.93), has_gstin_Y (+0.60), lead_source_Inbound call (+0.32), segment_Small manufacturers (+0.29), preferred_language_Hindi (+0.28), segment_Small multi-site businesses (+0.28), preferred_language_English (+0.25), current_internet_Leased line (+0.25), current_internet_Mixed per site (+0.24), annual_turnover_band_5 - 25 cr (+0.23)

Lowers odds: lead_source_WhatsApp campaign (-0.97), segment_Micro retail & services (-0.80), has_gstin_N (-0.70), lead_source_Website form (-0.58), preferred_language_Tamil (-0.51), preferred_language_Kannada (-0.34), city_tier (-0.25), current_internet_Business broadband (-0.22), annual_turnover_band_< 40 lakh (-0.22), current_internet_Unknown (-0.19)