# Experiment 5 — Does district-level irrigation explain the remaining cross-regional agricultural gap?

**FINAL PRIMARY OUTCOME: LITTLE OR NO SUPPORT** (Outcome C — a valid negative result)

Plan: `EXPERIMENT_5_IMPLEMENTATION_PLAN.md` · Provenance: `EXPERIMENT_5_IRRIGATION_PROVENANCE.md` · Data audit: `EXPERIMENT_5_IRRIGATION_DATA_AUDIT.md` · Leakage audit: `EXPERIMENT_5_LEAKAGE_AUDIT.md`
Results: `experiment5_primary_results.json`, `experiment5_robustness.json`, `experiment5_descriptive.json`, `experiment5_predictive_results.json` · Figures: `figures/experiment5/`

Experiments 1–4 are unchanged. No previous experiment file was modified or overwritten.

---

## 1. Question and pre-registered hypotheses

> Does historically appropriate district-level irrigation explain a meaningful additional portion of the residual cross-regional difference remaining after Experiment 4?

**H5** — irrigation explains a statistically meaningful additional portion. **H0** — it does not materially reduce the residual regional coefficient beyond the Experiment 4 covariates.

Both were fixed before any Model C coefficient existed, as was the primary statistic and its threshold:

```
Incremental Irrigation Explanation (%) = ((β_B − β_C) / β_A) × 100
MEANINGFUL ≥ 10 pp · PARTIAL 5–10 pp · LITTLE OR NO < 5 pp · INCONCLUSIVE if unevaluable
```

The question is **explanatory**. Predictive performance is secondary and cannot override the primary classification.

## 2. Data: what was collected, and how

The binding difficulty was access, not existence. Every Andhra Pradesh / Telangana statistics host fails DNS from this environment, and `micensus.gov.in` likewise. The data were recovered from the **Internet Archive**, which preserves the original government publications byte-for-byte; publication identity and retrieval route are recorded separately throughout.

| Source | Publication | Year | Level | Unit | Status |
|---|---|---|---|---|---|
| DES Andhra Pradesh | *Season and Crop Report 2004-05 / 1414 Fasli*, Table III-B | 2004-05 | District (23, undivided AP) | Hectares (stated) | **Used** |
| DES Tamil Nadu | *Season and Crop Report 2004-05*, Table III-B | 2004-05 | District (30) | Hectares (stated) | **Used** |
| Minor Irrigation Census, 4th | Ministry of Jal Shakti | 2006-07 | State + partial district | schemes / potential | **Rejected** |
| Minor Irrigation Census, 3rd | — | 2000-01 | — | — | `SOURCE_UNREADABLE` (truncated) |
| ICRISAT DLD (apportioned) | — | 1966–2015 | District (redistributed) | — | **Barred** by standing ruling |
| data.gov.in | — | 2016-17 | 12/13 state-level | — | **Rejected** |

**Why the Minor Irrigation Census was rejected** — reported, not quietly dropped: its 431-page national report contains **zero** pages carrying ≥3 study districts from either region. Its only district content is Appendix-II *"Districts with more than 1 lakh MI schemes"*, a threshold-filtered partial list of **scheme counts**. Its variables (schemes, irrigation potential created/utilised) are not net or gross irrigated area, and it covers only schemes with **CCA ≤ 2,000 ha**, structurally excluding the major canal systems that serve the Cauvery and Krishna/Godavari deltas — an exclusion correlated with the very contrast under study.

**Nothing was interpolated, redistributed, estimated, state-substituted or imputed anywhere in this experiment.**

## 3. District harmonization

32 study districts → **26 EXACT, 5 RENAMED, 1 UNMAPPABLE**; zero SPLIT or MERGED, because neither is used to move a value. Every mapping is declared explicitly; no fuzzy matching. All 31 mapped source names were verified present in the source tables (0 mismatches).

**Ariyalur** is `UNMAPPABLE_YEAR_NOT_COVERED`: constituted in 2007 from Perambalur, so absent from the 2004-05 source. Perambalur's values were **not** assigned, split, estimated or copied. Coherence check: the four affected HarvestWise rows are dated 2009–2012, all after the district's creation — exactly as expected.

Telangana's ten districts appear under *"Andhra Pradesh (undivided)"*; `source_state_as_printed` is recorded separately from `harvestwise_region`. A state-attribution difference, not a boundary change.

## 4. Data quality — PASS (9/9 gating checks, 1 warning)

The decisive checks:

| Check | Result |
|---|---|
| AP district sum vs its own published state total | 3,880,590 ha vs 3,880,590 ha — **0.00%** |
| TN district sum vs its own published state total | 2,637,198 ha vs 2,637,198 ha — **0.00%** |
| Identity `gross = net + irrigated more than once` | **53 of 53 rows exact** |

The state totals are printed elsewhere in the same publications, independent of the district tables parsed, so exact agreement is strong evidence of faithful, complete extraction.

**Warning:** the two sources do not use provably identical net-area definitions — Tamil Nadu's column is labelled *"(excl. wells suppl. other sources)"*, Andhra Pradesh's states no exclusion. Recorded on every row; a genuine comparability limitation sitting on the exact contrast being measured.

## 5. Descriptive findings

| Variable | AP (n=10) | Telangana (n=10) | Tamil Nadu (n=11) | SMD (TN vs AP+TG) |
|---|---|---|---|---|
| Net irrigated area (ha) | 214,030 | 128,029 | 92,411 | **−1.05** |
| Gross irrigated area (ha) | 277,726 | 166,118 | 107,856 | **−1.09** |
| **% net irrigated to net sown** | 45.77 | 32.43 | **51.08** | **+0.56** |
| Irrigation intensity | 1.26 | 1.31 | 1.17 | −0.72 |

Tamil Nadu districts are **smaller in absolute irrigated area but proportionally more irrigated** (51% vs 39%). The fraction moves in the direction H5 predicts; the absolute measures move opposite.

**All four variables were flagged `POTENTIAL_GEOGRAPHIC_CONFOUNDING`.** For the primary variable the pooled correlation with yield is ≈ 0 (+0.006 / +0.018) but decomposes into **−0.44/−0.56 within Tamil Nadu** and **+0.26/+0.09 within AP/Telangana** — a sign reversal around a null pooled value, the same structure that nearly derailed Experiment 4.

## 6. Primary results

Sample: **378 rows, 31 districts, Kharif 2000–2012** (TN 139 · AP 130 · TG 109). The only loss from Experiment 4's 382 is the four Ariyalur rows. β_A, β_B and β_C are estimated on identical rows.

Experiment 4 reproduced **exactly** on its original 382 rows: β_A **+0.8250** (published +0.825), β_B **+0.5646** (published +0.565).

| Model | β_region | Plain 95% CI | **Clustered 95% CI (G=31)** | R² |
|---|---|---|---|---|
| A region only | **+0.8340** | [+0.674, +0.994] | [+0.400, +1.268] | 0.219 |
| B + Exp 4 covariates | **+0.5702** | [+0.369, +0.772] | [+0.125, +1.015] | 0.284 |
| C + irrigation | **+0.5834** | [+0.382, +0.785] | [+0.146, +1.021] | 0.290 |

Clustering roughly doubles the standard errors, as it must: `is_tn` and irrigation are both constant within district, so the effective units are 31 districts, not 378 rows.

```
Experiment 4 covariates accounted for:       31.63 %
Observed incremental irrigation explanation: −1.57 percentage points
Bootstrap 95% CI:                            [−23.67, +8.83] pp
P(incremental ≥ 10 pp):                      0.021
```

**The region coefficient rose rather than fell.** The irrigation coefficient is −0.0057 t/ha per percentage point.

## 7. Robustness — PASS

| Test | Result |
|---|---|
| R1 alternative definitions | **All four negative**: primary −1.57, net area −41.04, gross −36.30, intensity −4.48 pp |
| R2 within-region | TN −0.0170 [−0.049, +0.015]; AP/TG +0.0020 [−0.011, +0.015] — both indistinguishable from zero |
| R3 source composition | **NOT RUN — invalid by construction**; the two DES taxonomies have no defensible one-to-one mapping |
| R4 symmetric winsorization | −1.57 → −1.55 pp (8 values clipped: TN 7, AP 1) |
| R5 leave-one-district-out | Range −3.69 to −0.17; **0 of 31 folds reach the threshold, none positive**; Hyderabad removed → −1.10 |
| R6 cluster bootstrap | 95% CI [−23.67, +8.83]; P(≥10 pp) = 0.021 |

The absolute-area definitions worsen the gap markedly, consistent with them partly proxying region (TN districts are smaller) rather than explaining it.

## 8. Leakage — PASS (8 PASS, 2 WARNING, 0 CRITICAL)

Verified clean: no state-average substitution (31 distinct values across 31 districts — state substitution could yield at most 3), no target leakage (irrigated fraction's denominator is *net area sown, all crops*; the target's is *rice area*), **no interpolation anywhere**, boundary changes declared rather than absorbed.

**Warning 3 — future-year exposure.** 117 of 378 rows (**31.0%**) pair a yield observation with an irrigation figure measured in a later year. Balanced across regions (AP 40, TN 40, TG 37), so it does not favour one side. Defensible for an explanatory analysis of a slow-moving attribute; a real limitation in a forecasting framework.

**Warning 10 — location fingerprint.** Irrigation is constant within district (0 of 31 vary) and takes 31 distinct values across 31 districts — numerically a one-to-one district identifier. Mitigated by the mandatory arm-7 control.

Both warnings would tend to **inflate** an apparent effect. The result is a null, so they cannot have produced it; they make the negative more conservative.

## 9. Predictive transfer (secondary)

Train AP+Telangana (239 rows, 20 districts) → test unseen Tamil Nadu (139 rows, 11 districts), overlap 0, seeds 42–46, hyperparameters unchanged.

| Arm | MAE ↓ | R² ↑ |
|---|---|---|
| 1 Baseline | 1.058 ± 0.022 | −0.684 |
| 2 Weather + Satellite | 1.079 ± 0.041 | −0.840 |
| 3 + Exp 4 covariates | 0.907 ± 0.054 | −0.417 |
| **4 + Irrigation** | **0.878 ± 0.100** | −0.355 |
| 5 Static only | 1.237 ± 0.147 | −1.272 |
| 6 Soil only | 1.457 ± 0.187 | −2.065 |
| **7 Static only + irrigation** | 1.239 ± 0.035 | −1.261 |

**The shortcut control passed:** arm 7 is far worse than arm 4 and worse than baseline, and arm 5 → arm 7 moves by **−0.0015** — irrigation adds essentially zero standalone static power.

**But the arm-4 gain does not survive scrutiny.** It wins in only **3 of 5 seeds**; the mean gain (0.029) is a quarter of its own seed SD (0.108); paired t **p = 0.58**. Reported as **no demonstrable predictive improvement**. The best arm's R² is still −0.355, worse than predicting Tamil Nadu's own mean. And 31% of rows carry the anachronism above.

## 10. What the data support

1. Irrigation **as measured here** accounts for none of the residual regional association; H0 is not rejected.
2. A *meaningful* (≥10 pp) effect is excluded at conventional confidence (bootstrap upper bound +8.83; P = 0.021).
3. The finding is stable: four definitions, 31 leave-one-out folds, winsorization — all agree.
4. Tamil Nadu districts really are proportionally more irrigated (51% vs 39%) — the descriptive premise of H5 held; the explanatory consequence did not.
5. Experiment 4's coefficients reproduce exactly, so this is the same estimator, not an approximation.

## 11. What the data do NOT support

1. **No causal claim.** Nothing here establishes that irrigation does or does not cause yield differences.
2. **Not** evidence that irrigation is agronomically unimportant — a proposition this design cannot test.
3. **Not** a demonstrated predictive improvement (p = 0.58 across seeds).
4. **Not** a claim that *partial* support is excluded: P(incremental ≥ 5 pp) = 0.063, so 5–10 pp cannot be conclusively ruled out.
5. **Not** a statement about Rabi or Whole Year seasons, or about districts outside the 31 studied.

## 12. Limitations

**Coverage** — one observation year (2004-05); the 3rd MI Census retrieval was truncated; direct government hosts unreachable; 11 of 12 TN study districts; 4 of 382 rows lost with Ariyalur.

**Measurement** — net-area definitions not provably identical; source-composition taxonomies incomparable; Tiruppur's 2009 formation alters Coimbatore/Erode extents relative to 2004-05.

**Design** — irrigation static per district under an explicitly approved stability assumption, never described as annually observed; all four variables flagged for geographic confounding, with a within-region sign reversal on the primary variable.

**Inference** — 31 clusters is small; the bootstrap CI is wide.

## 13. Scientific conclusion

Experiment 4 left approximately 70% of the Tamil Nadu yield gap unexplained and identified district irrigation as the leading remaining hypothesis. Experiment 5 obtained genuine, historically appropriate, unit-verified district irrigation data for both regions in a matched year — data that reconciles exactly with its own sources' published state totals — and tested that hypothesis under a pre-registered threshold with clustered inference, a district bootstrap, five robustness tests and a ten-category leakage audit.

**The hypothesis did not hold.** Irrigation accounts for none of the residual regional association, and the result is robust to every alternative definition, every leave-one-district-out fold, and symmetric outlier treatment.

The gap therefore remains unexplained — but the field of candidates is now smaller, which is the point of a controlled negative result. Two directions follow, in order of promise: **more irrigation years**, which would convert a static approximation into a genuine panel and permit within-district identification; and **non-irrigation candidates** — varietal composition, fertiliser intensity, cropping calendar and soil-water holding capacity — none of which this project has yet measured at district level.

```
Pre-registered threshold:                    ≥ 10 percentage points
Observed incremental irrigation explanation: −1.57 %
Statistical precision:   PASS
Robustness:              PASS
Leakage/provenance:      PASS

FINAL PRIMARY OUTCOME: LITTLE OR NO SUPPORT
```
