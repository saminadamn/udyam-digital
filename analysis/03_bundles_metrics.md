# Bundles and metrics

## Mis-sold bundles (break a catalogue rule) vs clean bundles
| mis_sold   |   n |   churn |   nps |   calls |   days |
|:-----------|----:|--------:|------:|--------:|-------:|
| False      | 312 |    0.16 |  6.86 |    3.03 |  17.27 |
| True       |  56 |    0.09 |  6.89 |    2.89 |  19.54 |

Mis-sold by source: {'Field sales': 19, 'Channel partner': 12, 'Referral': 10, 'Website form': 7, 'Inbound call': 6, 'WhatsApp campaign': 2}
Mis-sold share by source: {'Channel partner': 14.8, 'Field sales': 15.2, 'Inbound call': 12.5, 'Referral': 16.4, 'Website form': 16.3, 'WhatsApp campaign': 20.0}

## Segment ranking (score = base share x conversion x median value / churn)
| segment                     |   base_share |   conv_pct |   median_value |   churn_6m_pct |   cac_per_activation |   payback_months |   yr1_value_per_lead |   score |
|:----------------------------|-------------:|-----------:|---------------:|---------------:|---------------------:|-----------------:|---------------------:|--------:|
| Small multi-site businesses |         0.15 |       11   |          28080 |           10.8 |                15614 |              0.6 |                33026 |    42.7 |
| Professional offices        |         0.25 |       11.1 |           6575 |           13.8 |                10694 |              1.6 |                 7529 |    13.2 |
| Small manufacturers         |         0.05 |       12.8 |          15910 |            8.1 |                15324 |              1   |                22461 |    12.6 |
| Micro retail & services     |         0.55 |        4.1 |           2470 |           22.7 |                20007 |              8.1 |                  930 |     2.4 |

## Recommended starter bundles (priced: micro at catalogue min, others at mid of range)
### micro: Dukaan Digital (kirana/salon, 3 staff, 1 site, tier 2, no GSTIN)
- Core: P01 Biz Fibre 100 x1, P07 Business Postpaid 299 x1
- Core price: Rs 1,298/month, setup Rs 0, contract 12 months. Rule check: PASS
- Add-ons: P19 Cloud POS & Billing x1, P23 Cloud CCTV x2, P22 Secure Wi-Fi with Guest Network x1
- With all add-ons: Rs 2,694/month, setup Rs 7,100, contract 12 months. Rule check: PASS
- Median actually paid by this segment today: Rs 2,470/month

### prof: Clinic/CA Office Pro (6 staff, 1 site, tier 1, active GSTIN)
- Core: P02 Biz Fibre 300 x1, P07 Business Postpaid 299 x2, P16 Cloud Email & Office Suite x6, P17 Cloud Backup 1 TB x1
- Core price: Rs 3,774/month, setup Rs 0, contract 12 months. Rule check: PASS
- Add-ons: P20 Endpoint Security x6, P12 Cloud Telephony / SIP x2, P09 Backup 4G/5G Failover x1
- With all add-ons: Rs 7,567/month, setup Rs 5,500, contract 12 months. Rule check: PASS
- Median actually paid by this segment today: Rs 6,575/month

### multi: Chain Connect (4 outlets, 24 staff, tier 1, active GSTIN)
- Core: P02 Biz Fibre 300 x4, P09 Backup 4G/5G Failover x4, P08 Business Postpaid 599 x4, P23 Cloud CCTV x8
- Core price: Rs 13,580/month, setup Rs 20,400, contract 12 months. Rule check: PASS
- Add-ons: P10 Managed SD-WAN x4, P19 Cloud POS & Billing x4, P15 WhatsApp Business API Starter x1, P13 Toll-free Number x1
- With all add-ons: Rs 31,575/month, setup Rs 51,400, contract 24 months. Rule check: PASS
- Median actually paid by this segment today: Rs 28,080/month

### mfg: Factory Line (30 staff, 1 site, tier 2, active GSTIN)
- Core: P05 Internet Leased Line 20 x1, P08 Business Postpaid 599 x3, P16 Cloud Email & Office Suite x10, P20 Endpoint Security x10
- Core price: Rs 14,717/month, setup Rs 10,000, contract 12 months. Rule check: PASS
- Add-ons: P24 Machine Monitoring IoT x5, P21 Managed Firewall x1, P23 Cloud CCTV x4
- With all add-ons: Rs 19,207/month, setup Rs 36,200, contract 24 months. Rule check: PASS
- Median actually paid by this segment today: Rs 15,910/month

## Negative rule tests (must fail)
- WhatsApp API without GSTIN: FAILS as expected -> ['P15: needs an active GSTIN']
- Fibre 1G in tier 2: FAILS as expected -> ['P03: not sold in tier 2']
- CCTV with no connection: FAILS as expected -> ['P23: needs one of P01|P02|P03|P04|P05|P06']
- SD-WAN for 2 sites: FAILS as expected -> ['P10: needs 3+ sites']
- Leased line with cancelled GSTIN: FAILS as expected -> ['P05: needs an active GSTIN']

## Baselines
- Lead-to-activation conversion: 7.4%
- Quote acceptance (needs assessed -> quote accepted): 44%
- Days from lead to activation: 17.6
- CAC per activation: Rs 15,053
- 6-month churn: 15.2%
- Status-chase calls per customer: 3.0
- Bundles sold that break a catalogue rule: 15%