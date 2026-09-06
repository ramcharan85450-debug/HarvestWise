# Experiment 9 — Results report

**Within-season temperature structure as incremental predictive information for Kharif rice yield**

| Field | Value |
|---|---|
| Frozen pre-registration | `experiments/EXPERIMENT_9_PREREGISTRATION.md` |
| Pre-registration SHA-256 | `a906931309fdc5ddfe948afdaccb2fffb159b95f46699451b40a7b1574479a30` (verified unmodified) |
| Git HEAD | `677ace08667c3bbd755c499a494fc240dcea1feb` |
| Estimation date | 2026-09-06 |
| Results artefact | `experiments/experiment9_results.json` |

---

## 1. Executive summary

# SUPPORTED UNDER THE PRE-REGISTERED PRIMARY SPECIFICATION, BUT SPECIFICATION-FRAGILE

The pre-registered primary analysis (Arm 0) found a positive within-panel association between
daily maximum-temperature variability (`t_sd_daily_tmax`) and Kharif rice yield, conditional on
district fixed effects, year fixed effects, seasonal mean temperature and seasonal precipitation.
**β = +0.17195 t/ha per SD, bootstrap p = 0.0211, bootstrap CI [+0.0422, +0.3233].** All three
pre-registered conditions were satisfied.

**The association is nonetheless specification-fragile, and the report does not present it as
robust, definitive, or causal.** Removing year fixed effects **reverses the sign** and remains
statistically significant in that opposite direction. The balanced-panel sensitivity produces an
essentially zero estimate (β = +0.0059, p = 0.9408). Neither regional subset is statistically
supported on its own. Two secondary temperature constructs survive multiplicity correction **with
opposite signs**.

The correct characterisation is **pre-registered primary support with substantial specification
sensitivity** — not evidence that higher temperature variability increases yield.

---

## 2. Pre-registered research question

> Does **within-season temperature structure** — the shape and variability of daily maximum
> temperature across the Kharif window — contain **predictive information about district rice
> yield beyond the seasonal temperature representation already present in the model**?

The model has carried `weather_temp_c_mean`, a single seasonal average, since Experiment 1. The
question is whether *structure* adds to *level*. It is **not** the question "does temperature
affect yield".

## 3. Pre-registered hypothesis

**H9.** Conditional on district fixed effects, year fixed effects, `weather_temp_c_mean` and
`weather_precip_mm_sum`, `t_sd_daily_tmax` is **associated** with Kharif rice yield.
**H9-0:** its coefficient is zero.

## 4. Frozen specification

```
yield_it = alpha_i + gamma_t
         + delta_1 * weather_temp_c_mean_it      (always retained)
         + delta_2 * weather_precip_mm_sum_it    (always retained)
         + beta * t_sd_daily_tmax_it             (standardised to unit SD)
         + e_it
```

Inference fixed in advance: OLS two-way FE; clustering on district (31 clusters); **restricted
wild cluster bootstrap, Rademacher weights, 9,999 replications, seed 20260905** as the p-value of
record; CR1 and HC3 reported alongside; CI by test inversion of the same bootstrap.

## 5. Dataset and sample

| | Rows | Districts |
|---|---:|---:|
| Andhra Pradesh | 130 | 10 |
| Tamil Nadu | 121 | 12 |
| Telangana | 108 | 9 |
| **Total** | **359** | **31** |

13 years (2000–2012), Kharif rice, 183-day window (1 June – 30 November), 183/183 days present for
every district-year, zero missing values. Exclusions E1–E4 applied exactly as pre-registered
(22 boundary rows, 1 singleton). **No post-hoc exclusion was applied to Arm 0.**

## 6. Primary model

Two-way fixed effects, 46 parameters, 313 residual degrees of freedom. `weather_temp_c_mean` and
`weather_precip_mm_sum` retained throughout, as the hypothesis is defined as incremental to them.

## 7. Primary result

```
n                    359          districts 31        years 13
beta (t/ha per SD)   +0.17195
SE  CR1              0.07207      SE HC3    0.06687
t   CR1              2.386        design effect 1.078
p   bootstrap        0.0211       p CR1 0.0235       p HC3 0.0106
CI  bootstrap       [+0.04223, +0.32329]
CI  CR1             [+0.02477, +0.31913]
residual df          313          raw SD of predictor 0.5681 C
```

All three inference procedures agree in sign and significance. The design effect of 1.078 shows
clustering barely inflated standard errors — the result is not an artefact of the clustering
choice.

## 8. Primary criterion evaluation

| Condition | Requirement | Observed | Met |
|---|---|---|---|
| 1 | bootstrap p < 0.05 | 0.0211 | **YES** |
| 2 | bootstrap CI excludes zero | [+0.0422, +0.3233] | **YES** |
| 3 | \|β\| ≥ A1 = 0.0834 | 0.17195 (≈ 2.1 × A1) | **YES** |

# PRIMARY CLASSIFICATION: SUPPORTED

This classification is **not** revised in light of the robustness arms. The pre-registration
imposed no directional condition, and no sign requirement is introduced retroactively.

## 9. Robustness arms

| Arm | N | β | Bootstrap p | Interpretation |
|---|---:|---:|---:|---|
| Arm 0 primary | 359 | +0.1720 | 0.0211 | Pre-registered criterion supported |
| R1 district FE only | 359 | −0.1263 | 0.0034 | **Significant opposite direction** |
| R2 region trends | 359 | −0.0906 | 0.0159 | **Significant opposite direction** |
| R3 exclude 6 low-agreement districts | 299 | +0.1638 | 0.0273 | Same direction |
| R3b exclude 7 incl. Medak | 287 | +0.1539 | 0.0450 | Same direction |
| R5 balanced panel | 221 | +0.0059 | 0.9408 | Association disappears |
| R8 AP + TG | 238 | +0.0564 | 0.1843 | Null |
| R8 TN | 121 | +0.2433 | 0.1965 | Null |
| R9 drop temperature control | 359 | +0.1403 | 0.0311 | Same direction |

> **R1 and R2 are not confirmations of Arm 0. They are statistically significant estimates in the
> opposite direction.**

Removing year fixed effects does not merely weaken the association — it reverses it, with
β = −0.1263 (p = 0.0034) and a CI of [−0.204, −0.049] that excludes zero on the negative side.
R2, which replaces year effects with region-specific trends, does the same (β = −0.0906,
p = 0.0159, CI [−0.159, −0.022]).

### 9.1 Labelling defect — documented, not corrected retroactively

The analysis script's `criterion()` function mechanically labelled R1 and R2 as **"SUPPORTED"**
because it tests only three quantities — bootstrap p < 0.05, CI excluding zero, and |β| ≥ A1 —
and has **no sign condition**, since the pre-registration deliberately imposed none on the primary.
Applied to an arm whose coefficient points the other way, that label is meaningless.

**This is a labelling and reporting defect in the results artefact, not substantive support.**
It is recorded here rather than repaired, because editing the criterion function after seeing
results would itself be a post-hoc change. Readers of `experiment9_results.json` must interpret
the `criterion.verdict` field for R1 and R2 accordingly. **The pre-registration is not modified.**

## 10. Balanced-panel sensitivity

The balanced panel retains only districts observed in all 13 years: **221 observations,
17 districts, 13 years.**

```
beta = +0.0059      bootstrap p = 0.9408      CI = [-0.135, +0.146]
```

> **The primary association essentially disappears in the balanced-panel sensitivity analysis.**

The point estimate falls from +0.1720 to +0.0059 — about 3 % of its full-sample magnitude and
roughly 7 % of the A1 anchor — and the p-value is 0.94.

This is **not** proof that the primary result is false. The balanced panel is a different and
smaller sample, and the confidence interval [−0.135, +0.146] is wide enough to contain the Arm 0
estimate, so the two are not formally incompatible. What it does demonstrate is **substantial
sensitivity to panel composition**: the association depends materially on which districts and
district-years are included, and the districts dropped from the balanced panel are those with
incomplete year coverage.

## 11. Region-specific sensitivity

```
AP + TG:   beta = +0.0564   p = 0.1843   n = 238   19 districts
TN:        beta = +0.2433   p = 0.1965   n = 121   12 districts
```

**The association is not statistically supported when analysed separately within either regional
grouping.** Both bootstrap p-values exceed 0.18.

The Tamil Nadu point estimate is larger, but **this does not establish that the association exists
only in Tamil Nadu.** Its confidence interval is very wide ([−0.071, +0.934]) on 12 clusters, its
p-value is not significant, and a larger point estimate on a smaller, noisier subsample is exactly
what sampling variability produces. No regional claim is made.

This further limits the strength of the primary result: an association present in the pooled panel
but absent from both of its constituent parts warrants caution, not confidence.

## 12. Measurement-limitation sensitivity

Pre-registered scope decision: **all eligible Tamil Nadu districts retained in the primary sample.**
The six districts with low ERA5–IMD agreement form a measurement-limitation subgroup defined
solely on agreement statistics, with **no reference to yield**.

| Arm | Excluded | N | Districts | β | p |
|---|---|---:|---:|---:|---:|
| Arm 0 | none | 359 | 31 | +0.1720 | 0.0211 |
| R3 | Coimbatore, Erode, Madurai, Kanniyakumari, Dindigul, Karur | 299 | 25 | **+0.1638** | 0.0273 |
| R3b | the above plus Medak | 287 | 24 | **+0.1539** | 0.0450 |

**The primary result is not obviously driven by the predefined low ERA5–IMD agreement subgroup.**
Dropping those districts moves the coefficient by less than 10 %, and it retains significance in
both arms.

**This does NOT establish that the temperature measurement is unbiased.** Two separate concepts
must be kept apart:

1. *Does the low-agreement subgroup drive the estimate?* — Evidence says no.
2. *Is ERA5 temperature accurate?* — **Not addressed by this test.** A measurement error present
   in all districts, or one uncorrelated with the ERA5–IMD agreement ranking, would be invisible
   to R3/R3b. The terrain-correlated limitation documented in the measurement-validation report
   stands unchanged.

## 13. Secondary analyses

Each secondary predictor was fitted in its own model with the identical specification, with
Holm–Bonferroni correction across the three.

| Construct | β | Bootstrap p | Holm-adjusted p | CI |
|---|---:|---:|---:|---|
| `t_p95_tmax` | **+0.3670** | <0.0002 | **0.0003** | [+0.278, +0.456] |
| `tdays_gt30_tmax` | **−0.3321** | 0.0035 | **0.0070** | [−0.530, −0.134] |
| `t_range_season_tmax` | +0.1157 | 0.2239 | 0.2239 | [−0.082, +0.313] |

- **`t_p95_tmax` survives Holm correction.**
- **`tdays_gt30_tmax` survives Holm correction.**
- **They have opposite signs.**
- **Neither may be promoted to primary.** The pre-registration bars promoting a secondary
  regardless of result, and bars presenting a secondary as the main finding.
- **The divergent secondary results reinforce specification sensitivity.**

Note on `t_p95_tmax`'s p-value: with 9,999 replications and the `(count+1)/(reps+1)` convention,
**0.0001 is the smallest reportable value**. It means zero of 9,999 bootstrap draws exceeded the
observed statistic, and should be read as *p < 0.0002*, not as a precisely estimated 0.0001.

**These results are not combined into a single temperature effect.** Two constructs of similar
magnitude and opposite sign, both surviving correction under identical controls, cannot be
summarised as one directional finding. They indicate that constructs sharing the label
"temperature" are measuring materially different phenomena — plausibly duration of warmth versus
peak intensity — and any mechanism for that difference is **untested by this design** and is not
asserted here.

## 14. Exploratory analysis

```
tdays_gt32_tmax:   beta = +0.1970   bootstrap p = 0.4020   CI = [-0.222, +0.616]
```

Not significant, and **positive** — the opposite sign to `tdays_gt30_tmax`, its neighbour differing
only by a 2 °C threshold.

**`tdays_gt32_tmax` remains exploratory and cannot be promoted regardless of its result.** It was
designated exploratory in the pre-registration because of region-correlated zero-inflation
(zero-rate: AP 0.0 %, TN 10.3 %, TG 0.9 %, with 16 of 17 zero district-years in Tamil Nadu) — a
decision recorded before any of these estimates existed.

## 15. Leave-one-out analyses

```
R6  leave-one-district-out (31 refits):  beta range [+0.1370, +0.1970]   sign stable: yes
R7  leave-one-year-out     (13 refits):  beta range [+0.1028, +0.2410]   sign stable: yes
```

**Interpretation, deliberately narrow:** the sign of the Arm 0 estimate was stable under the
pre-registered leave-one-district-out and leave-one-year-out procedures. No single district and no
single year drives it.

**This does not overcome the balanced-panel or alternative-specification sensitivity.** Leave-one-out
perturbs the sample by one unit at a time within a fixed specification; it cannot detect fragility
that appears when the specification changes (R1, R2) or when panel composition changes
substantially (R5). Stability under R6/R7 and fragility under R1/R2/R5 are compatible, and both
are reported.

## 16. Power

Carried forward from the pre-registration, published before estimation:

```
N = 359   clusters = 31   residual df ~ 312/313 (depending on estimation convention)
Within-district-year yield SD  0.4439 t/ha
Residualised predictor SD      0.2465 C (18.8% of raw variance survives two-way FE)

MDE at 80% power, alpha 0.05:   DE 1.0 -> 0.0656 | DE 1.5 -> 0.0804 | DE 2.0 -> 0.0928
A1 = 0.0834   A2 = 0.0444
```

The design was declared **marginally powered for A1 and not powered for A2**. The realised design
effect was **1.078**, at the favourable end of that range, so the study was powered for A1 as
executed. The observed |β| = 0.1720 exceeds A1 by roughly 2.1×.

**Power considerations do not establish validity.** Adequate power means a true association of a
given size would probably be detected; it says nothing about whether the detected association is
the one intended, or whether it is stable. The balanced-panel result is the direct demonstration:
nominal full-sample power did not prevent the estimate from collapsing to +0.0059 under a
different panel composition. **Nominal power must not be read as evidence that the association is
stable.**

## 17. Computational verification

A computational optimisation was applied to the bootstrap inner loop after an initial run: `(X'X)⁻¹`
and the cluster grouping were hoisted out of the replication loop (X is invariant across
replications) and the CR1 meat matrix was formed by grouped reduction rather than a per-cluster
Python loop, using the identity `Σ_g (X_g'u_g)(X_g'u_g)' ≡ S'S`.

**Verification before use:**

```
Arm 0 bootstrap p, original implementation:   0.0211
Arm 0 bootstrap p, optimised implementation:  0.0211      BIT-IDENTICAL
speedup: 36.9x  (whole analysis 45 min -> 75 s)
```

The RNG is drawn in the same order with the same seed, so the replication sequence is identical.
**The optimisation changed computational efficiency, not the statistical specification or the
result. It is not a new experiment**, and no result was re-estimated under a different procedure.

## 18. Measurement limitations

Carried forward from `EXPERIMENT_9_MEASUREMENT_VALIDATION_REPORT.md`, pre-registered as a known
limitation rather than discovered afterwards:

| Level | ERA5–IMD agreement, AP | TN | TG | Overall |
|---|---:|---:|---:|---:|
| Within-district (district-year) | 0.873 | **0.705** | 0.818 | 0.793 |
| Daily resolution | 0.884 | **0.841** | 0.900 | — |

Classified as a **terrain-correlated measurement limitation / calibration difference**, not
evidence that ERA5 is invalid: ERA5 runs consistently cooler than IMD in all three regions
(−1.24 to −2.02 °C, a uniform calibration offset); on mean absolute difference and bias
**Telangana is the outlier, not Tamil Nadu**; and Tamil Nadu's best district reaches r = 0.916,
equal to Telangana's best. The weakest districts all lie in the Western Ghats rain-shadow interior.

ERA5 `temperature_2m_max` was **reproducibly constructible for the full sample** — 73,749 of
73,749 daily district observations, zero nulls, 183/183 days per district-year.

## 19. Interpretation

The pre-registered primary analysis found a positive within-panel association between daily Tmax
variability and Kharif rice yield after conditioning on district fixed effects, year fixed effects,
seasonal mean temperature and seasonal precipitation. The result satisfied the pre-registered
statistical and effect-size criterion.

However, the association is **specification-fragile**. Removing year fixed effects reverses the
sign; the balanced-panel analysis produces an essentially zero estimate; neither regional subset is
statistically supported; and secondary temperature constructs produce significant estimates in
opposite directions.

**This result is therefore described as: pre-registered primary support with substantial
specification sensitivity.**

It is **not** described as causal, as proof, as definitive, as robust across specifications, as
universally generalizable, or as evidence that higher temperature variability increases yield.
Permitted language throughout: *predictive association*, *incremental predictive information*,
*accounts for statistical variation*, *associated with*.

## 20. Limitations

1. **Specification fragility** — the dominant limitation. Sign reversal under R1/R2; near-zero estimate under R5; null in both R8 subsets.
2. **Direction unexplained.** The positive sign was not predicted in advance and no mechanism is asserted. The divergent secondary signs suggest these constructs may capture radiation or cloudiness rather than heat stress — untested and not claimed.
3. **Year fixed effects carry the result.** Only 18.8 % of predictor variance survives two-way FE; removing year effects changes the sign, so the estimate depends heavily on which common-shock structure is imposed.
4. **Terrain-correlated measurement limitation** in ERA5-derived weather features (§18).
5. **Observational design.** Temperature is exogenous to yield, which strengthens plausibility, but no causal claim is licensed.
6. **Power for A2 absent.** The design could not detect associations at the scale of 10 % of within-district yield variation.
7. **Kharif window and constructs are conventions**, not per-district verified agronomic calendars.

## 21. Final conclusion

# SUPPORTED UNDER THE PRE-REGISTERED PRIMARY SPECIFICATION, BUT SPECIFICATION-FRAGILE

The pre-registered primary criterion was satisfied — bootstrap p = 0.0211, CI excluding zero,
|β| = 0.1720 exceeding the A1 anchor of 0.0834 by roughly 2.1×. That verdict stands and is not
revised in light of unfavourable robustness arms.

The robustness evidence materially qualifies it. A defensible alternative specification produces a
significant estimate of the opposite sign; the balanced panel produces essentially zero; neither
region alone supports the association; and two secondary constructs disagree in direction while
both surviving multiplicity correction.

Experiment 9 should be cited as a pre-registered positive primary result whose robustness is
limited, not as a demonstration that within-season temperature structure improves yield prediction.

## 22. Reproducibility and provenance

| Item | Value |
|---|---|
| Estimation script | `experiments/run_experiment9_analysis.py` |
| Results artefact | `experiments/experiment9_results.json` |
| Panel artefact | `data/processed/experiment9_temperature_panel.csv` |
| Per-arm cache | `experiments/.experiment9_cache/` |
| Seed | `20260905` |
| Bootstrap replications | 9,999 (primary and robustness arms); 1,999 per CI grid point; 999 for leave-one-out |
| Software | Python 3.14.6, numpy 2.4.4, scipy 1.18.0, pandas 3.0.5 |
| Predictor source | `data/raw/weather/era5_tmax_daily/` — 31 JSON, ERA5-Land `temperature_2m_max` |
| Outcome source | `data/processed/district_multimodal_examples_v2.csv` (unmodified) |
| Exclusion source | `data/processed/experiment8_rainfall_panel.csv` (unmodified) |
| IMD validation reference | `data/raw/weather/imd_maxtemp/` — 13 grids, **CITED-NOT-STORED** |

Raw IMD `.grd` files are not committed, following the Experiment 8 precedent; inventory,
filenames, byte sizes, SHA-256 hashes, retrieval metadata and aggregation methodology are recorded
in the measurement-validation report.

## 23. Git integrity

```
HEAD                       677ace08667c3bbd755c499a494fc240dcea1feb
Pre-registration SHA-256   a906931309fdc5ddfe948afdaccb2fffb159b95f46699451b40a7b1574479a30
                           verified UNMODIFIED after estimation
Staged                     none
Committed / pushed         nothing
```

**Pre-registration integrity:**

- The pre-registration was **not modified**; its hash is unchanged.
- **No post-hoc sample exclusion** was used for Arm 0.
- **No predictor was promoted** on the basis of its result.
- **No robustness result replaced the primary result.**
- **R3 and R3b were predefined** sensitivity analyses, defined on measurement agreement only.
- **Secondary variables remain secondary**; `tdays_gt32_tmax` remains exploratory.
- The primary specification, controls, fixed effects, clustering, bootstrap procedure and success
  criterion were **not changed after seeing results**.

**Experiments 1–8:** `git diff 677ace0` against `training/`, `models/`, `backend/`, `ingestion/`
and both protected modelling datasets returns **empty**. No prior report was rewritten, no prior
conclusion altered, no prior model retrained, no prior dataset modified. The Experiment 8
ERA5/weather measurement audit remains a documented limitation and is **not** retroactively
invalidated by this experiment.

## 24. Amendment policy

The frozen pre-registration is not modified on the basis of these results. Any genuinely necessary
correction must be appended as a **dated amendment** in §21 of that document, preserving the
original text. The labelling defect recorded in §9.1 of this report is documented, not repaired,
for exactly this reason.

---

*Experiment 9 estimated 2026-09-06 at Git HEAD `677ace0` under frozen pre-registration
`a906931309fdc5dd…`. Verdict: SUPPORTED under the pre-registered primary specification, but
specification-fragile.*
