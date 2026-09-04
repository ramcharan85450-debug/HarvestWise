# Experiment 5 — leakage audit (Checkpoint 10)

Covers the ten required categories. Every verdict below is backed by a check run against the actual 378-row estimation frame, not by inspection of intent.

**Overall: 8 categories PASS, 2 categories WARNING, 0 CRITICAL.**

No critical leakage was found, so predictive modelling is not blocked — but the two warnings impose a mandatory control on Checkpoint 11 and a mandatory caveat in the final report.

---

## 1. Geographic leakage — PASS

The explanatory models (A/B/C) are cross-sectional-plus-panel regressions on a fixed 378-row sample; there is no train/test split to leak across. For Checkpoint 11 the design is AP+Telangana → Tamil Nadu, where the training and test districts are **disjoint by construction** (20 source districts vs 11 target districts, intersection empty). No district appears on both sides.

## 2. District identity leakage — PASS

No district identifier enters any model. The regressors are `is_tn`, four Experiment 4 covariates and one irrigation variable. `district`, `district_id`, `canonical_district_name` and `group` are carried as metadata only. See category 10 for the separate — and real — question of whether the irrigation *value* can act as an identifier.

## 3. Future-year leakage — **WARNING (declared, not concealed)**

Irrigation is observed for **one year only (Fasli 1414 = 2004-05)** and, under the approved Convention 1, is applied as a static district attribute across 2000–2012. Measured consequence:

| Rows relative to the irrigation observation year | Count | Share |
|---|---|---|
| **Before 2004 (2000–2003)** | **117** | **31.0%** |
| At 2004 | 30 | 7.9% |
| After 2004 | 231 | 61.1% |

Pre-2004 rows by region: Andhra Pradesh 40, Tamil Nadu 40, Telangana 37 — the exposure is **balanced across regions**, so it does not systematically favour one side of the regional contrast.

**Assessment.** For an *explanatory* analysis of a slow-moving structural district characteristic this is a standard and defensible treatment, and it was explicitly approved (D-A) with the stability assumption recorded. It is **not** a case of a future outcome contaminating a predictor. It nevertheless means that for 31% of rows the irrigation figure post-dates the yield being explained, and the variable must never be described as annually observed. Classified WARNING rather than PASS because in a **forecasting** framework — which HarvestWise is — an anachronistic covariate is a genuine limitation, and it is carried into the Checkpoint 11 caveats.

## 4. Target leakage — PASS

Target is `final_yield_t_ha` = rice production / **rice area**. The primary irrigation variable is `pct_net_irrigated_to_net_area_sown`, whose denominator is **net area sown (all crops)**, a different quantity from rice area. The target is not among the regressors, and no regressor is derived from rice production or rice area. The two Experiment 4 covariates that *did* share the target's denominator (`gross_cropped_area_ha`, `rice_area_share`) remain excluded.

## 5. Train/test contamination — PASS

No train/test split exists in the explanatory analysis. For Checkpoint 11, source and target district sets are disjoint (category 1), and all preprocessing — scaler, any imputation — is fit on training rows only, as in Experiment 4's audited Phase C.

## 6. State-average substitution — PASS

Verified numerically: the irrigation variable takes **31 distinct values across 31 districts**. Had any state average been substituted, at most 3 distinct values could appear. No state-level figure was used as a district value anywhere; the state totals in the sources were used **only** as reconciliation checks (Checkpoint 5, matching to 0.00%).

## 7. Derived-feature leakage — PASS

The primary variable is **published directly by both sources** and is not derived by this project. The one derived quantity, `irrigation_intensity` = gross/net, is confined to robustness test R1 and was validated against Tamil Nadu's own published intensity column (max absolute difference 0.0048). No feature is constructed from the target, from post-outcome information, or from the test split.

## 8. Historical boundary leakage — PASS

Boundary changes were handled explicitly, not absorbed:

- **Ariyalur** (created 2007 from Perambalur) is classified `UNMAPPABLE_YEAR_NOT_COVERED` and **excluded** (4 rows). Perambalur's values were not split, redistributed, copied or estimated onto it.
- **Telangana districts** are reported in the source under undivided Andhra Pradesh. This is recorded as a state-attribution difference; district identity and boundaries are unchanged, and no value crosses a boundary.
- **Tiruppur** (formed 2009 from parts of Coimbatore and Erode) is recorded as `OBSERVED_WITH_BOUNDARY_CAVEAT`: the 2004-05 Coimbatore/Erode extents are larger than their post-2009 extents. This is a **declared limitation**, not a correction applied to the data.

No apportioned or redistributed source was used in the primary analysis, per the standing ruling on ICRISAT.

## 9. Interpolation leakage — PASS

**Nothing was interpolated.** No value was forward-filled, back-filled, imputed, smoothed or estimated between census or report years. The single observed year is used as a single observed year, with its temporal extension declared as an assumption rather than manufactured as data. Missingness is excluded (Ariyalur), never filled.

## 10. Location-fingerprint shortcuts — **WARNING (material for Checkpoint 11)**

Measured, not assumed:

- Districts with more than one distinct irrigation value: **0 of 31** — irrigation is constant within district by construction.
- Distinct irrigation values: **31 across 31 districts** — the value is **unique to each district**.

So the irrigation variable is, numerically, a **one-to-one district identifier**. This is precisely the failure mode this project has already encountered twice: soil in Experiment 1, and `n_rice_seasons` in Experiment 4.

**Why this is a WARNING rather than CRITICAL.** In the Checkpoint 11 design the model trains on AP+Telangana districts and is tested on Tamil Nadu districts it has never seen. A value unique to an unseen district cannot be memorised from training, so it functions as a legitimate district-level covariate rather than as a lookup key. The risk is not memorisation but **shortcut behaviour** — the model exploiting a static district-level signal instead of the season-varying agronomy the framework is supposed to learn.

**Mandatory mitigation, carried into Checkpoint 11:** the pre-registered `static_only` arm must be run and reported, exactly as Experiment 4 did. If the full model improves while `static_only` performs comparably, the improvement must be reported as shortcut behaviour, not as an irrigation effect.

---

## Verdict

| # | Category | Verdict |
|---|---|---|
| 1 | Geographic leakage | PASS |
| 2 | District identity leakage | PASS |
| 3 | Future-year leakage | **WARNING** |
| 4 | Target leakage | PASS |
| 5 | Train/test contamination | PASS |
| 6 | State-average substitution | PASS |
| 7 | Derived-feature leakage | PASS |
| 8 | Historical boundary leakage | PASS |
| 9 | Interpolation leakage | PASS |
| 10 | Location-fingerprint shortcuts | **WARNING** |

**No CRITICAL leakage. Predictive modelling is not blocked.**

Neither warning affects the Checkpoint 8/9 explanatory result, which is a **negative** finding: irrigation accounts for none of the residual regional association. Leakage of either kind would tend to *inflate* an apparent effect, so their presence cannot manufacture the null that was observed — if anything they make the negative result more conservative.

Both warnings must appear in the final report's limitations, and the `static_only` control is mandatory at Checkpoint 11.
