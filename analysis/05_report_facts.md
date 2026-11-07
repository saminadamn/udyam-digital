# Supplementary facts for the Phase 1 report

## Funnel with drop-off counts
| stage          |   leads |   conv_from_prev |   lost_at_this_step |   share_of_all_lost |
|:---------------|--------:|-----------------:|--------------------:|--------------------:|
| Lead           |    5000 |            nan   |                 nan |               nan   |
| Contacted      |    3406 |             68.1 |                1594 |                34.4 |
| Needs assessed |    1974 |             58   |                1432 |                30.9 |
| Quote accepted |     861 |             43.6 |                1113 |                24   |
| KYC complete   |     588 |             68.3 |                 273 |                 5.9 |
| Activated      |     368 |             62.6 |                 220 |                 4.7 |

## Mis-sold vs clean bundles (activated)
| mis_sold   |   customers |   churn |   nps |   calls |
|:-----------|------------:|--------:|------:|--------:|
| False      |         312 |   0.163 | 6.856 |   3.032 |
| True       |          56 |   0.089 | 6.893 |   2.893 |

## Segment profiles
### Micro retail & services
- leads: 2709
- share_%: 54.2
- conv_%: 4.1
- top_source: Field sales (33%)
- median_emp: 3.0
- median_sites: 1.0
- median_spend: 900.0
- gstin_%: 52.8
- tier1_%: 51.9
- top_interest: P23 Cloud CCTV, P22 Secure Wi-Fi with Guest Network, P18 Website + Domain Starter
- top_bought: P07 Business Postpaid 299 (100%), P01 Biz Fibre 100 (92%), P19 Cloud POS & Billing (34%)
- median_bundle: 2470.0
- mean_bundle: 2505
- churn_%: 22.7
- nps: 7.05
- main_drop: Unreachable after 3 attempts (16%)
- cac_per_activation: 20007
- cost_per_lead: 812
- days: 16.6
- calls: 3.16
- top_business_types: Stationery shop, Salon, Boutique, Mobile repair shop

### Professional offices
- leads: 1247
- share_%: 24.9
- conv_%: 11.1
- top_source: Field sales (36%)
- median_emp: 14.0
- median_sites: 1.0
- median_spend: 2600.0
- gstin_%: 86.1
- tier1_%: 51.4
- top_interest: P02 Biz Fibre 300, P20 Endpoint Security, P13 Toll-free Number
- top_bought: P16 Cloud Email & Office Suite (100%), P08 Business Postpaid 599 (52%), P20 Endpoint Security (49%)
- median_bundle: 6575.0
- mean_bundle: 6796
- churn_%: 13.8
- nps: 6.92
- main_drop: Unreachable after 3 attempts (18%)
- cac_per_activation: 10695
- cost_per_lead: 1184
- days: 16.9
- calls: 3.07
- top_business_types: Law office, Coaching centre, Travel agency, Diagnostic lab

### Small manufacturers
- leads: 289
- share_%: 5.8
- conv_%: 12.8
- top_source: Field sales (35%)
- median_emp: 85.0
- median_sites: 1.0
- median_spend: 14300.0
- gstin_%: 99.3
- tier1_%: 49.8
- top_interest: P17 Cloud Backup 1 TB, P08 Business Postpaid 599, P20 Endpoint Security
- top_bought: P08 Business Postpaid 599 (100%), P16 Cloud Email & Office Suite (100%), P05 Internet Leased Line 20 (51%)
- median_bundle: 15910.0
- mean_bundle: 19980
- churn_%: 8.1
- nps: 6.46
- main_drop: Unreachable after 3 attempts (20%)
- cac_per_activation: 15324
- cost_per_lead: 1962
- days: 20.5
- calls: 2.86
- top_business_types: Plastic moulding unit, Packaging unit, Textile unit, Auto-parts unit

### Small multi-site businesses
- leads: 755
- share_%: 15.1
- conv_%: 11.0
- top_source: Field sales (37%)
- median_emp: 71.0
- median_sites: 8.0
- median_spend: 9150.0
- gstin_%: 98.3
- tier1_%: 51.1
- top_interest: P10 Managed SD-WAN, P15 WhatsApp Business API Starter, P14 Business SMS 10k
- top_bought: P08 Business Postpaid 599 (100%), P09 Backup 4G/5G Failover (57%), P01 Biz Fibre 100 (52%)
- median_bundle: 28080.0
- mean_bundle: 31233
- churn_%: 10.8
- nps: 6.7
- main_drop: Unreachable after 3 attempts (20%)
- cac_per_activation: 15614
- cost_per_lead: 1717
- days: 18.8
- calls: 2.78
- top_business_types: Budget hotel group, Electronics retail chain, Pharmacy chain, Apparel retail chain

## Lead source quality
| source            |   leads |   share_% |   conv_% |   cost_per_lead |   total_cost |   cost_per_activation |   never_contacted_% |   dropoff_% |   churn_% |   nps |   median_bundle |   days |   mis_sold_% |
|:------------------|--------:|----------:|---------:|----------------:|-------------:|----------------------:|--------------------:|------------:|----------:|------:|----------------:|-------:|-------------:|
| WhatsApp campaign |     358 |       7.2 |      2.8 |             112 |        40260 |                  4026 |                58.7 |        97.2 |      20   |  7.1  |            6915 |   19.8 |         20   |
| Referral          |     413 |       8.3 |     14.8 |             605 |       250020 |                  4099 |                21.1 |        85.2 |      24.6 |  7.11 |            5730 |   16.6 |         16.4 |
| Inbound call      |     504 |      10.1 |      9.5 |             487 |       245440 |                  5113 |                19.8 |        90.5 |      14.6 |  6.65 |            6960 |   17.6 |         12.5 |
| Website form      |     995 |      19.9 |      4.3 |             274 |       273120 |                  6352 |                45.1 |        95.7 |      11.6 |  7.07 |            8110 |   17.4 |         16.3 |
| Channel partner   |    1010 |      20.2 |      8   |            1672 |      1688930 |                 20851 |                28.8 |        92   |      18.5 |  6.75 |            5110 |   17.9 |         14.8 |
| Field sales       |    1720 |      34.4 |      7.3 |            1769 |      3041870 |                 24335 |                26.6 |        92.7 |       9.6 |  6.8  |            7420 |   17.8 |         15.2 |

Share of total acquisition spend: WhatsApp campaign 1%, Referral 5%, Inbound call 4%, Website form 5%, Channel partner 30%, Field sales 55%
Share of activations: Field sales 34%, Channel partner 22%, Referral 17%, Inbound call 13%, Website form 12%, WhatsApp campaign 3%

## Customer experience
### Languages
| preferred_language   |   leads |   share_% |   conv_% |
|:---------------------|--------:|----------:|---------:|
| Hindi                |    2137 |      42.7 |      7.9 |
| English              |    1168 |      23.4 |      8   |
| Marathi              |     505 |      10.1 |      6.3 |
| Kannada              |     253 |       5.1 |      5.1 |
| Gujarati             |     233 |       4.7 |      6   |
| Telugu               |     207 |       4.1 |      7.7 |
| Tamil                |     207 |       4.1 |      4.3 |
| Bengali              |     111 |       2.2 |      9   |
| Punjabi              |      96 |       1.9 |      4.2 |
| Malayalam            |      83 |       1.7 |      8.4 |

Hindi+English share: 66.1%; regional share: 33.9%

### Language by state (top language per state)
| state          | preferred_language   |
|:---------------|:---------------------|
| Andhra Pradesh | Telugu (46%)         |
| Bihar          | Hindi (76%)          |
| Delhi          | Hindi (78%)          |
| Gujarat        | Gujarati (43%)       |
| Karnataka      | Kannada (45%)        |
| Kerala         | Malayalam (43%)      |
| Madhya Pradesh | Hindi (75%)          |
| Maharashtra    | Marathi (49%)        |
| Punjab         | Punjabi (52%)        |
| Rajasthan      | Hindi (73%)          |
| Tamil Nadu     | Tamil (45%)          |
| Telangana      | Telugu (42%)         |
| Uttar Pradesh  | Hindi (75%)          |
| West Bengal    | Bengali (48%)        |

### Business types (top 15)
| business_type      | segment                     |   leads |   conv_% |
|:-------------------|:----------------------------|--------:|---------:|
| Stationery shop    | Micro retail & services     |     291 |      3.4 |
| Salon              | Micro retail & services     |     282 |      5.7 |
| Boutique           | Micro retail & services     |     278 |      4.7 |
| Mobile repair shop | Micro retail & services     |     275 |      4.7 |
| Bakery             | Micro retail & services     |     274 |      3.3 |
| Sweet shop         | Micro retail & services     |     268 |      5.2 |
| Hardware store     | Micro retail & services     |     265 |      3   |
| Pharmacy           | Micro retail & services     |     260 |      3.5 |
| Optician           | Micro retail & services     |     258 |      3.5 |
| Kirana store       | Micro retail & services     |     258 |      3.5 |
| Coaching centre    | Professional offices        |     135 |      8.9 |
| Law office         | Professional offices        |     135 |     14.1 |
| Travel agency      | Professional offices        |     132 |     11.4 |
| Budget hotel group | Small multi-site businesses |     128 |     11.7 |
| Diagnostic lab     | Professional offices        |     128 |      9.4 |

### Employee count
|       |   employee_count |
|:------|-----------------:|
| count |           5000   |
| mean  |             20.5 |
| std   |             31.3 |
| min   |              1   |
| 25%   |              3   |
| 50%   |              6   |
| 75%   |             21   |
| max   |            150   |

### Current internet and provider
| ci                 |   leads |   spend |   conv_% |
|:-------------------|--------:|--------:|---------:|
| Business broadband |    1433 |    3250 |      9.3 |
| Home broadband     |    1250 |    1300 |      7.6 |
| Leased line        |     173 |   11750 |     15   |
| Mixed per site     |     221 |    9300 |     12.7 |
| Mobile hotspot     |    1799 |     950 |      4.5 |
| Unknown            |     124 |     900 |      4   |

| current_provider    |   count |
|:--------------------|--------:|
| Accel (mobile only) |    1505 |
| Competitor A        |    1200 |
| Local ISP           |    1042 |
| Competitor B        |     744 |
| Accel               |     385 |
| Unknown             |     124 |

Conversion by current provider:
| pr                  |   leads |   conv_% |
|:--------------------|--------:|---------:|
| Accel               |     385 |      9.1 |
| Accel (mobile only) |    1505 |      9.2 |
| Competitor A        |    1200 |      6.5 |
| Competitor B        |     744 |      7.4 |
| Local ISP           |    1042 |      5.4 |
| Unknown             |     124 |      4   |
Existing Accel customers: 1890 leads (37.8%), conversion 9.2% vs 6.2% for everyone else

### Telecom spend by segment (median, Rs/month)
| segment                     |   25% |   50% |   75% |
|:----------------------------|------:|------:|------:|
| Micro retail & services     |   650 |   900 |  1150 |
| Professional offices        |  2000 |  2600 |  3150 |
| Small manufacturers         | 10700 | 14300 | 17050 |
| Small multi-site businesses |  6850 |  9150 | 11500 |

Activated customers: median bundle value / prior telecom spend = 2.59
| segment                     |   ratio |
|:----------------------------|--------:|
| Micro retail & services     |    2.74 |
| Professional offices        |    2.66 |
| Small manufacturers         |    1.23 |
| Small multi-site businesses |    3.04 |

### Products of interest (top 10)
| product                             |   leads |   share_of_leads_% |
|:------------------------------------|--------:|-------------------:|
| P07 Business Postpaid 299           |     838 |               16.8 |
| P15 WhatsApp Business API Starter   |     827 |               16.5 |
| P22 Secure Wi-Fi with Guest Network |     814 |               16.3 |
| P14 Business SMS 10k                |     813 |               16.3 |
| P23 Cloud CCTV                      |     787 |               15.7 |
| P18 Website + Domain Starter        |     748 |               15   |
| P04 Biz 5G AirFiber 100             |     719 |               14.4 |
| P01 Biz Fibre 100                   |     713 |               14.3 |
| P19 Cloud POS & Billing             |     677 |               13.5 |
| P08 Business Postpaid 599           |     283 |                5.7 |

Conversion by product asked about (n>=150): P17 Cloud Backup 1 TB 14.1%, P03 Biz Fibre 1G 12.5%, P09 Backup 4G/5G Failover 12.5%, P21 Managed Firewall 12.4%, P20 Endpoint Security 12.2%, P16 Cloud Email & Office Suite 11.8%, P08 Business Postpaid 599 9.9%, P13 Toll-free Number 9.7%, P11 Static IP 9.4%, P12 Cloud Telephony / SIP 9.2%, P02 Biz Fibre 300 7.7%, P14 Business SMS 10k 6.4%, P15 WhatsApp Business API Starter 6.2%, P22 Secure Wi-Fi with Guest Network 5.7%, P01 Biz Fibre 100 5.6%, P04 Biz 5G AirFiber 100 5.4%, P07 Business Postpaid 299 5.4%, P19 Cloud POS & Billing 4.6%, P23 Cloud CCTV 4.6%, P18 Website + Domain Starter 4.5%

### Follow-up calls distribution (activated)
|   customer_follow_up_calls |   count |
|---------------------------:|--------:|
|                          1 |      34 |
|                          2 |      84 |
|                          3 |     137 |
|                          4 |      70 |
|                          5 |      43 |

% of activated customers who chased 3+ times: 68%

### Activation duration
|       |   days_lead_to_activation |
|:------|--------------------------:|
| count |                     368   |
| mean  |                      17.6 |
| std   |                       4.2 |
| min   |                       7   |
| 25%   |                      15   |
| 50%   |                      17   |
| 75%   |                      20   |
| max   |                      31   |
% activated within 14 days: 23%; over 21 days: 16%

### NPS distribution (activated)
Promoters (9-10): 18%, passives (7-8): 38%, detractors (0-6): 43%, NPS-style score = -25; mean score 6.86
Churn among detractors: 13%, among promoters: 19%

## Persona slices
### Micro shop on mobile hotspot: 1597 leads (31.9%)
- conv 4.1%; median employees 4; median sites 1; median spend Rs 900; GSTIN 53%; tier 1 52%
- languages: Hindi 44%, English 24%, Marathi 10%
- top business types: Mobile repair shop, Stationery shop, Bakery, Pharmacy
- top sources: Field sales 34%, Channel partner 20%, Website form 19%
- top interests: WhatsApp Business API Starter 23%, Website + Domain Starter 23%, Secure Wi-Fi with Guest Network 22%, Business Postpaid 299 22%
- top drop reasons: Unreachable after 3 attempts 18%, Owner had no time for a visit 12%, Price too high 11%
- contact role: Owner 41%, Manager 21%
- activated 65: median bundle Rs 2,440, churn 29%, NPS 7.2, calls 3.2, days 16.4

### Micro shop with broadband: 1112 leads (22.2%)
- conv 4.0%; median employees 3; median sites 1; median spend Rs 900; GSTIN 52%; tier 1 52%
- languages: Hindi 44%, English 22%, Marathi 10%
- top business types: Stationery shop, Salon, Boutique, Sweet shop
- top sources: Field sales 32%, Channel partner 22%, Website form 21%
- top interests: Cloud CCTV 28%, Biz 5G AirFiber 100 23%, Secure Wi-Fi with Guest Network 22%, Cloud POS & Billing 22%
- top drop reasons: Unreachable after 3 attempts 14%, Owner had no time for a visit 13%, Not interested on first call 10%
- contact role: Owner 42%, Manager 20%
- activated 45: median bundle Rs 2,510, churn 13%, NPS 6.8, calls 3.2, days 17.0

### Professional office: 1247 leads (24.9%)
- conv 11.1%; median employees 14; median sites 1; median spend Rs 2,600; GSTIN 86%; tier 1 51%
- languages: Hindi 41%, English 24%, Marathi 10%
- top business types: Law office, Coaching centre, Travel agency, Diagnostic lab
- top sources: Field sales 36%, Channel partner 20%, Website form 19%
- top interests: Biz Fibre 300 13%, Endpoint Security 12%, Toll-free Number 12%, Website + Domain Starter 12%
- top drop reasons: Unreachable after 3 attempts 18%, Not interested on first call 10%, Owner had no time for a visit 10%
- contact role: Owner 40%, Partner 20%
- activated 138: median bundle Rs 6,575, churn 14%, NPS 6.9, calls 3.1, days 16.9

### Multi-site chain: 755 leads (15.1%)
- conv 11.0%; median employees 71; median sites 8; median spend Rs 9,150; GSTIN 98%; tier 1 51%
- languages: Hindi 41%, English 23%, Marathi 12%
- top business types: Budget hotel group, Electronics retail chain, Pharmacy chain, Apparel retail chain
- top sources: Field sales 37%, Website form 21%, Channel partner 18%
- top interests: Managed SD-WAN 14%, WhatsApp Business API Starter 13%, Business SMS 10k 12%, Business Postpaid 299 12%
- top drop reasons: Unreachable after 3 attempts 20%, Owner had no time for a visit 12%, Not interested on first call 11%
- contact role: Owner 43%, Manager 22%
- activated 83: median bundle Rs 28,080, churn 11%, NPS 6.7, calls 2.8, days 18.8

### Small manufacturer: 289 leads (5.8%)
- conv 12.8%; median employees 85; median sites 1; median spend Rs 14,300; GSTIN 99%; tier 1 50%
- languages: Hindi 45%, English 22%, Marathi 7%
- top business types: Plastic moulding unit, Packaging unit, Textile unit, Auto-parts unit
- top sources: Field sales 35%, Channel partner 21%, Website form 20%
- top interests: Cloud Backup 1 TB 20%, Business Postpaid 599 18%, Endpoint Security 17%, Static IP 17%
- top drop reasons: Unreachable after 3 attempts 20%, Not interested on first call 13%, Owner had no time for a visit 8%
- contact role: Owner 42%, Manager 22%
- activated 37: median bundle Rs 15,910, churn 8%, NPS 6.5, calls 2.9, days 20.5

## KYC-stage baselines
- KYC completion rate (quote accepted -> KYC complete): 588/861 = 68.3%
- Leads lost at the KYC step: 273; of these, paperwork reasons: 273 (100%)
- 'Document details did not match' drops: 47 = 5.5% of quote-accepted leads, 17% of KYC-step losses
- Drop reasons at the KYC step: Missing GST or Udyam document 94, Found paperwork too long 79, Authorised signatory not available 53, Document details did not match 47
- Leads lost after KYC (KYC complete -> not activated): 220; reasons: Installation delayed beyond 21 days 98, Customer cancelled before install 53, Site not feasible for fibre 41, First payment failed 28
- No escalation-time field exists in the data; the 'chase calls' field (mean 3.01) is the closest proxy for unresolved status.

## Catalogue facts
- Products: 25; categories: Connectivity 11, Communication 4, Cloud & Productivity 4, Security 3, IoT & Physical 3
- requires_gstin=Y: 10 products: P03, P05, P06, P10, P12, P13, P14, P15, P21, P24
- has requires_one_of: 7 products: P09, P10, P11, P12, P21, P22, P23
- tier 1 only: P03
- min_employees > 1: P03 (5), P05 (10), P06 (25), P10 (10), P12 (3), P21 (10), P24 (10)
- min_sites > 1: P10 (3)
- setup fee > 0: 12 products; contract range 1-24 months; install range 1-30 days
- Most purchased (share of activated customers): P08 Business Postpaid 599 52%, P01 Biz Fibre 100 49%, P07 Business Postpaid 299 48%, P16 Cloud Email & Office Suite 48%, P02 Biz Fibre 300 27%, P23 Cloud CCTV 23%, P20 Endpoint Security 23%, P19 Cloud POS & Billing 22%, P09 Backup 4G/5G Failover 22%, P22 Secure Wi-Fi with Guest Network 17%
- Activated: median setup Rs 2,650, mean Rs 13,879; contracts: 6 mo 3, 12 mo 304, 24 mo 61