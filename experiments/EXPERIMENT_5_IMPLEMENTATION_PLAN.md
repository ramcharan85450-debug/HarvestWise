# Experiment 5 — Implementation Plan

**Status: PRE-REGISTERED PLAN. Written at Checkpoint 1, before any source was accessed, any data collected, or any model run.**

Repository state at plan time: branch `main`, HEAD `d55e59f` (Experiment 4), 0 modified tracked files, Experiments 1–4 verified unchanged by re-execution (field-level 21 examples, Experiment 1 district dataset 561 aligned).

---

# 1. Research question

> Does historically appropriate district-level irrigation explain a meaningful additional portion of the residual cross-regional agricultural difference that remained after Experiment 4?

The primary question is **explanatory**, not predictive. Whether irrigation improves machine-learning accuracy is a **secondary** outcome and cannot override the primary classification.

# 2. Pre-registered hypotheses

**H5 (alternative).** Historically appropriate district-level irrigation availability explains a statistically meaningful additional portion of the residual cross-regional agricultural difference remaining after controlling for the credible agricultural covariates identified in Experiment 4.

**H0 (null).** Adding district-level irrigation variables does not materially reduce the residual regional coefficient beyond the Experiment 4 covariates.

These are fixed. They will not be revised after Model C is estimated.

# 3. Background this experiment must reproduce exactly

Read from `experiments/experiment4_results.json`, not assumed:

| Quantity | Experiment 4 value |
|---|---|
| Model A region coefficient (β_A) | **+0.825**, 95% CI [0.666, 0.984], R² 0.216 |
| Model B region coefficient (β_B) | **+0.565**, 95% CI [0.364, 0.765], R² 0.282 |
| Gap accounted for by Model B | **31.56%** |
| Estimation sample | Kharif, 2000–2012, **n = 382** (TN 143 / AP+TG 239), 32 districts |
| Model B covariates | `non_rice_cropped_area_ha`, `n_crops_grown`, `elevation_m_mean`, `slope_deg_mean` |
| Excluded — region proxy | `n_rice_seasons` (KS 0.996, zero within-TN variance; a source reporting convention, not agronomy) |
| Excluded — target-denominator overlap | `gross_cropped_area_ha`, `rice_area_share` |
| Region variable | binary `is_tn` (Tamil Nadu = 1; Andhra Pradesh + Telangana = 0) |
| Estimator | OLS with intercept; SEs from residual variance; 95% CI via t-distribution |

# 4. Data requirements

Every irrigation observation must be:

1. **District-level** — never a state or national value, never a neighbouring district substituted.
2. **Historically appropriate to 2000–2012** — no modern data projected backwards, no future observations.
3. **Traceable** — publisher, report, table, year, page/URL, retrieval date, unit.
4. **Definition-documented** — the source's own definition of net/gross irrigated area recorded verbatim where available.

Every value carries an explicit status from: `OBSERVED`, `NOT_AVAILABLE`, `YEAR_NOT_COVERED`, `UNMAPPABLE`, `SOURCE_UNREADABLE`, `SOURCE_ACCESS_FAILED`, `AMBIGUOUS`.

# 5. Geographic strategy

Exactly the 32 districts already in the Experiment 4 estimation subset. No districts added to inflate sample size; none removed for weakening results.

- **Tamil Nadu (12):** Ariyalur, Coimbatore, Cuddalore, Dharmapuri, Dindigul, Erode, Kancheepuram, Kanniyakumari, Karur, Krishnagiri, Madurai, Nagapattinam
- **Andhra Pradesh (10):** Anantapur, Chittoor, East Godavari, Guntur, Krishna, Kurnool, Prakasam, Srikakulam, Vizianagaram, West Godavari
- **Telangana (10):** Adilabad, Hyderabad, Karimnagar, Khammam, Mahbubnagar, Medak, Nalgonda, Nizamabad, Rangareddi, Warangal

**Historical-geography hazard, flagged in advance.** Telangana was formed in 2014. For 2000–2011 these ten districts were part of **undivided Andhra Pradesh**, and every historical source will file them under Andhra Pradesh. Experiment 5 will therefore treat "state as printed in the historical source" and "HarvestWise study region" as two separate fields, and will not apply modern Telangana boundaries to historical records without documenting it. This mirrors the constraint already respected in this project's Telangana yield collection.

# 6. Candidate sources (to be assessed at Checkpoint 2 — none accessed yet)

| Candidate | Why plausible | Known concern to test |
|---|---|---|
| ICRISAT **District Level Database** (apps.icrisat.org) | District-level, 1966–2015, carries net/gross irrigated area and source-wise irrigation for Indian districts | Publishes values **apportioned to a fixed historical district base**. That is a documented redistribution. It may conflict with this experiment's rule against redistributing historical values — a decision to raise explicitly, not resolve silently |
| **Tamil Nadu DES** — Season and Crop Report / Agricultural Statistics | The state's own primary statistical publication; district irrigation tables | Availability of 2000–2012 volumes; PDF table extraction quality |
| **Andhra Pradesh DES** — Statistical Abstract / Agricultural Statistics | Primary source for undivided AP, covering both AP and present-day Telangana districts | Same; plus historical district naming |
| **Minor Irrigation Census** (Ministry of Jal Shakti) | Independent cross-check; source composition (canal/tank/well) | Census years only (e.g. 2000-01, 2006-07). **No interpolation between census years** |
| **India-WRIS** | Water resources portal | Geographic level and period must be verified |
| data.gov.in | Already partly explored | Experiment 4 found 12/13 irrigation datasets state-level; the one district-level candidate (`9678fb5e`) returned **HTTP 502** on three attempts and covers 2016-17 — temporally inappropriate regardless |

Sources will be classified `ACCEPTABLE` / `POSSIBLY_ACCEPTABLE` / `REJECTED` / `ACCESS_FAILED` / `INSUFFICIENT_COVERAGE`, with every rejection explained. **A source will not be chosen because it produces a preferred result.**

# 7. Planned irrigation features

Created only where the source definition supports them:

| Feature | Definition | Precondition |
|---|---|---|
| `net_irrigated_area` | As defined by the source, recorded verbatim | Unit stated or independently corroborated |
| `gross_irrigated_area` | As defined by the source | Same |
| `irrigation_intensity` | `gross_irrigated_area / net_irrigated_area` | Both valid, same district, same year, same source |
| `irrigated_fraction` | `net_irrigated_area / comparable_cultivated_area` | Same district, same period, comparable definitions, compatible units |
| `irrigation_source_composition` | Canal / tank / tube well / other wells / other, kept **separate** | Categories not collapsed without stated justification |

**Pre-registered primary irrigation variable:** `irrigated_fraction` if obtainable, else `net_irrigated_area`. Choosing among definitions *after* seeing Model C would be specification search; the fallback order is fixed here.

**Denominator-overlap check.** `irrigated_fraction` uses a cultivated-area denominator. The target is rice yield = rice production / **rice area**. If the only available denominator is rice area itself, the feature shares a term with the target and will be **barred from models** exactly as `rice_area_share` was in Experiment 4. A non-rice or all-crop cultivated-area denominator avoids this.

# 8. Primary models

All three fitted by the same estimator as Experiment 4 (OLS, intercept, t-based 95% CI).

```
Model A:  yield ~ is_tn
Model B:  yield ~ is_tn + non_rice_cropped_area_ha + n_crops_grown
                        + elevation_m_mean + slope_deg_mean
Model C:  yield ~ is_tn + [Model B covariates] + [approved irrigation variables]
```

**Critical pre-registered rule — common estimation sample.** β_A, β_B and β_C must be estimated on the **identical set of rows**, namely the rows where the irrigation variables are `OBSERVED`. Comparing a β_B from 382 rows against a β_C from a smaller irrigation-available subset would confound "irrigation explains the gap" with "the subset is different". Experiment 4's published β_A = +0.825 and β_B = +0.565 will additionally be **re-estimated on the original 382 rows as a reproduction check**, reported separately from the common-sample estimates.

**Coverage note.** Experiment 4's satellite provenance pull completed after that commit (38 districts, 18,758 scenes, 0 failures), so aligned coverage may now exceed the 143 Tamil Nadu rows Experiment 4 used. The analysis dataset will be **frozen as a snapshot** at Checkpoint 5 and the difference from Experiment 4's coverage documented in `EXPERIMENT_5_IRRIGATION_PROVENANCE.md`.

No variables will be added to Model C after seeing its results. No alternative model will be run in search of a preferred outcome.

# 9. Primary outcome and pre-registered threshold

```
Incremental Irrigation Explanation (%) = ((β_B − β_C) / β_A) × 100
```

| Classification | Condition |
|---|---|
| **MEANINGFUL SUPPORT** | ≥ 10 percentage points, AND acceptable precision, AND direction consistent in approved robustness checks, AND not driven by a single district or anomaly, AND no critical leakage, AND adequate provenance |
| **PARTIAL / SUGGESTIVE SUPPORT** | 5% ≤ incremental < 10%, OR point estimate reaches 10% but precision/robustness insufficient |
| **LITTLE OR NO SUPPORT** | < 5%, OR no stable reduction in the regional coefficient |
| **INCONCLUSIVE** | Reliable evaluation impossible: insufficient sample, inadequate historical coverage, unresolved mapping, excessive uncertainty, material source disagreement, or critical data-quality problems |

Exactly one classification will be reported, in the fixed format specified in the task (threshold, observed value, precision PASS/WARNING/FAIL, robustness PASS/WARNING/FAIL, leakage/provenance PASS/FAIL, final classification).

# 10. Mandatory pooled-vs-within-region rule

For every important relationship, three quantities are computed: **pooled**, **within Tamil Nadu**, **within AP/TG**. If a relationship is strong pooled but disappears or materially changes within regions, it is flagged **`POTENTIAL_GEOGRAPHIC_CONFOUNDING`** and is not interpreted as a genuine agricultural relationship without explicit review.

This rule exists because Experiment 4 was nearly misled by exactly this: `n_rice_seasons` correlated −0.463 with yield pooled but −0.01 within AP/TG — a Simpson's-paradox artefact of a reporting convention.

# 11. Robustness tests (proposed; to be individually approved at Checkpoint 9)

1. Alternative valid irrigation definitions (pre-listed, not chosen by outcome)
2. Within-region relationships
3. Irrigation source composition
4. Symmetric outlier robustness (winsorization applied identically to all states, as in Experiment 4 B9)
5. Leave-one-district-out sensitivity

All approved tests are reported, including failures. No test will be invented after seeing results to improve a conclusion.

# 12. Leakage checks (Checkpoint 10)

Geographic leakage; district identity leakage; future-year leakage; target leakage; train/test contamination; state-average substitution; derived-feature leakage; historical boundary leakage; interpolation leakage; location-fingerprint shortcuts.

Critical leakage ⇒ **EXPERIMENT STOP**; no predictive modelling until resolved.

Note: irrigation is plausibly a **static-ish district property**. If it varies little within a district over 2000–2012 it can act as a location fingerprint, the failure mode this project already found with soil (Experiment 1) and controlled for in Experiment 4 Phase C2. A **static-only control arm is therefore mandatory** in the predictive test.

# 13. Secondary predictive transfer test (Checkpoint 11, only after leakage approval)

Six arms: Baseline; Weather+Satellite; Weather+Satellite+Exp4 covariates; Weather+Satellite+Exp4 covariates+Irrigation; Static only; Soil only. Metrics: MAE and R². Hyperparameters unchanged from Experiment 1. Train/test share no district.

Explanatory and predictive findings are interpreted **separately**. A predictive gain does not demonstrate that irrigation explains the regional gap.

# 14. Success and failure criteria

The experiment succeeds if it answers the question reliably. All four outcomes are valid results:

- **A** Meaningful support
- **B** Partial/suggestive support
- **C** Little or no support — a valid negative result
- **D** Inconclusive due to insufficient valid historical data — also a valid result

Failure is defined as: fabricated or substituted data, hidden missingness, undocumented methodology change, post-hoc threshold change, or a claim unsupported by the evidence.

# 15. Planned figures (`experiments/figures/experiment5/`)

Created only where real data supports them: irrigation coverage by district/year; missingness; net and gross irrigated area by region; irrigated fraction by region; region coefficient A vs B vs C; incremental explained gap; pooled vs within-region relationships; robustness results; cross-region MAE and R²; leave-one-district-out sensitivity.

# 16. Assumptions and open risks

Stated now so they are not silently resolved later:

1. **Assumption:** Experiment 4's `is_tn` contrast (TN vs AP+TG pooled) is the correct region variable to carry forward. *Risk:* it pools AP and Telangana, which differ. Any change would break comparability with Experiment 4 and would require re-approval.
2. **Assumption:** the Kharif 2000–2012 subset remains the estimation frame. *Risk:* irrigation sources may report on an **agricultural year** (e.g. 2004-05) rather than a Kharif calendar year; the year-alignment convention must be decided explicitly at Checkpoint 3/5, not assumed.
3. **Risk — the most likely failure mode:** irrigation statistics for 2000–2012 at district level may exist only in scanned PDF volumes, or only for census years. If coverage is too thin, the honest outcome is **INCONCLUSIVE**, and this plan commits to reporting that rather than padding the sample.
4. **Risk:** ICRISAT's apportioned district base is a redistribution of historical values. If it is the only viable source, that tension must be resolved by explicit approval, not by quietly accepting it.
5. **Risk:** sources may disagree materially (e.g. DES vs Minor Irrigation Census). The pre-registered response is to report the disagreement, not to pick the source giving the preferred result.
6. **Assumption:** units are hectares. Any source not stating a unit will be treated as this project already treats such cases — corroborated or marked `AMBIGUOUS`, never guessed.

# 16a. Approved modifications (recorded at Checkpoint 1 approval)

Two binding decisions were issued by the user when approving Checkpoint 1. They modify the plan above and are recorded here rather than applied silently.

## Decision 1 — apportioned / redistributed district values

> Do not use apportioned or redistributed historical district values in the primary Experiment 5 analysis. Classify such data separately and document the redistribution methodology. It may only be considered later as an external validation or sensitivity source with explicit approval.

**Consequences.** The ICRISAT District Level Database, which publishes values apportioned to a fixed historical district base, is **barred from the primary analysis**. It is not rejected outright: it is classified in a separate tier and may be proposed later, with explicit approval, as an external cross-check only. Any other source discovered to redistribute values across boundary changes falls under the same rule.

This tightens the evidence standard and raises the risk of an **INCONCLUSIVE** outcome, because the barred source is the one most likely to offer complete 2000–2012 district coverage in machine-readable form. That trade — a smaller, cleaner evidence base over a larger, redistributed one — is accepted deliberately.

## Decision 2 — year alignment

> Do not assume an agricultural-year-to-Kharif mapping. During source discovery, document the exact time definition used by every candidate source. Do not merge, transform, or align years until the convention is explicitly reviewed and approved.

**Consequences.** The time definition of every candidate source (agricultural year, calendar year, crop year, census reference year, and the exact months it spans) is recorded verbatim at Checkpoint 2. **No year mapping, merge or transformation occurs** until a convention is reviewed and approved. Risk 2 in §16 is therefore not resolved by assumption; it becomes an explicit approval item.

# 16b. Checkpoint 7 — primary model specification (presented for approval; NOT yet run)

No regression has been estimated. This section fixes every analysis decision **before** any Model C coefficient exists.

## Estimation sample

| Quantity | Value |
|---|---|
| Experiment 4 matched subset | 382 rows |
| Rows with all four Model B covariates | 382 (0 missing) |
| Rows excluded — Ariyalur, `UNMAPPABLE_YEAR_NOT_COVERED` | 4 |
| **Common estimation sample for A, B and C** | **378 rows** |
| Districts | 31 |
| Years | 2000–2012 (Kharif) |
| By region | Tamil Nadu 139 · Andhra Pradesh 130 · Telangana 109 |

The **only** loss relative to Experiment 4 is the 4 Ariyalur rows. β_A, β_B and β_C are all estimated on these identical 378 rows, so the incremental statistic is not contaminated by a changing sample. Experiment 4's published β_A = +0.825 / β_B = +0.565 will additionally be re-estimated on its original 382 rows as a separate reproduction check.

## Models

```
Model A:  yield ~ is_tn
Model B:  yield ~ is_tn + non_rice_cropped_area_ha + n_crops_grown
                        + elevation_m_mean + slope_deg_mean
Model C:  yield ~ is_tn + [Model B covariates] + pct_net_irrigated_to_net_area_sown
```

Estimator: OLS with intercept, identical to Experiment 4. Target `final_yield_t_ha`. Region variable `is_tn` (Tamil Nadu = 1; AP + Telangana = 0).

## Included irrigation variable — one, fixed in advance

**`pct_net_irrigated_to_net_area_sown`** — the pre-registered primary variable `irrigated_fraction`. It is **published directly by both sources**, so it requires no derivation, and being a ratio it is less exposed to the absolute-area definitional difference than the raw hectare columns. Exactly **one** irrigation regressor enters Model C; entering several and reporting the best would be specification search.

## Excluded variables and reasons

| Excluded | Reason |
|---|---|
| `n_rice_seasons` | Experiment 4 region proxy (KS 0.996, zero within-TN variance); a reporting convention, not agronomy |
| `gross_cropped_area_ha`, `rice_area_share` | Share a term with the target's denominator (rice area) |
| `net_irrigated_area_ha`, `gross_irrigated_area_ha` | Reserved for pre-approved robustness only. Collinear with the primary and with each other; entering them alongside it would be redundant |
| `irrigation_intensity` | Reserved for robustness. Undefined for Hyderabad (0/0) |
| Irrigation **source composition** (canal/tank/well shares) | **The two DES offices use different source taxonomies** (AP: major/medium/minor projects, tanks by size; TN: canals, tanks, wells-sole, supplementary). Category-by-category comparison is not valid |

## Missing-data handling

No imputation. The common sample has **zero** missing values in the target, the four Model B covariates and the irrigation variable. Ariyalur is **excluded, not filled**.

## Transformations

**None.** All variables enter as published, on their original scales. No logs, no standardization in the primary models (a ridge robustness check standardizes covariates only, leaving `is_tn` unpenalized).

## Outlier rules — fixed in advance

No observation is deleted in the main analysis. **Hyderabad's net and gross irrigated area of exactly 0 is a real published value** (an essentially urban district), not missing data, and is retained. Sensitivity to extremes is assessed only through the pre-approved Checkpoint 9 tests: symmetric winsorization applied identically to all states, and leave-one-district-out.

## Two decisions that require explicit approval

### D-A. Year-alignment convention

Irrigation exists for one year only (Fasli 1414 = 2004-05); yield rows span Kharif 2000–2012.

- **Convention 1 — static district attribute (recommended).** Apply each district's 2004-05 value to all its 2000–2012 rows. Keeps n = 378 and preserves comparability with Experiment 4. **Assumption, stated and unverifiable from one year: district irrigation extent is approximately stable over 2000–2012.**
- **Convention 2 — nearest-year only.** Restrict to year 2004, giving ~31 rows (one per district). Assumption-light but collapses the sample and destroys precision; β_A and β_B would also have to be refit on those 31 rows.

Checkpoint 6 showed the choice matters: pooled correlation with `net_irrigated_area` flips from **+0.233** (2004 only) to **−0.186** (district mean). The convention must therefore be chosen deliberately, not defaulted into.

### D-B. Standard errors

Experiment 4 used plain OLS standard errors at observation level. In Model C both `is_tn` **and** the irrigation variable are **constant within district**, with ~12 rows per district. Plain OLS SEs on 378 observations therefore overstate precision, because the effective number of independent units is 31 districts, not 378 rows.

- **Option 1 (recommended):** report **both** plain OLS SEs (for exact Experiment 4 comparability) **and** district-clustered SEs, and use the **clustered** SEs for the primary outcome's "statistical precision" verdict.
- **Option 2:** plain OLS only, matching Experiment 4 exactly.

This affects the pre-registered precision judgement, not the point estimates, so it must be settled before Model C is estimated.

## Carried-forward caveats that will appear in the final report

1. All four irrigation variables were flagged **`POTENTIAL_GEOGRAPHIC_CONFOUNDING`** at Checkpoint 6. For the primary variable the pooled correlation is ~0 while within-region correlations are **−0.44/−0.56 (TN)** and **+0.26/+0.09 (AP/TG)** — a sign reversal.
2. Net-area definitions are not provably identical across the two sources.
3. Irrigation is static per district, so in the Checkpoint 11 predictive test it can act as a **location fingerprint**; a static-only control arm is mandatory there.
4. Tiruppur's 2009 formation changes Coimbatore/Erode extents relative to the 2004-05 figures.

# 17. What this checkpoint did NOT do

No source accessed. No data collected, downloaded, merged, cleaned, imputed or interpolated. No feature created. No model run. No figure generated. No previous experiment file touched. Nothing committed.
