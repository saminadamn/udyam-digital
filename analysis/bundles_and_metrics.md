# Segments, starter bundles and success metrics

Built from smb_leads.csv and product_catalogue.csv. Every bundle below is checked by `analysis/validate_bundles.py` against the catalogue rules.

## 1. Segment ranking

Score = share of base × conversion × median monthly bundle value × 1 / 6-month churn (shown as an index, top segment = 100).

|   rank | segment                     | share of base   | conversion   |   median bundle Rs/mo | 6m churn   |   score (index, top=100) |   CAC per activation |   payback (months) |
|-------:|:----------------------------|:----------------|:-------------|----------------------:|:-----------|-------------------------:|---------------------:|-------------------:|
|      1 | Small multi-site businesses | 15%             | 11.0%        |                28,080 | 10.8%      |                      100 |               15,614 |                0.6 |
|      2 | Professional offices        | 25%             | 11.1%        |                 6,575 | 13.8%      |                       31 |               10,695 |                1.6 |
|      3 | Small manufacturers         | 5%              | 12.8%        |                15,910 | 8.1%       |                       29 |               15,324 |                1   |
|      4 | Micro retail & services     | 55%             | 4.1%         |                 2,470 | 22.7%      |                        6 |               20,007 |                8.1 |

### Launch first: Professional offices (clinics, CA firms, coaching centres)

1. Multi-site tops the formula (index 100 vs 31), but its bundle needs SD-WAN across 7 sites and 14-day installs, so it can't close without a human; it runs alongside as the field-assisted track.
2. Professional offices are the best self-serve fit: 11.1% conversion, the lowest CAC of any segment (Rs 10,695), 1.6-month payback, one site and 5-day installs.
3. They give the advisor and Smart KYC a clean proving ground (89% have an active GSTIN), before scaling to micro, which is 55% of the base but converts at 4.1% with an 8-month payback today.

## 2. Starter bundles

Quantity rule: Per-site products = number of sites. Per-user products = min(segment median quantity, employees). Everything else = segment median quantity.  
Pricing rule: micro at catalogue price_min (very price-sensitive); prof, multi and mfg at the midpoint of price_min and price_max, rounded to the rupee. Contract = longest min_contract_months in the bundle.

### Dukaan Digital (Micro retail & services)

*Why these products:* P07 in 100% and P01 in 92% of activated micro bundles; median 2 SIMs. Add-ons are the next three products, each bought by 30-34%.

| item | product | qty | Rs/unit/mo | setup/unit | install days | GSTIN? |
|---|---|---|---|---|---|---|
| core | P01 Biz Fibre 100 | 1 | 999 (range 999-1,199) | 0 | 5 | N |
| core | P07 Business Postpaid 299 | 2 | 299 (range 299-399) | 0 | 1 | N |
| add-on | P19 Cloud POS & Billing | 1 | 599 (range 599-899) | 2,500 | 3 | N |
| add-on | P22 Secure Wi-Fi with Guest Network | 1 | 399 (range 399-599) | 1,000 | 3 | N |
| add-on | P23 Cloud CCTV | 1 | 199 (range 199-299) | 1,800 | 4 | N |
| add-on, GSTIN only | P15 WhatsApp Business API Starter | 1 | 999 (range 999-1,499) | 0 | 3 | Y |

| profile | variant | monthly | setup | contract | install | rule check |
|---|---|---|---|---|---|---|
| typical: 3 staff, 1 site, tier 1, active GSTIN | core | Rs 1,597 | Rs 0 | 12 mo | 5 days | PASS |
| typical: 3 staff, 1 site, tier 1, active GSTIN | core + add-ons | Rs 2,794 | Rs 5,300 | 12 mo | 5 days | PASS |
| typical: 3 staff, 1 site, tier 1, active GSTIN | core + GSTIN add-ons | Rs 2,596 | Rs 0 | 12 mo | 5 days | PASS |
| typical: 3 staff, 1 site, tier 1, active GSTIN | fallback (fibre not feasible at the site) | Rs 1,497 | Rs 0 | 6 mo | 2 days | PASS |
| harder case: 2 staff, 1 site, tier 2, no GSTIN | core | Rs 1,597 | Rs 0 | 12 mo | 5 days | PASS |
| harder case: 2 staff, 1 site, tier 2, no GSTIN | core + add-ons | Rs 2,794 | Rs 5,300 | 12 mo | 5 days | PASS |
| harder case: 2 staff, 1 site, tier 2, no GSTIN | core + GSTIN add-ons | - | - | - | - | blocked: P15: needs an active GSTIN |
| harder case: 2 staff, 1 site, tier 2, no GSTIN | fallback (fibre not feasible at the site) | Rs 1,497 | Rs 0 | 6 mo | 2 days | PASS |

What this segment pays today (activated customers): median Rs 2,470/mo, median setup Rs 1,800, median contract 12 months.
Fallback: if fibre not feasible at the site, swap P01 for P04 (Biz 5G AirFiber 100).

### Office Pro (Professional offices)

*Why these products:* P16 in 100% (median 7 seats), P08 52% (median 3), P20 49% (median 6), P02 44% (most-bought fibre), P17 41%. Add-ons are 26-30% products.

| item | product | qty | Rs/unit/mo | setup/unit | install days | GSTIN? |
|---|---|---|---|---|---|---|
| core | P02 Biz Fibre 300 | 1 | 1,649 (range 1,499-1,799) | 0 | 5 | N |
| core | P08 Business Postpaid 599 | 3 | 699 (range 599-799) | 0 | 1 | N |
| core | P16 Cloud Email & Office Suite | 7 | 138 (range 125-150) | 0 | 1 | N |
| core | P20 Endpoint Security | 6 | 124 (range 99-149) | 0 | 1 | N |
| core | P17 Cloud Backup 1 TB | 1 | 599 (range 499-699) | 0 | 1 | N |
| add-on | P12 Cloud Telephony / SIP | 3 | 1,250 (range 1,000-1,500) | 2,000 | 5 | Y |
| add-on | P11 Static IP | 1 | 250 (range 200-300) | 0 | 1 | N |

| profile | variant | monthly | setup | contract | install | rule check |
|---|---|---|---|---|---|---|
| typical: 13 staff, 1 site, tier 2, active GSTIN | core | Rs 6,055 | Rs 0 | 12 mo | 5 days | PASS |
| typical: 13 staff, 1 site, tier 2, active GSTIN | core + add-ons | Rs 10,055 | Rs 6,000 | 12 mo | 5 days | PASS |
| typical: 13 staff, 1 site, tier 2, active GSTIN | tier-1 upgrade | - | - | - | - | blocked: P03: not sold in tier 2 |
| small clinic: 4 staff, 1 site, tier 1, active GSTIN | core | Rs 5,393 | Rs 0 | 12 mo | 5 days | PASS |
| small clinic: 4 staff, 1 site, tier 1, active GSTIN | core + add-ons | Rs 9,393 | Rs 6,000 | 12 mo | 5 days | PASS |
| small clinic: 4 staff, 1 site, tier 1, active GSTIN | tier-1 upgrade | - | - | - | - | blocked: P03: needs 5+ employees |

What this segment pays today (activated customers): median Rs 6,575/mo, median setup Rs 0, median contract 12 months.
Upgrade: Biz Fibre 1G is tier 1 only and needs 5+ staff and an active GSTIN.

### Chain Connect (Small multi-site businesses)

*Why these products:* P08 in 100% (median 4), P09 57%, P01 52%, P19 52%, all one per site. Add-ons are 31-46% products. Quantities scale with site count (median 7 sites).

| item | product | qty | Rs/unit/mo | setup/unit | install days | GSTIN? |
|---|---|---|---|---|---|---|
| core | P01 Biz Fibre 100 | 7 | 1,099 (range 999-1,199) | 0 | 5 | N |
| core | P09 Backup 4G/5G Failover | 7 | 549 (range 499-599) | 1,500 | 3 | N |
| core | P19 Cloud POS & Billing | 7 | 749 (range 599-899) | 2,500 | 3 | N |
| core | P08 Business Postpaid 599 | 4 | 699 (range 599-799) | 0 | 1 | N |
| add-on | P10 Managed SD-WAN | 7 | 3,000 (range 2,500-3,500) | 5,000 | 14 | Y |
| add-on | P23 Cloud CCTV | 10 | 249 (range 199-299) | 1,800 | 4 | N |
| add-on | P22 Secure Wi-Fi with Guest Network | 7 | 499 (range 399-599) | 1,000 | 3 | N |
| add-on | P13 Toll-free Number | 1 | 1,750 (range 1,500-2,000) | 1,000 | 3 | Y |
| add-on | P15 WhatsApp Business API Starter | 1 | 1,249 (range 999-1,499) | 0 | 3 | Y |

| profile | variant | monthly | setup | contract | install | rule check |
|---|---|---|---|---|---|---|
| typical: 61 staff, 7 sites, tier 2, active GSTIN | core | Rs 19,575 | Rs 28,000 | 12 mo | 5 days | PASS |
| typical: 61 staff, 7 sites, tier 2, active GSTIN | core + add-ons | Rs 49,557 | Rs 89,000 | 24 mo | 14 days | PASS |
| small chain: 12 staff, 3 sites, tier 1, active GSTIN | core | Rs 9,987 | Rs 12,000 | 12 mo | 5 days | PASS |
| small chain: 12 staff, 3 sites, tier 1, active GSTIN | core + add-ons | Rs 25,973 | Rs 49,000 | 24 mo | 14 days | PASS |

What this segment pays today (activated customers): median Rs 28,080/mo, median setup Rs 37,800, median contract 12 months.

### Factory Line (Small manufacturers)

*Why these products:* P08 and P16 in 100% (median 4 and 11), P05 51%, P20 43% (median 8.5). Add-ons are 32-38% products. Static IP (35%) is left out: it needs fibre, not a leased line.

| item | product | qty | Rs/unit/mo | setup/unit | install days | GSTIN? |
|---|---|---|---|---|---|---|
| core | P05 Internet Leased Line 20 | 1 | 10,000 (range 8,000-12,000) | 10,000 | 21 | Y |
| core | P08 Business Postpaid 599 | 4 | 699 (range 599-799) | 0 | 1 | N |
| core | P16 Cloud Email & Office Suite | 11 | 138 (range 125-150) | 0 | 1 | N |
| core | P20 Endpoint Security | 9 | 124 (range 99-149) | 0 | 1 | N |
| add-on | P21 Managed Firewall | 1 | 2,499 (range 1,999-2,999) | 4,000 | 10 | Y |
| add-on | P23 Cloud CCTV | 5 | 249 (range 199-299) | 1,800 | 4 | N |
| add-on | P24 Machine Monitoring IoT | 10 | 199 (range 149-249) | 3,000 | 10 | Y |

| profile | variant | monthly | setup | contract | install | rule check |
|---|---|---|---|---|---|---|
| typical: 74 staff, 1 site, tier 2, active GSTIN | core | Rs 15,430 | Rs 10,000 | 12 mo | 21 days | PASS |
| typical: 74 staff, 1 site, tier 2, active GSTIN | core + add-ons | Rs 21,164 | Rs 53,000 | 24 mo | 21 days | PASS |
| small unit: 12 staff, 1 site, tier 1, active GSTIN | core | Rs 15,430 | Rs 10,000 | 12 mo | 21 days | PASS |
| small unit: 12 staff, 1 site, tier 1, active GSTIN | core + add-ons | Rs 21,164 | Rs 53,000 | 24 mo | 21 days | PASS |

What this segment pays today (activated customers): median Rs 15,910/mo, median setup Rs 15,400, median contract 24 months.

### Rule checks the advisor must refuse

| case | blocked because | result |
|---|---|---|
| WhatsApp API without a GSTIN | P15: needs an active GSTIN | PASS |
| Biz Fibre 1G in a tier 2 city | P03: not sold in tier 2 | PASS |
| Cloud CCTV with no connection | P23: needs one of P01, P02, P03, P04, P05, P06 in the bundle | PASS |
| SD-WAN for only 2 sites | P10: needs 3+ sites | PASS |
| Leased line on a cancelled GSTIN | P05: needs an active GSTIN | PASS |
| Static IP on a leased line | P11: needs one of P01, P02, P03 in the bundle | PASS |
| Cloud Telephony for a 2-person office | P12: needs 3+ employees | PASS |
| Machine IoT for a 6-person unit | P24: needs 10+ employees | PASS |
| Toll-free on a suspended GSTIN | P13: needs an active GSTIN | PASS |

**Validation: 22 bundle checks and 9 negative checks, 0 failures.**

## 3. Success metrics

| # | metric | baseline (Apr-Jun 2026) | 6-month pilot target | how we get there |
|---|---|---|---|---|
| 1 | Lead-to-activation conversion | 7.4% | 11% | Professional offices already convert at 11.1% and referrals at 14.8%; removing the visit and the slow quote attacks the 41% of drops caused by reach and speed. |
| 2 | Days from lead to activation | 17.6 | 8 | 9.0 days pass before the quote is accepted today and 3.8 more for KYC; one session plus instant lookups removes most of that, leaving install time (core bundles: 5 days micro, 5 days professional). |
| 3 | CAC per activation | Rs 15,053 | Rs 8,000 | Digital leads cost Rs 232 each; at 11% conversion that's about Rs 2,106 per self-serve activation. Field and partner deals cost Rs 22,965 today; if they cost 40% less because the app does discovery and KYC, a 50/50 self-serve/assisted mix gives Rs 7,942. |
| 4 | 6-month churn | 15.2% | 11% | Customers who chased once churned 6% and twice 14%; the tracker and WhatsApp updates cut chasing, and the rules engine stops thin or mis-sold bundles. |
| 5 | Status-chase calls per customer | 3.0 | under 0.5 | Live tracker with expected dates from typical_install_days, proactive WhatsApp updates, and automatic escalation to a named agent when a step runs late. |

### Baselines by segment

| segment                     | conversion   |   days to activate | CAC per activation   | 6m churn   |   chase calls |
|:----------------------------|:-------------|-------------------:|:---------------------|:-----------|--------------:|
| Micro retail & services     | 4.1%         |               16.6 | Rs 20,007            | 22.7%      |          3.16 |
| Professional offices        | 11.1%        |               16.9 | Rs 10,695            | 13.8%      |          3.07 |
| Small multi-site businesses | 11.0%        |               18.8 | Rs 15,614            | 10.8%      |          2.78 |
| Small manufacturers         | 12.8%        |               20.5 | Rs 15,324            | 8.1%       |          2.86 |

Track these weekly on the admin dashboard, split by segment and by channel (self-serve vs assisted), so the pilot can show the digital journey beating the baseline on the same segment.