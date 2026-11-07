# Data profile

## smb_leads: 5,000 rows x 40 cols
| column | dtype | nulls |
|---|---|---|
| lead_id | string | 0 |
| created_date | datetime64[us] | 0 |
| lead_source | category | 0 |
| business_name | string | 0 |
| business_type | category | 0 |
| segment | category | 0 |
| city | category | 0 |
| city_tier | Int8 | 0 |
| state | category | 0 |
| preferred_language | category | 0 |
| employee_count | Int32 | 0 |
| num_sites | Int16 | 0 |
| annual_turnover_band | category | 0 |
| has_gstin | category | 0 |
| gstin | string | 1466 |
| has_udyam | category | 0 |
| udyam_number | string | 2277 |
| current_internet | category | 124 |
| current_provider | category | 124 |
| monthly_telecom_spend_inr | Float64 | 0 |
| products_of_interest | string | 0 |
| contact_name | string | 0 |
| contact_role | category | 0 |
| stage_reached | category | 0 |
| outcome | category | 0 |
| drop_reason | category | 368 |
| contacted_date | datetime64[us] | 1594 |
| needs_assessed_date | datetime64[us] | 3026 |
| quote_accepted_date | datetime64[us] | 4139 |
| kyc_complete_date | datetime64[us] | 4412 |
| activated_date | datetime64[us] | 4632 |
| days_lead_to_activation | Float64 | 4632 |
| customer_follow_up_calls | Int16 | 0 |
| bundle_products | string | 4632 |
| monthly_bundle_value_inr | Float64 | 4632 |
| one_time_setup_inr | Float64 | 4632 |
| contract_months | Float64 | 4632 |
| churned_within_6_months | category | 4632 |
| nps_score | Float64 | 4632 |
| acquisition_cost_inr | Float64 | 0 |

Duplicate rows: 0

## product_catalogue: 25 rows x 16 cols
| column | dtype | nulls |
|---|---|---|
| product_id | string | 0 |
| category | category | 0 |
| product_name | string | 0 |
| description | string | 0 |
| unit | category | 0 |
| price_min_inr_per_month | Int32 | 0 |
| price_max_inr_per_month | Int32 | 0 |
| one_time_setup_inr | Int32 | 0 |
| min_contract_months | Int16 | 0 |
| available_city_tiers | string | 0 |
| min_employees | Int16 | 0 |
| min_sites | Int16 | 0 |
| requires_gstin | category | 0 |
| requires_one_of | string | 18 |
| typical_install_days | Int16 | 0 |
| target_segments | string | 0 |

Duplicate rows: 0

## gstin_registry: 3,534 rows x 8 cols
| column | dtype | nulls |
|---|---|---|
| gstin | string | 0 |
| legal_name | string | 0 |
| trade_name | string | 0 |
| constitution | category | 0 |
| principal_place_of_business | string | 0 |
| state | category | 0 |
| registration_date | datetime64[us] | 0 |
| status | category | 0 |

Duplicate rows: 0

## udyam_registry: 2,723 rows x 8 cols
| column | dtype | nulls |
|---|---|---|
| udyam_number | string | 0 |
| enterprise_name | string | 0 |
| enterprise_type | category | 0 |
| major_activity | category | 0 |
| nic_description | string | 0 |
| state | category | 0 |
| city | category | 0 |
| date_of_registration | datetime64[us] | 0 |

Duplicate rows: 0

## Consistency checks
| check | rows |
|---|---|
| has_gstin=Y but gstin blank | 0 |
| has_gstin=N but gstin present | 0 |
| has_udyam=Y but udyam blank | 0 |
| has_udyam=N but udyam present | 0 |
| gstin not 15 chars | 0 |
| udyam not UDYAM-XX-00-NNNNNNN | 0 |
| city_tier not 1 or 2 | 0 |
| employee_count < 1 | 0 |
| num_sites < 1 | 0 |
| negative telecom spend | 0 |
| negative acquisition cost | 0 |
| nps outside 0-10 | 0 |
| stage_reached not a known stage | 0 |
| Activated without activated_date | 0 |
| Activated with a drop_reason | 0 |
| Dropped without drop_reason | 0 |
| Dropped with activation fields filled | 0 |
| Activated without bundle | 0 |
| products_of_interest has unknown product | 0 |
| bundle has unknown product | 0 |
| bundle qty < 1 | 0 |
| days_lead_to_activation != activated - created | 0 |
| contacted_date before created_date | 0 |
| reached Contacted but contacted_date blank | 0 |
| contacted_date filled but stage not reached | 0 |
| needs_assessed_date before contacted_date | 0 |
| reached Needs assessed but needs_assessed_date blank | 0 |
| needs_assessed_date filled but stage not reached | 0 |
| quote_accepted_date before needs_assessed_date | 0 |
| reached Quote accepted but quote_accepted_date blank | 0 |
| quote_accepted_date filled but stage not reached | 0 |
| kyc_complete_date before quote_accepted_date | 0 |
| reached KYC complete but kyc_complete_date blank | 0 |
| kyc_complete_date filled but stage not reached | 0 |
| activated_date before kyc_complete_date | 0 |
| reached Activated but activated_date blank | 0 |
| activated_date filled but stage not reached | 0 |
| catalogue: price_min > price_max | 0 |
| catalogue: requires_one_of points to unknown product | 0 |

- created_date range: 2026-04-01 to 2026-06-30
- employee_count 1-150, num_sites 1-12, spend Rs 200-27,750
- outcome: {'Dropped': 4632, 'Activated': 368}
- leads with current_internet blank: 124 (treat as Unknown)

## Funnel (leads that reached at least this stage)
| stage | leads | expected | % of previous | match |
|---|---|---|---|---|
| Lead | 5,000 | 5,000 | - | OK |
| Contacted | 3,406 | 3,406 | 68% | OK |
| Needs assessed | 1,974 | 1,974 | 58% | OK |
| Quote accepted | 861 | 861 | 44% | OK |
| KYC complete | 588 | 588 | 68% | OK |
| Activated | 368 | 368 | 63% | OK |

**Funnel matches README: YES**

## Leads -> GSTIN registry
- Leads with a GSTIN: 3,534; found in registry: 3,534; not found: 0
- Registry status: Active 3,266, Cancelled 167, Suspended 101
- business_name differs from legal_name: 2,443 (of which 2,443 are proprietorships stored as 'Owner (Prop. Trade name)')
- business_name differs from trade_name: 0
- Lead state differs from registry state: 0
- GSTIN state code vs registry state: first 2 digits checked against state below
  state codes mapping to more than one state: 0
- Activated leads with Cancelled/Suspended GSTIN: 22
- Constitution: {'Proprietorship': 2443, 'Private Limited Company': 631, 'Limited Liability Partnership': 460}

## Leads -> Udyam registry
- Leads with a Udyam number: 2,723; found in registry: 2,723; not found: 0
- business_name differs from enterprise_name: 0
- city differs: 0, state differs: 0
- enterprise_type: {'Micro': 1833, 'Small': 737, 'Medium': 153}
- Leads with Udyam but no GSTIN: 636

## Registry coverage
- GSTIN registry rows not linked to any lead: 0
- Udyam registry rows not linked to any lead: 0

## Flags
- Nothing odd found. All consistency checks returned 0.

## Saved
- data/clean/leads.parquet (5,000), lead_interest.parquet (9,971 lead-product rows), lead_bundle_items.parquet (1,651 lead-product-qty rows), catalogue.parquet, gstin.parquet, udyam.parquet