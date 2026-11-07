# Pricing rule (build Phase 2)

Code: `backend/app/pricing/service.py`. Every price sits inside the catalogue's `price_min_inr_per_month`–`price_max_inr_per_month` range. A test checks this for all 25 products under both rules.

| Rule | Who | Unit price | Why |
|---|---|---|---|
| `micro_min_v1` | Micro retail & services | Catalogue minimum | The case calls this segment very price-sensitive. Its median bundle today is Rs 2,470, and "price too high" is the third-largest drop reason (414 leads) [S] |
| `midpoint_v1` | Professional offices, multi-site businesses, manufacturers | Rounded midpoint of min and max | A transparent middle price, with room for the sales team on assisted deals |

**What the owner sees**

- **Monthly total:** sum of unit price × quantity for the selected items. One number.
- **One-time setup:** sum of `one_time_setup_inr` × quantity for the selected items, shown separately from the monthly price.
- **Contract:** the longest `min_contract_months` among the selected items. If SD-WAN or a firewall is added, the plan becomes 24 months.
- **Live in about N days:** the longest `typical_install_days` among the selected items, plus 1.
- **Compared with what you pay now:** monthly total − what the owner says they pay today. When the plan costs more, the screen adds "Your plan also includes services you don't have today". Activated customers' bundles cost a median 2.6× their previous spend [F], so this is said plainly rather than hidden.

**Examples** (from the 10 advisor test profiles)

| Bundle | Rule | Monthly | Setup | Contract |
|---|---|---|---|---|
| Kirana, 3 staff, no GSTIN: Biz Fibre 100 + 2 SIMs + Cloud POS + CCTV | micro_min_v1 | Rs 2,395 | Rs 4,300 | 12 months |
| Clinic, 12 staff: Office Pro core | midpoint_v1 | Rs 6,055 | Rs 0 | 12 months |
| Same clinic + Static IP + 1 more email seat | midpoint_v1 | Rs 6,443 | Rs 0 | 12 months |

**Not done, on purpose:** no discounts or per-customer prices. One transparent price is what the case asks for, and nothing in the data shows discounts improve conversion (Phase 1 report, Section 12).
