# Signals in smb_leads.csv

Base rate: **7.4%** of 5,000 leads activated (368). Every table uses data/clean from step 1.1.

## Q1. Conversion by lead attribute

### Segment
| segment                     |   leads |   activated |   conv % | vs avg   |
|:----------------------------|--------:|------------:|---------:|:---------|
| Small manufacturers         |     289 |          37 |     12.8 | 1.74x    |
| Professional offices        |    1247 |         138 |     11.1 | 1.5x     |
| Small multi-site businesses |     755 |          83 |     11   | 1.49x    |
| Micro retail & services     |    2709 |         110 |      4.1 | 0.55x    |

**Takeaway:** Small manufacturers converts best at 12.8% and Micro retail & services worst at 4.1%.

### Lead source
| lead_source       |   leads |   activated |   conv % | vs avg   |
|:------------------|--------:|------------:|---------:|:---------|
| Referral          |     413 |          61 |     14.8 | 2.01x    |
| Inbound call      |     504 |          48 |      9.5 | 1.29x    |
| Channel partner   |    1010 |          81 |      8   | 1.09x    |
| Field sales       |    1720 |         125 |      7.3 | 0.99x    |
| Website form      |     995 |          43 |      4.3 | 0.59x    |
| WhatsApp campaign |     358 |          10 |      2.8 | 0.38x    |

**Takeaway:** Referral converts best at 14.8% and WhatsApp campaign worst at 2.8%.

### City tier
|   city_tier |   leads |   activated |   conv % | vs avg   |
|------------:|--------:|------------:|---------:|:---------|
|           1 |    2578 |         221 |      8.6 | 1.16x    |
|           2 |    2422 |         147 |      6.1 | 0.82x    |

**Takeaway:** 1.0 converts best at 8.6% and 2.0 worst at 6.1%.

### Preferred language
| preferred_language   |   leads |   activated |   conv % | vs avg   |
|:---------------------|--------:|------------:|---------:|:---------|
| Bengali              |     111 |          10 |      9   | 1.22x    |
| Malayalam            |      83 |           7 |      8.4 | 1.15x    |
| English              |    1168 |          94 |      8   | 1.09x    |
| Hindi                |    2137 |         169 |      7.9 | 1.07x    |
| Telugu               |     207 |          16 |      7.7 | 1.05x    |
| Marathi              |     505 |          32 |      6.3 | 0.86x    |
| Gujarati             |     233 |          14 |      6   | 0.82x    |
| Kannada              |     253 |          13 |      5.1 | 0.7x     |
| Tamil                |     207 |           9 |      4.3 | 0.59x    |
| Punjabi              |      96 |           4 |      4.2 | 0.57x    |

**Takeaway:** Bengali converts best at 9.0% and Punjabi worst at 4.2%.

### Current internet
| current_internet   |   leads |   activated |   conv % | vs avg   |
|:-------------------|--------:|------------:|---------:|:---------|
| Leased line        |     173 |          26 |     15   | 2.04x    |
| Mixed per site     |     221 |          28 |     12.7 | 1.72x    |
| Business broadband |    1433 |         133 |      9.3 | 1.26x    |
| Home broadband     |    1250 |          95 |      7.6 | 1.03x    |
| Mobile hotspot     |    1799 |          81 |      4.5 | 0.61x    |
| Unknown            |     124 |           5 |      4   | 0.55x    |

**Takeaway:** Leased line converts best at 15.0% and Unknown worst at 4.0%.

### Has GSTIN
| has_gstin   |   leads |   activated |   conv % | vs avg   |
|:------------|--------:|------------:|---------:|:---------|
| Y           |    3534 |         338 |      9.6 | 1.3x     |
| N           |    1466 |          30 |      2   | 0.28x    |

**Takeaway:** Confirmed: 9.6% with a GSTIN vs 2.0% without, a 4.7x gap (README says 9.6% vs 2.0%).

### GSTIN status (registry)
| gst_status   |   leads |   activated |   conv % | vs avg   |
|:-------------|--------:|------------:|---------:|:---------|
| Cancelled    |     167 |          18 |     10.8 | 1.46x    |
| Active       |    3266 |         316 |      9.7 | 1.31x    |
| Suspended    |     101 |           4 |      4   | 0.54x    |
| No GSTIN     |    1466 |          30 |      2   | 0.28x    |

**Takeaway:** Cancelled GSTINs still activated at 10.8%, so today's sellers close deals the catalogue says they shouldn't.

### Has Udyam
| has_udyam   |   leads |   activated |   conv % | vs avg   |
|:------------|--------:|------------:|---------:|:---------|
| Y           |    2723 |         241 |      8.9 | 1.2x     |
| N           |    2277 |         127 |      5.6 | 0.76x    |

**Takeaway:** Y converts best at 8.9% and N worst at 5.6%.

### Turnover band
| annual_turnover_band   |   leads |   activated |   conv % | vs avg   |
|:-----------------------|--------:|------------:|---------:|:---------|
| 5 - 25 cr              |     731 |          95 |     13   | 1.77x    |
| 25 - 100 cr            |     223 |          23 |     10.3 | 1.4x     |
| 1.5 - 5 cr             |    1012 |          84 |      8.3 | 1.13x    |
| 40 lakh - 1.5 cr       |    1537 |         108 |      7   | 0.95x    |
| < 40 lakh              |    1497 |          58 |      3.9 | 0.53x    |

**Takeaway:** 5 - 25 cr converts best at 13.0% and < 40 lakh worst at 3.9%.

### Employees
| employee_bucket   |   leads |   activated |   conv % | vs avg   |
|:------------------|--------:|------------:|---------:|:---------|
| 1-2               |     914 |          41 |      4.5 | 0.61x    |
| 3-5               |    1510 |          71 |      4.7 | 0.64x    |
| 6-10              |     705 |          46 |      6.5 | 0.89x    |
| 11-25             |     934 |         100 |     10.7 | 1.45x    |
| 26+               |     937 |         110 |     11.7 | 1.6x     |

**Takeaway:** Teams of 1-5 convert at 4.6%, teams over 10 at 11.2%: size roughly doubles the odds.

## Q2. Biggest drop stage

### By segment
| segment                     |   leads | -> Contacted   | -> Needs assessed   | -> Quote accepted   | -> KYC complete   | -> Activated   | biggest drop              |
|:----------------------------|--------:|:---------------|:--------------------|:--------------------|:------------------|:---------------|:--------------------------|
| Micro retail & services     |    2709 | 68%            | 54%                 | 32%                 | 54%               | 63%            | Quote accepted (32% pass) |
| Professional offices        |    1247 | 69%            | 62%                 | 53%                 | 74%               | 65%            | Quote accepted (53% pass) |
| Small manufacturers         |     289 | 66%            | 68%                 | 64%                 | 83%               | 54%            | Activated (54% pass)      |
| Small multi-site businesses |     755 | 66%            | 60%                 | 56%                 | 79%               | 62%            | Quote accepted (56% pass) |

**Takeaway:** the quote step is the biggest drop for 3 of 4 segment groups.

### By lead source
| lead_source       |   leads | -> Contacted   | -> Needs assessed   | -> Quote accepted   | -> KYC complete   | -> Activated   | biggest drop              |
|:------------------|--------:|:---------------|:--------------------|:--------------------|:------------------|:---------------|:--------------------------|
| Channel partner   |    1010 | 71%            | 57%                 | 48%                 | 65%               | 63%            | Quote accepted (48% pass) |
| Field sales       |    1720 | 73%            | 61%                 | 41%                 | 67%               | 58%            | Quote accepted (41% pass) |
| Inbound call      |     504 | 80%            | 55%                 | 45%                 | 78%               | 62%            | Quote accepted (45% pass) |
| Referral          |     413 | 79%            | 71%                 | 48%                 | 71%               | 77%            | Quote accepted (48% pass) |
| Website form      |     995 | 55%            | 50%                 | 43%                 | 63%               | 58%            | Quote accepted (43% pass) |
| WhatsApp campaign |     358 | 41%            | 45%                 | 27%                 | 83%               | 67%            | Quote accepted (27% pass) |

**Takeaway:** the quote step is the biggest drop for 6 of 6 lead source groups.

Also: micro businesses pass the quote step only 32% of the time, and WhatsApp-campaign and website-form leads are contacted only 41% and 55% of the time (vs 68% overall).

## Q3. Drop reasons and what a digital journey fixes

| bucket              | drop_reason                         | fixable   | how                                              |   drops |   % of drops |
|:--------------------|:------------------------------------|:----------|:-------------------------------------------------|--------:|-------------:|
| Other               | Not interested on first call        | No        |                                                  |     470 |         10.1 |
| Other               | Locked in with current provider     | No        |                                                  |     325 |          7   |
| Other               | Wrong or invalid number             | No        |                                                  |     319 |          6.9 |
| Other               | Decided to wait                     | No        |                                                  |     107 |          2.3 |
| Other               | Customer cancelled before install   | Partly    | tracker reduces anxiety                          |      53 |          1.1 |
| Other               | Site not feasible for fibre         | Yes       | advisor offers 5G AirFiber                       |      41 |          0.9 |
| Other               | First payment failed                | Yes       | in-app retry/UPI                                 |      28 |          0.6 |
| Paperwork           | Missing GST or Udyam document       | Yes       | registry lookup pre-fills it                     |      94 |          2   |
| Paperwork           | Found paperwork too long            | Yes       | lookup + OCR                                     |      79 |          1.7 |
| Paperwork           | Authorised signatory not available  | Partly    | remote e-sign                                    |      53 |          1.1 |
| Paperwork           | Document details did not match      | Yes       | mismatch caught at upload                        |      47 |          1   |
| Reach/speed         | Unreachable after 3 attempts        | Partly    | owner starts the chat, but some never engage     |     805 |         17.4 |
| Reach/speed         | Owner had no time for a visit       | Yes       | self-serve, no visit needed                      |     531 |         11.5 |
| Reach/speed         | Visit not scheduled by sales        | Yes       | no visit needed                                  |     296 |          6.4 |
| Reach/speed         | Quote took too long to arrive       | Yes       | instant quote                                    |     179 |          3.9 |
| Reach/speed         | Installation delayed beyond 21 days | Partly    | tracker + escalation, install itself is physical |      98 |          2.1 |
| Understanding/price | Price too high                      | Partly    | right-sized bundle, add-on toggles               |     414 |          8.9 |
| Understanding/price | Only wanted a mobile plan           | Partly    | advisor can sell a mobile-only plan              |     280 |          6   |
| Understanding/price | Competitor offered cheaper plan     | No        |                                                  |     207 |          4.5 |
| Understanding/price | Quote too complex to understand     | Yes       | plain-language quote                             |     206 |          4.4 |

### By bucket
| bucket              |   drops |   fixable_yes |   fixable_partly |   % of all drops | digital journey fixes   |
|:--------------------|--------:|--------------:|-----------------:|-----------------:|:------------------------|
| Reach/speed         |    1909 |          1006 |              903 |             41.2 | Mostly                  |
| Other               |    1343 |            69 |               53 |             29   | Mostly not              |
| Understanding/price |    1107 |           206 |              694 |             23.9 | Partly                  |
| Paperwork           |     273 |           220 |               53 |              5.9 | Mostly                  |

**Takeaway:** reach/speed is the biggest bucket at 41.2% of drops; a digital journey fully fixes 32% of all drops and partly fixes another 37%.

## Q4. Activated customers: speed, chasing, churn and NPS

### By segment
| segment                     |   customers |   avg_days |   avg_chase_calls | churn_6m   |   avg_nps |
|:----------------------------|------------:|-----------:|------------------:|:-----------|----------:|
| Micro retail & services     |         110 |      16.65 |              3.16 | 22.7%      |      7.05 |
| Professional offices        |         138 |      16.92 |              3.07 | 13.8%      |      6.92 |
| Small manufacturers         |          37 |      20.51 |              2.86 | 8.1%       |      6.46 |
| Small multi-site businesses |          83 |      18.77 |              2.78 | 10.8%      |      6.7  |

**Takeaway:** micro customers churn most (23%) while manufacturers take longest to activate (20.5 days).

### By bundle size (number of distinct products)
| bundle_size   |   customers |   avg_days |   avg_chase_calls | churn_6m   |   avg_nps |
|:--------------|------------:|-----------:|------------------:|:-----------|----------:|
| 2             |          25 |      17.12 |              3.24 | 24.0%      |      6.64 |
| 3             |          66 |      17.44 |              2.91 | 13.6%      |      7.05 |
| 4             |         107 |      17.55 |              2.97 | 15.9%      |      7.07 |
| 5             |          88 |      17.52 |              2.99 | 13.6%      |      6.77 |
| 6             |          48 |      18.17 |              3.12 | 10.4%      |      6.67 |
| 7+            |          34 |      18    |              3.06 | 20.6%      |      6.5  |

**Takeaway:** 2-product bundles churn at 24% vs 14% for 3-6 products, so a thin bundle is a weak bundle.

### Do more chase calls predict churn or low NPS?
| calls   |   customers | churn_6m   |   avg_nps |   avg_days |
|:--------|------------:|:-----------|----------:|-----------:|
| 1       |          34 | 5.9%       |      7.47 |      17.32 |
| 2       |          84 | 14.3%      |      7.19 |      17.88 |
| 3       |         137 | 11.7%      |      6.89 |      17.47 |
| 4       |          70 | 20.0%      |      6.66 |      17.57 |
| 5+      |          43 | 27.9%      |      5.98 |      17.88 |

Correlations: calls vs churn +0.14, calls vs NPS -0.24, calls vs days +0.01, days vs NPS -0.28.

**Takeaway:** yes. Churn climbs from 6% at 1 call to 28% at 5+ calls and NPS drops from 7.5 to 6.0; calls aren't explained by slow activation (r=+0.01), so it's the uncertainty, not the wait, that hurts.

## Q5. Most common bundles and what gets bought together

### Micro retail & services (110 activated, 30 distinct bundles)
| combo           | products                                                                                   |   buys |   median_monthly |   median_contract | churn   |
|:----------------|:-------------------------------------------------------------------------------------------|-------:|-----------------:|------------------:|:--------|
| P01+P07         | Biz Fibre 100, Business Postpaid 299                                                       |     21 |             1520 |                12 | 19%     |
| P01+P07+P19     | Biz Fibre 100, Business Postpaid 299, Cloud POS & Billing                                  |     10 |             2515 |                12 | 20%     |
| P01+P07+P23     | Biz Fibre 100, Business Postpaid 299, Cloud CCTV                                           |      9 |             2170 |                12 | 11%     |
| P01+P07+P22     | Biz Fibre 100, Business Postpaid 299, Secure Wi-Fi with Guest Network                      |      8 |             2100 |                12 | 25%     |
| P01+P07+P19+P22 | Biz Fibre 100, Business Postpaid 299, Cloud POS & Billing, Secure Wi-Fi with Guest Network |      7 |             2930 |                12 | 14%     |

### Professional offices (138 activated, 96 distinct bundles)
| combo               | products                                                                                               |   buys |   median_monthly |   median_contract | churn   |
|:--------------------|:-------------------------------------------------------------------------------------------------------|-------:|-----------------:|------------------:|:--------|
| P02+P07+P16+P17+P20 | Biz Fibre 300, Business Postpaid 299, Cloud Email & Office Suite, Cloud Backup 1 TB, Endpoint Security |      5 |             5280 |                12 | 20%     |
| P02+P07+P16         | Biz Fibre 300, Business Postpaid 299, Cloud Email & Office Suite                                       |      5 |             3460 |                12 | 0%      |
| P02+P07+P16+P17     | Biz Fibre 300, Business Postpaid 299, Cloud Email & Office Suite, Cloud Backup 1 TB                    |      5 |             4750 |                12 | 0%      |
| P01+P08+P16         | Biz Fibre 100, Business Postpaid 599, Cloud Email & Office Suite                                       |      3 |             4230 |                12 | 33%     |
| P02+P07+P14+P16     | Biz Fibre 300, Business Postpaid 299, Business SMS 10k, Cloud Email & Office Suite                     |      3 |             5300 |                12 | 0%      |

### Small manufacturers (37 activated, 31 distinct bundles)
| combo               | products                                                                                                 |   buys |   median_monthly |   median_contract | churn   |
|:--------------------|:---------------------------------------------------------------------------------------------------------|-------:|-----------------:|------------------:|:--------|
| P03+P08+P16         | Biz Fibre 1G, Business Postpaid 599, Cloud Email & Office Suite                                          |      2 |             7420 |                12 | 0%      |
| P05+P08+P11+P16+P20 | Internet Leased Line 20, Business Postpaid 599, Static IP, Cloud Email & Office Suite, Endpoint Security |      2 |            16265 |                12 | 0%      |
| P03+P08+P16+P21+P23 | Biz Fibre 1G, Business Postpaid 599, Cloud Email & Office Suite, Managed Firewall, Cloud CCTV            |      2 |            12010 |                24 | 0%      |
| P05+P08+P16         | Internet Leased Line 20, Business Postpaid 599, Cloud Email & Office Suite                               |      2 |            12985 |                12 | 50%     |
| P05+P08+P16+P23     | Internet Leased Line 20, Business Postpaid 599, Cloud Email & Office Suite, Cloud CCTV                   |      2 |            15440 |                12 | 0%      |

### Small multi-site businesses (83 activated, 73 distinct bundles)
| combo                       | products                                                                                                                                      |   buys |   median_monthly |   median_contract | churn   |
|:----------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------|-------:|-----------------:|------------------:|:--------|
| P01+P08+P09+P10+P19         | Biz Fibre 100, Business Postpaid 599, Backup 4G/5G Failover, Managed SD-WAN, Cloud POS & Billing                                              |      2 |            40470 |                24 | 0%      |
| P02+P08+P09+P10+P19+P22+P23 | Biz Fibre 300, Business Postpaid 599, Backup 4G/5G Failover, Managed SD-WAN, Cloud POS & Billing, Secure Wi-Fi with Guest Network, Cloud CCTV |      2 |            58785 |                24 | 0%      |
| P02+P08+P09+P10+P19+P23     | Biz Fibre 300, Business Postpaid 599, Backup 4G/5G Failover, Managed SD-WAN, Cloud POS & Billing, Cloud CCTV                                  |      2 |            38235 |                24 | 0%      |
| P02+P08+P09+P19+P22+P23     | Biz Fibre 300, Business Postpaid 599, Backup 4G/5G Failover, Cloud POS & Billing, Secure Wi-Fi with Guest Network, Cloud CCTV                 |      2 |            34110 |                12 | 50%     |
| P02+P08+P10+P15+P23         | Biz Fibre 300, Business Postpaid 599, Managed SD-WAN, WhatsApp Business API Starter, Cloud CCTV                                               |      2 |            28815 |                24 | 0%      |

**Takeaway:** only micro has a clear default (P01+P07, 21 of 110 buys); other segments buy near-unique bundles, which is exactly why a conversational advisor beats a fixed menu.

### Products bought together (pairs in 10+ baskets, ranked by lift)
| pair    | products                                           |   together |   support % |   lift |
|:--------|:---------------------------------------------------|-----------:|------------:|-------:|
| P12+P14 | Cloud Telephony / SIP + Business SMS 10k           |         14 |         3.8 |   5.02 |
| P10+P13 | Managed SD-WAN + Toll-free Number                  |         12 |         3.3 |   4.15 |
| P03+P11 | Biz Fibre 1G + Static IP                           |         20 |         5.4 |   2.95 |
| P14+P17 | Business SMS 10k + Cloud Backup 1 TB               |         12 |         3.3 |   2.92 |
| P11+P20 | Static IP + Endpoint Security                      |         31 |         8.4 |   2.81 |
| P14+P20 | Business SMS 10k + Endpoint Security               |         17 |         4.6 |   2.79 |
| P03+P12 | Biz Fibre 1G + Cloud Telephony / SIP               |         14 |         3.8 |   2.66 |
| P13+P22 | Toll-free Number + Secure Wi-Fi with Guest Network |         12 |         3.3 |   2.54 |
| P17+P20 | Cloud Backup 1 TB + Endpoint Security              |         32 |         8.7 |   2.53 |
| P09+P13 | Backup 4G/5G Failover + Toll-free Number           |         15 |         4.1 |   2.46 |
| P13+P19 | Toll-free Number + Cloud POS & Billing             |         15 |         4.1 |   2.46 |
| P13+P23 | Toll-free Number + Cloud CCTV                      |         15 |         4.1 |   2.35 |

### Most frequent pairs
| pair    | products                                           |   together |   support % |   lift |
|:--------|:---------------------------------------------------|-----------:|------------:|-------:|
| P01+P07 | Biz Fibre 100 + Business Postpaid 299              |        116 |        31.5 |   1.35 |
| P08+P16 | Business Postpaid 599 + Cloud Email & Office Suite |        109 |        29.6 |   1.19 |
| P16+P20 | Cloud Email & Office Suite + Endpoint Security     |         83 |        22.6 |   2.1  |
| P02+P08 | Biz Fibre 300 + Business Postpaid 599              |         69 |        18.8 |   1.31 |
| P07+P16 | Business Postpaid 299 + Cloud Email & Office Suite |         66 |        17.9 |   0.79 |
| P01+P08 | Biz Fibre 100 + Business Postpaid 599              |         64 |        17.4 |   0.68 |
| P08+P09 | Business Postpaid 599 + Backup 4G/5G Failover      |         64 |        17.4 |   1.53 |
| P02+P16 | Biz Fibre 300 + Cloud Email & Office Suite         |         61 |        16.6 |   1.27 |

**Takeaway:** the strongest attachment is Cloud Telephony / SIP + Business SMS 10k (lift 5.02); fibre + a business SIM is the base almost every bundle grows from, so the advisor should lead with connectivity and attach from there.

## Q6. Acquisition cost vs conversion by lead source

| lead_source       |   leads |   activated |   cost_per_lead |   conv % |   cost per activation |
|:------------------|--------:|------------:|----------------:|---------:|----------------------:|
| WhatsApp campaign |     358 |          10 |             112 |        3 |                  4026 |
| Referral          |     413 |          61 |             605 |       15 |                  4099 |
| Inbound call      |     504 |          48 |             487 |       10 |                  5113 |
| Website form      |     995 |          43 |             274 |        4 |                  6352 |
| Channel partner   |    1010 |          81 |            1672 |        8 |                 20851 |
| Field sales       |    1720 |         125 |            1769 |        7 |                 24335 |

Blended: Rs 15,053 per activation.

**Takeaway:** the cheapest per activation is WhatsApp campaign (Rs 4,026) but it barely converts; Referral is the real winner at 14.8% conversion and Rs 4,099, while Field sales costs Rs 24,335, 6x more.

## Q7. Things that look deliberately planted

### 1. Mis-selling: 56 of 368 activated customers (15%) were sold something the catalogue says they can't have
| rule                            |   customers |
|:--------------------------------|------------:|
| sold outside its city tier      |          24 |
| GSTIN product with no gstin     |          11 |
| missing a required base product |           9 |
| below min employees             |           8 |
| GSTIN product with cancelled    |           7 |
| GSTIN product with suspended    |           3 |

### 2. Languages: Tamil, Punjabi and Kannada lag
| preferred_language   |   leads |   activated |   conv % | vs avg   |
|:---------------------|--------:|------------:|---------:|:---------|
| Bengali              |     111 |          10 |      9   | 1.22x    |
| Malayalam            |      83 |           7 |      8.4 | 1.15x    |
| English              |    1168 |          94 |      8   | 1.09x    |
| Hindi                |    2137 |         169 |      7.9 | 1.07x    |
| Telugu               |     207 |          16 |      7.7 | 1.05x    |
| Marathi              |     505 |          32 |      6.3 | 0.86x    |
| Gujarati             |     233 |          14 |      6   | 0.82x    |
| Kannada              |     253 |          13 |      5.1 | 0.7x     |
| Tamil                |     207 |           9 |      4.3 | 0.59x    |
| Punjabi              |      96 |           4 |      4.2 | 0.57x    |

Regional-language leads accept the quote 40% of the time vs 45% for Hindi/English.

### 3. Cities: spread is wide (n >= 150)
| city      |   leads |   activated |   conv % | vs avg   |
|:----------|--------:|------------:|---------:|:---------|
| Delhi     |     445 |          45 |     10.1 | 1.37x    |
| Ahmedabad |     188 |          18 |      9.6 | 1.3x     |
| Kochi     |     191 |          18 |      9.4 | 1.28x    |
| Kolkata   |     233 |          21 |      9   | 1.22x    |
| Indore    |     180 |           9 |      5   | 0.68x    |
| Mysuru    |     169 |           8 |      4.7 | 0.64x    |
| Lucknow   |     178 |           8 |      4.5 | 0.61x    |
| Vadodara  |     196 |           8 |      4.1 | 0.55x    |

### 4. Digital leads go unanswered
| lead_source       |   % of drops unreachable or wrong number |
|:------------------|-----------------------------------------:|
| WhatsApp campaign |                                     44   |
| Website form      |                                     33.7 |
| Channel partner   |                                     21.9 |
| Field sales       |                                     19.9 |
| Referral          |                                     16.2 |
| Inbound call      |                                     16   |

### 5. Mobile-hotspot shops convert at half the average
4.5% vs 7.4% overall; these are the micro shops the case calls very price-sensitive.

### 6. Registry name format
Every proprietorship's legal_name is 'Owner (Prop. Trade name)'. Match KYC names on trade_name, or about 2,443 honest applicants get flagged.

### 7. Catalogue trap
Static IP (P11) needs Biz Fibre (P01-P03), not a leased line, even though leased-line customers are the ones most likely to want a static IP.

### 8. Stage timing for activated customers (median days)
- created -> contacted: 2 days
- contacted -> needs_assessed: 3 days
- needs_assessed -> quote_accepted: 4 days
- quote_accepted -> kyc_complete: 4 days
- kyc_complete -> activated: 4 days

On average 9.0 of the 17.6 days pass before the quote is even accepted; a one-sitting advisor removes most of that.