# Experiment 9 — Pre-registration

**Within-season temperature structure as incremental predictive information for Kharif rice yield**

| Field | Value |
|---|---|
| **Pre-registration date** | **2026-09-05** |
| **Git HEAD at writing** | **`677ace08667c3bbd755c499a494fc240dcea1feb`** |
| Outcome dataset | `data/processed/district_multimodal_examples_v2.csv` (unmodified, committed at `fef3ec9`) |
| Panel / exclusion source | `data/processed/experiment8_rainfall_panel.csv` (committed at `677ace0`) |
| Predictor source | `data/raw/weather/era5_tmax_daily/` — 31 files, ERA5-Land `temperature_2m_max` |
| Validation source | `data/raw/weather/imd_maxtemp/` — 13 IMD grids, cited-not-stored |
| Governing validation | `experiments/EXPERIMENT_9_MEASUREMENT_VALIDATION_REPORT.md` |
| Governing measurement spec | `experiments/EXPERIMENT_9_MEASUREMENT_PRESPECIFICATION.md` |

> **This document was created BEFORE any Experiment 9 estimation.** No model has been fitted, no
> predictor–outcome relationship has been estimated, and no coefficient or p-value involving any
> Experiment 9 construct has been computed or observed.

**Anti-hindsight rule.** Once written, this document is not modified on the basis of estimation
results. Any genuinely necessary correction is appended as a dated amendment in §21; the text
above §21 is never silently overwritten.

---

## 1. Research question

> Does **within-season temperature structure** — the shape and variability of daily maximum
> temperature across the Kharif window — contain **predictive information about district rice
> yield beyond the seasonal temperature representation already present in the model**?

The existing model already carries `weather_temp_c_mean`, a single seasonal average of daily mean
temperature (`training/district_dataset.py`, `WEATHER_FEATURES`, in place since Experiment 1). A
season averaging 30 °C evenly and a season averaging 30 °C through alternating cool spells and hot
extremes are identical to that feature. This experiment asks whether the distinction carries
information the average discards.

**This is not asking whether temperature affects yield.** It asks whether *structure* adds to
*level*.

## 2. Hypothesis

**H9 (primary).** Conditional on district fixed effects, year fixed effects, the existing seasonal
mean temperature, and seasonal rainfall total, the within-season standard deviation of daily
maximum temperature (`t_sd_daily_tmax`) is **associated** with Kharif rice yield.

**H9-0 (null).** Its coefficient is zero.

**Language discipline, binding on every output.** Permitted: *predictive association*,
*incremental predictive information*, *accounts for statistical variation*, *associated with*.
Prohibited: *causes*, *proves*, *determines*, *demonstrates the effect of*, *heat damages yield*.
This is an observational panel design; temperature is exogenous to yield, which strengthens the
plausibility of a causal reading but does **not** license one.

## 3. Primary predictor

**`t_sd_daily_tmax`** — standard deviation of daily ERA5-Land `temperature_2m_max` across the
183-day Kharif window, °C.

Chosen over the alternatives on **measured** grounds, fixed here in advance:

| Property | `t_sd_daily_tmax` | `tdays_gt30_tmax` |
|---|---:|---:|
| ICC (lower = less fingerprint-like) | **0.499** | 0.847 |
| Within-district variance | **50.1 %** | 15.3 % |
| Variance surviving two-way FE | **18.8 %** | 8.6 % |
| KS (TN vs AP+TG) | 0.185 | 0.295 |
| SMD | −0.267 | −0.012 |

The measurement-validation report noted `tdays_gt30_tmax` scores best on the *screening* table.
It is nonetheless **not** the primary construct: at ICC 0.847 only 15.3 % of its variance is
within-district and only **8.6 %** survives two-way fixed effects, less than half of
`t_sd_daily_tmax`'s 18.8 %. A construct whose variation is mostly *between* districts is closer to
a district identifier, which is the failure mode that has recurred throughout this project
(soil ICC 1.000; `n_rice_seasons` ICC 1.000; seasonal mean temperature ICC 0.939). Structure
variables are also the direct expression of the research question in §1, whereas a threshold count
imports an arbitrary cutoff.

**Collinearity with the control it must beat**, measured in advance: `corr(t_sd_daily_tmax,
weather_temp_c_mean)` = 0.548 raw, but only **0.150 after two-way fixed effects**. The primary
predictor is therefore near-orthogonal to the existing seasonal representation in the variation
the design actually uses. Correlation with seasonal rainfall total after fixed effects is 0.197.

## 4. Secondary predictors

Tested only if pre-registered here, each in its **own** model with the same specification, and
reported with the multiplicity correction in §14:

1. **`t_range_season_tmax`** — season max minus season min of daily Tmax (°C). ICC 0.477, within 52.3 %, KS 0.385, SMD −0.931.
2. **`t_p95_tmax`** — 95th percentile of daily Tmax (°C). ICC 0.611, within 38.9 %, KS 0.326, SMD −0.518.
3. **`tdays_gt30_tmax`** — count of days with Tmax > 30 °C. ICC 0.847, within 15.3 %, KS 0.295, SMD −0.012, zero-rate 0.0 % in all regions, minimum 7 days.

## 5. Exploratory predictors

**`tdays_gt32_tmax`** — count of days with Tmax > 32 °C. ICC 0.884, within 11.6 %, KS 0.432,
SMD +0.578, **zero-rate 4.2 % overall but region-correlated: AP 0.0 %, TN 10.3 %, TG 0.9 %, with
16 of 17 zero district-years in Tamil Nadu.**

**It may not be promoted to primary or secondary status under any result.** It is reported as
exploratory and cautionary only, because mild region-correlated zero-inflation is the same class
of defect — at lower severity — that disqualified the daily-mean-temperature count constructs.

Any construct not named in §3, §4 or §5 is exploratory by definition and may not be reported as a
finding.

## 6. Outcome

**`final_yield_t_ha`** — Kharif rice yield, tonnes per hectare, taken unchanged from
`district_multimodal_examples_v2.csv`. Identical to the outcome used in Experiments 4–8. No
transformation, winsorization, or trimming.

## 7. Sample definition

Fixed before estimation. The intersection of temperature availability and yield eligibility:

```
ERA5 Tmax constructs available          403 district-years  (31 x 13, complete)
Experiment 8 yield-eligible analytic set 359 district-years
INTERSECTION = EXPERIMENT 9 SAMPLE      359 district-years
```

| Region | Rows | Districts |
|---|---:|---:|
| Andhra Pradesh | 130 | 10 |
| Tamil Nadu | 121 | 12 |
| Telangana | 108 | 9 |
| **Total** | **359** | **31** |

Years: 13 (2000–2012). Season: **Kharif**. Crop: **rice**. Window: **1 June – 30 November**,
183 days per district-year, unchanged from Experiment 8.

44 temperature district-years have no eligible yield row and are dropped. They are lost to the
exclusion rules in §8, not to any property of the outcome.

## 8. Inclusion / exclusion rules

Inherited unchanged from Experiment 8 so the two experiments remain comparable:

| ID | Rule | Effect |
|---|---|---|
| **E1** | Drop rows where the modern district polygon post-dates the yield record's boundary: Dharmapuri < 2004, Coimbatore < 2009, Erode < 2009 | −22 rows |
| **E2** | Drop districts with < 2 observations after E1 (Hyderabad) | −1 row |
| **E3** | **Retain** Krishnagiri and Ariyalur — formed within the window, contributing no pre-formation rows | 0 |
| **E4** | Require complete daily Tmax coverage (183/183 days) | 0 dropped — coverage is complete |

**No exclusion may be introduced on the basis of the outcome, at any stage.** No imputation, no
interpolation, no carry-forward or carry-backward, no state-average substitution, no boundary
redistribution, no fuzzy name matching.

## 9. Feature construction

All constructs are computed from the 183 daily ERA5-Land `temperature_2m_max` values in
1 June – 30 November of year *Y*, district-polygon mean at 11,132 m, converted K → °C by
subtracting 273.15.

```
t_sd_daily_tmax      = sd(Tmax_d),  d in window                       [C]
t_range_season_tmax  = max(Tmax_d) - min(Tmax_d)                      [C]
t_p95_tmax           = 95th percentile of Tmax_d                      [C]
tdays_gt30_tmax      = #{d : Tmax_d > 30}                             [days]
tdays_gt32_tmax      = #{d : Tmax_d > 32}                             [days]
```

**Denominator for the heat-stress counts: none.** They are absolute day counts out of a fixed
183-day window identical for every district-year. No area, production, or yield quantity enters
any construct, so **denominator overlap is structurally impossible**.

Predictors are standardised to unit SD within the analytic sample; coefficients read as t/ha per
1 SD.

**No future-year exposure:** no observation dated after 30 November of year *Y* enters row *Y*.
This is asserted in code, not assumed.

## 10. Fixed effects and controls

```
yield_it = alpha_i + gamma_t
         + delta_1 * weather_temp_c_mean_it      (existing seasonal representation - ALWAYS retained)
         + delta_2 * weather_precip_mm_sum_it    (existing seasonal rainfall - ALWAYS retained)
         + beta * STRUCTURE_it
         + e_it
```

- `alpha_i` — **district fixed effects** (31): within-district identification, eliminating district fingerprinting by construction
- `gamma_t` — **year fixed effects** (13): absorb common national shocks, monsoon-wide years, and the 2000–2012 varietal/input trend

**`weather_temp_c_mean` is never removed from any specification.** The hypothesis is defined as
incremental to it; a model without it would answer a different question. `weather_precip_mm_sum`
is likewise retained throughout, since rainfall and temperature structure co-vary.

**Measured cost of the year fixed effects**, published in advance: only **18.8 %** of
`t_sd_daily_tmax` variance survives two-way FE, against 55.4 % under district FE alone. This power
cost is accepted deliberately — without year effects, any 2000–2012 trend in temperature structure
could be confounded with the yield trend. Robustness arm R1 reports the district-FE-only
specification, but **Arm 0 stands as primary regardless of which is more favourable**.

## 11. Inference procedure

Fixed before estimation; unchanged from Experiments 6 and 8 for cross-experiment comparability.

| Element | Choice |
|---|---|
| Estimator | OLS with two-way fixed effects |
| Clustering | **District** (31 clusters) |
| Heteroskedasticity | CR1 cluster-robust; HC3 reported alongside |
| **Primary p-value** | **Restricted wild cluster bootstrap, Rademacher weights, 9,999 replications, clustered on district** |
| Confidence intervals | From the same bootstrap; CR1 intervals reported alongside |
| Seed | `20260905`, fixed |

**Rationale, recorded in advance:** 31 clusters is too few for asymptotic cluster-robust inference
to be reliable. Experiment 8 demonstrated this concretely — Tamil Nadu's asymptotic χ² p = 0.0001
became a bootstrap p = 0.180 on 12 clusters. The bootstrap is the inference of record; asymptotic
values are reported for transparency and never headlined.

**This matches Experiment 8's procedure, so no deviation rationale is required.** One difference
is noted in advance: Experiment 8's primary test was a 5-df joint Wald test over a block;
Experiment 9's primary test is a **single-coefficient** test, because the hypothesis concerns one
pre-specified construct rather than a block. Bootstrap inference is applied to all robustness arms
from the outset — Experiment 8 applied it to arms only as a disclosed deviation, and adopting it
up front here removes that deviation.

## 12. Effect-size anchors

- **A1 (primary anchor)** — 10 % of the Experiment 4/5 cross-region yield gap = 0.10 × 0.8340 = **0.0834 t/ha per SD**. Retained from Experiments 6 and 8 for comparability.
- **A2 (secondary reference)** — 10 % of the within-district-year yield SD = 0.10 × 0.4439 = **0.0444 t/ha per SD**.

## 13. Primary statistical criterion — a single rule

**Exactly one decision rule governs the primary result:**

> **H9 is SUPPORTED if and only if, in Arm 0, the restricted wild cluster bootstrap p-value for
> `t_sd_daily_tmax` is < 0.05 AND its bootstrap 95 % confidence interval excludes zero AND
> |β| ≥ A1 (0.0834 t/ha per SD).**

All three conditions are required. Outcomes are then classified:

| Outcome | Condition |
|---|---|
| **SUPPORTED** | All three conditions above hold |
| **WEAK ASSOCIATION** | p < 0.05 and CI excludes zero, but \|β\| < A1 |
| **NOT SUPPORTED (precise null)** | p ≥ 0.05 **and** the CI **excludes** A1 — an informative null |
| **INCONCLUSIVE** | p ≥ 0.05 **and** the CI contains **both** 0 and A1 |

**Explicitly barred as substitutes for this rule:** significance in a robustness arm; the
best-performing specification; lowest MAE; highest R²; a favourable coefficient sign alone; a
secondary or exploratory construct reaching significance while the primary does not.

**If H9 is not supported, Experiment 9 is reported as null or inconclusive.** It is not rescued
through secondary specifications, and no secondary or exploratory result may be presented as the
headline finding.

## 14. Multiple-testing procedure

- **Primary (§3):** one test, no correction — this is the pre-registered primary criterion.
- **Secondary (§4):** three tests, **Holm–Bonferroni** across the three. A secondary result may be
  reported as supported only if it survives Holm **and** the primary criterion in §13 was met. If
  the primary is not supported, secondaries are reported as descriptive only.
- **Exploratory (§5):** reported uncorrected and labelled exploratory. Never a finding.

## 15. Robustness arms — fixed in advance

| Arm | Specification | Purpose |
|---|---|---|
| **0** | **Primary**: two-way FE, full 359-row sample | The pre-registered result |
| **R1** | District FE only | Quantifies the power/confounding trade-off in §10 |
| **R2** | District FE + region-specific linear year trends | Middle ground |
| **R3** | **Low-agreement sensitivity** — see §16 | Measurement-limitation subgroup |
| **R4** | Include the 22 E1 boundary rows | Shows E1 is not driving the result |
| **R5** | Balanced panel (districts observed in all 13 years) | Unbalanced-panel sensitivity |
| **R6** | Leave-one-district-out (31 refits) | No single district drives it |
| **R7** | Leave-one-year-out (13 refits) | No single year drives it |
| **R8** | Within-region (AP+TG separately from TN) | **Mandatory** — pooled and within-district correlations have opposite signs in this panel; Simpson's paradox is active |
| **R9** | Drop `weather_temp_c_mean` | Diagnostic **only**: shows how much of the association is incremental. Never the primary. |

Bootstrap inference is applied to every arm.

## 16. Low-agreement-district sensitivity analysis

**Scope decision, adopted and recorded:** **all eligible Tamil Nadu districts are RETAINED in the
primary sample.** The six low-agreement districts are **not** excluded from Arm 0. Observed
ERA5–IMD disagreement is a measurement-quality property, not grounds for removing valid
observations, and excluding them would silently narrow the population the experiment speaks about.

**The pre-specified measurement-limitation subgroup**, taken verbatim from the completed
measurement-validation report and defined **solely** on ERA5–IMD agreement with **no reference
whatsoever to yield**:

| District | ERA5–IMD within-district r | Rows |
|---|---:|---:|
| Coimbatore | 0.401 | 4 |
| Erode | 0.457 | 4 |
| Madurai | 0.463 | 13 |
| Kanniyakumari | 0.544 | 13 |
| Dindigul | 0.610 | 13 |
| **Karur** | **0.753** | 13 |
| **Subgroup total** | | **60** |

**Arm R3** repeats the Arm 0 specification on the remaining **299 rows across 25 districts**.

**Both results are reported.** R3 is a **sensitivity analysis, not a sample-cleaning procedure**.
It may not replace, override, or be substituted for Arm 0 under any outcome. If Arm 0 and R3
disagree, both are reported and Arm 0 remains the primary result.

**Boundary fragility, disclosed in advance.** The subgroup boundary is fragile: Karur (rank 6,
r = 0.753) and Medak (rank 7, Telangana, r = **0.754**) differ by **0.001**. The six-district
membership is adopted because it is the list already published in the validation report, not
because a natural break exists there. **Arm R3b** therefore repeats R3 with Medak additionally
excluded, so the conclusion cannot rest on a one-thousandth difference in a ranking.

## 17. Power analysis — prospective, published before estimation

Computed from the actual Experiment 9 sample structure.

```
N district-years            359
Districts (clusters)         31
Years                        13
Residual df                 312   (N - 31 district FE - 13 year FE - 3 regressors)
Within-district-year SD of yield          0.4439 t/ha
Residualised SD of t_sd_daily_tmax        0.2465 C   (18.8% of raw variance survives two-way FE)
alpha = 0.05 two-sided, power = 0.80
```

**Minimum detectable effect, t/ha per 1 SD of the residualised predictor:**

| Cluster design effect | MDE | vs A1 = 0.0834 | vs A2 = 0.0444 |
|---:|---:|---|---|
| 1.0 | **0.0656** | powered | **underpowered** |
| 1.5 | **0.0804** | powered (marginally) | **underpowered** |
| 2.0 | **0.0928** | **underpowered** | **underpowered** |
| 2.5 | **0.1038** | **underpowered** | **underpowered** |

Sensitivity sample R3 (N = 299, 25 clusters): MDE 0.0711 at DE 1.0, 0.1006 at DE 2.0.

### Adequacy statement — stated plainly, before any result

**This design is MARGINALLY POWERED for anchor A1 and NOT POWERED for anchor A2.** It can detect
an association of 10 % of the cross-region yield gap only if cluster design effects stay at or
below roughly 1.5. Experiment 8 observed design effects of 0.68–1.38 on this same panel, so that
condition is plausible but not guaranteed. **It cannot detect an association at the scale of 10 %
of within-district yield variation at 80 % power under any assumption examined.**

**INCONCLUSIVE is therefore a likely and pre-registered outcome, not a failure.** Experiments 6
and 8 both ended there for exactly this reason. Passing the ICC/KS/SMD screens does not confer
statistical power, and this experiment proceeds with its power limitation stated in advance rather
than discovered afterwards.

## 18. Measurement-validation limitation

ERA5-Land `temperature_2m_max` is **reproducibly constructible for the full sample** —
73,749 of 73,749 daily district observations, zero nulls, 183/183 days for every district-year —
and matches IMD observation coverage at **100 %** of district-days compared.

**ERA5–IMD agreement is not geographically uniform.** Validated values, preserved exactly:

| Level | Andhra Pradesh | Tamil Nadu | Telangana | Overall |
|---|---:|---:|---:|---:|
| **Within-district r** (district-year) | **0.873** | **0.705** | **0.818** | **0.793** |
| **Daily-resolution agreement** | **0.884** | **0.841** | **0.900** | — |

**Classification: a terrain-correlated measurement limitation / calibration difference.**

It is **not** evidence that ERA5 is invalid. Three facts bound it, all measured:

1. **ERA5 runs consistently cooler than IMD in every region** (−1.24 to −2.02 °C). A uniform offset is calibration, not a regional defect.
2. **On mean absolute difference and bias, Telangana is the outlier, not Tamil Nadu** (2.116 °C, −2.021 °C) — the reverse of the rainfall pattern.
3. **The shortfall tracks terrain, not administrative boundaries.** Tamil Nadu's best district reaches r = 0.916, equal to Telangana's best; the six weakest all sit in the Western Ghats rain-shadow interior — the same geography that produced the rainfall disagreement.

Severity relative to the adjudicated precedent: the Experiment 8 rainfall case had a TN/AP ratio
of **0.58** and was classified a CONFIRMED limitation. Here the ratio is **0.81**, and **0.95** at
daily resolution.

**Four levels must be kept distinct in every Experiment 9 output** and must never be conflated:

1. **Construct feasibility** — can the variable be built? *Established: yes.*
2. **ERA5–IMD agreement** — do two independent instruments concur? *Established: substantially, but not uniformly.*
3. **Predictive association** — does the construct carry information about yield? **Untested. This experiment's question.**
4. **Causal interpretation** — does temperature structure change yield? **Out of scope and not addressed by any design here.**

Establishing (1) and (2) says nothing about (3). Establishing (3) would say nothing about (4).

## 19. Missing-data policy

There is no missingness to handle in the predictors: coverage is complete (183/183 days, 31/31
districts, 13/13 years, zero nulls). Should any future re-derivation produce a gap, the affected
district-year is **dropped and counted**, never imputed, interpolated, carried forward, or
zero-filled. Explicit statuses (`OBSERVED`, `DATA_NOT_AVAILABLE`, `BOUNDARY_INCOMPATIBLE`,
`YEAR_NOT_COVERED`) are recorded. A missing value is never a zero — the distinction that matters
for the count constructs, where a genuine zero (0 days above threshold) and an absent observation
are different facts.

## 20. Reproducibility and data provenance

**ERA5-Land `temperature_2m_max`** — `ECMWF/ERA5_LAND/DAILY_AGGR`, ECMWF/Copernicus, district
polygon mean at 11,132 m over the same geometries as every prior pull, 2000–2012, stored at
`data/raw/weather/era5_tmax_daily/` (31 JSON, 4.5 MB).

**IMD gridded daily maximum temperature (validation reference only)** — India Meteorological
Department, Pune; 1.0° × 1.0° binary; `https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html`,
POST `maxtemp=<year>` to `maxtemp.php`; retrieved 2026-09-04/05; official filenames
`MaxT_<year>.GRD`; 13 files, 18,255,156 B; float32 LE (days, 31, 31), lat 7.5–37.5, lon
67.5–97.5; **missing sentinel 99.9** (differs from the rainfall product's −999.0 — a value that
would enter as a 99.9 °C observation if read naively). Per-file SHA-256 recorded in the
measurement-validation report §7.

**Raw-data storage decision: CITED-NOT-STORED**, following the Experiment 8 precedent. The 18.3 MB
is small enough to commit, but no documented reason to depart from the established project
precedent exists, and consistency is worth more than the convenience. Retained: inventory,
filenames, byte sizes, SHA-256 hashes, retrieval metadata, format specification, and the
aggregation methodology — sufficient to reproduce every reported number. **Raw `.grd` files are
not committed.**

**IMD aggregation methodology** — cell-centre-inside-polygon; unweighted mean over assigned cells;
nearest-cell-to-centroid fallback flagged `CELL_FALLBACK_NEAREST` (12 of 31 districts); missing
cells dropped, never zero-filled. **IMD Tmax is a validation reference only and is never a
predictor** — at 1.0° the 31 districts resolve to just 24 distinct cells with 45 % sharing.

## 21. Interpretation boundaries, failure reporting, and amendments

### Interpretation boundaries

- A supported result establishes a **predictive association**, not a causal effect. It must never be reported as proving that heat causes yield loss.
- A null result establishes only that **this design, at this power, on this sample, with this measurement system** could not detect an association at the pre-registered anchor. It must never be reported as proving that temperature structure has no agronomic effect.
- An INCONCLUSIVE result distinguishes neither and must be reported as such.
- Experiment 9 does not test the Experiment 5 cross-region gap question unless Arm R8 supports that extension.

### Failure / null-result reporting rule

If the §13 criterion is not met, the experiment is reported as **NULL** or **INCONCLUSIVE**
according to the §13 table, with the primary coefficient, CI and bootstrap p-value stated
prominently. Secondary and exploratory results are reported as descriptive only. **No
specification search is performed**, and no robustness arm is elevated to primary. Negative and
inconclusive results are valid outputs of this project; fabricated certainty is not.

### Carried-forward audit finding

The terrain-correlated ERA5 disagreement is now observed for **both rainfall and temperature**,
extending the existing Experiment 8 audit concern from rainfall specifically to **ERA5-derived
weather features**. This is a **forward-looking limitation for Experiment 9 only**. It does
**not** invalidate Experiment 8, does not require rerunning it, and does not alter any Experiment
1–8 result or conclusion. The separately scoped audit of prior experiments remains
**FUTURE AUDIT REQUIRED** and is not performed here.

### Amendments

*(none)*

---

*Pre-registered 2026-09-05 at Git HEAD `677ace0`, before any Experiment 9 estimation.*
