# Experiment 8 — Pre-registration

**Kharif rainfall anomaly and intra-seasonal distribution: an incremental-information test**

**This document was committed BEFORE any Experiment 8 data was pulled, any variable was
constructed, any panel was built, and any regression was run.** Its commit precedes the
climatology pull in the repository history. Nothing in it may be altered after results are
seen; changes, if any become necessary, must be recorded as dated amendments below the
signature line in §12, never as edits to the text above it.

Approved at Checkpoint 2. Execution approved at Checkpoint 2 sign-off.

---

## 0. Pre-registration disclosure (integrity statement)

This design was not written blind, and presenting it as blind would be dishonest.

During Checkpoint 1, as a **required leakage diagnostic**, the within-district correlation
between the *existing* seasonal rainfall total and yield was computed (`r = +0.092`), together
with the corresponding NDVI, EVI, NDWI and temperature correlations.

Consequences, stated precisely:

- **`weather_precip_mm_sum` is the baseline control, not a tested variable.** Its association
  with yield has been observed. It is therefore **not eligible to be reported as a finding of
  Experiment 8**.
- **The five tested block variables did not exist when this document was written.** No anomaly,
  rain-day count, dry-spell length, intra-seasonal coefficient of variation, or onset variable
  had ever been computed in this repository. Their relationship to yield was entirely
  unobserved. **The primary test is clean.**
- The outcome's marginal dispersion (within-district standard deviation) was computed for the
  power calculation in §5. **No predictor-outcome relationship for any block variable was
  estimated before this document was committed.**

---

## 1. Primary hypothesis

> **H8:** Within districts, information about the **intra-seasonal distribution and
> climatological anomaly** of Kharif rainfall explains variation in Kharif rice yield
> **beyond** what the seasonal rainfall total (`weather_precip_mm_sum`) already explains.

**H8-0 (null):** the coefficients on all five distribution/anomaly variables are jointly zero,
conditional on the seasonal rainfall total, district fixed effects, and year fixed effects.

This is explicitly **not** a test of whether rainfall affects yield. Seasonal rainfall is
already a model feature in Experiments 1-4 (`training/district_dataset.py`, `WEATHER_FEATURES`),
and its association with yield has already been observed (§0). The question is whether the
seasonal sum **destroys information that matters** — whether 600 mm delivered evenly and 600 mm
delivered in three storms are agronomically different seasons.

---

## 2. Analytic sample

Derived from `data/processed/district_multimodal_examples_v2.csv`, Kharif rice rows with both
weather and satellite available, 2000-2012.

| Step | Rows | Districts |
|---|---|---|
| Starting Kharif panel | 382 | 32 |
| **− E1** boundary-mismatch rows | −22 | — |
| **− E2** singleton districts | −1 | −1 |
| **ANALYTIC SAMPLE** | **359** | **31** |

| Region | Rows | Districts |
|---|---|---|
| Andhra Pradesh | 130 | 10 |
| Telangana | 108 | 9 |
| Tamil Nadu | 121 | 12 |

Years: 13 (2000-2012). Clusters: 31 districts. Residual degrees of freedom: **309**.

### 2.1 Exclusion rules — fixed in advance

| ID | Rule | Rows removed | Justification |
|---|---|---|---|
| **E1** | Drop rows where the modern district polygon post-dates the yield record's boundary: **Dharmapuri < 2004** (Krishnagiri split out, 2004), **Coimbatore < 2009** and **Erode < 2009** (Tiruppur split out, 2009) | **22** | The rainfall value would be measured on a polygon that is not the district the yield refers to. Required by Checkpoint 2 Safeguard 5: these rows are **not silently retained** |
| **E2** | Drop districts with fewer than 2 observations after E1 — **Hyderabad only** (1 year) | **1** | Contributes no within-district variation; would be absorbed by its own fixed effect in any case |
| **E3** | **Retain** Krishnagiri (9 years) and Ariyalur (4 years) | 0 | Both were formed during the window and contribute **no** pre-formation rows; their polygons are valid for every year in which they appear |

Andhra Pradesh and Telangana district boundaries are stable across 2000-2012; the Telangana
10 → 31 district reorganisation took place in October 2016, after the window.

### 2.2 Prohibited operations

No imputation, no interpolation, no carry-forward or carry-backward, no substitution of state
averages for district values, no redistribution of values across district boundaries, and no
fuzzy district-name matching. Any row lacking a required component is **dropped and counted**,
never filled. Missing values are recorded with explicit statuses (`OBSERVED`,
`DATA_NOT_AVAILABLE`, `BOUNDARY_INCOMPATIBLE`, `YEAR_NOT_COVERED`, `UNVERIFIED`) and are never
converted to zero.

---

## 3. Variables

### 3.1 Outcome

`final_yield_t_ha` — Kharif rice yield in tonnes per hectare, unchanged from Experiments 1-6.

### 3.2 Baseline control — retained in every specification

`weather_precip_mm_sum` — the existing Kharif-window (1 June - 30 November) rainfall total.
Present in the null model, the full model, and every robustness arm. It is **never removed**,
because the hypothesis is defined as incremental to it (Safeguard 2).

### 3.3 The tested block — five variables, fixed in advance

All are computed from the existing complete daily series in
`data/raw/weather/districts/D*_weather_daily.csv` (ERA5-Land daily aggregates, district polygon
mean), strictly within 1 June - 30 November of year *Y*.

| # | Variable | Definition | Rationale |
|---|---|---|---|
| 1 | `precip_anomaly_z` | (season total − district 1971-2000 Kharif normal) ÷ district standard deviation over 1971-2000 | Anomaly relative to a strictly prior climatological baseline (Safeguard 4) |
| 2 | `rain_days` | Count of days in the window with precipitation **≥ 2.5 mm** | 2.5 mm is **IMD's own definition of a "rainy day"** — an Indian meteorological convention, not an invented threshold |
| 3 | `max_dry_spell_days` | Longest run of consecutive days with precipitation < 2.5 mm | The agronomically critical quantity: a mid-season break is what fails a rainfed crop, and the seasonal sum cannot see it |
| 4 | `precip_cv_10day` | Standard deviation ÷ mean of rainfall totals across the 18 ten-day blocks of the window | Concentration versus evenness — precisely the information the sum destroys |
| 5 | `onset_day` | Day-of-year on which 7-day cumulative rainfall first reaches 25 mm, searching forward from 1 June | Timing of the sowing window |

**Honesty note on variable 5.** The 25 mm-in-7-days onset rule is a **standard agronomic
convention, not a per-district verified sowing observation.** This is the same honesty standard
already applied to the Kharif window itself in `ingestion/district_season_calendar.py`, whose
docstring states that its windows are "STANDARD CALENDAR CONVENTIONS, not per-district verified
sowing/harvest dates". The convention will be labelled as such wherever `onset_day` is reported.

**The block is capped at five variables and will not be expanded after results are seen.**
Post-hoc addition of variables is the most direct route to a false positive.

### 3.4 Climatological baseline

**1971-2000**, strictly prior to the 2000-2012 panel. The ERA5-Land daily aggregate collection
(`ECMWF/ERA5_LAND/DAILY_AGGR`) spans 1950-01-02 to the present, verified by metadata query at
Checkpoint 1, so this window is retrievable. It shares **zero years** with the panel, therefore
the normal cannot contain information about any year it is used to explain.
**Future-year exposure: none, by construction.**

### 3.5 Explicitly excluded from the primary model

`heat_stress_days` (requires the `temperature_2m_max` band) and soil moisture (requires
`volumetric_soil_water_layer_1`) are **secondary candidates only** (Safeguard 9). Both bands
exist in the collection but have never been pulled, and their district-fingerprint properties
are **predicted, not measured**. They may enter only as a clearly-labelled secondary analysis,
and only after passing the same ICC and region-proxy screens the primary variables must pass.
If they fail those screens, that failure is reported and they are dropped. They will **not** be
promoted into the primary model under any result.

---

## 4. Model specification

### 4.1 Primary — Arm 0

Two-way fixed effects, ordinary least squares:

```
yield_it = alpha_i + gamma_t + delta * precip_total_it + beta' * BLOCK_it + e_it

alpha_i = district fixed effect (31)  -> within-district identification (Safeguard 1)
gamma_t = year fixed effect     (13)  -> absorbs common national and monsoon-wide shocks
BLOCK   = the five variables of section 3.3
```

Block variables are standardised to unit standard deviation within the analytic sample, so
coefficients are interpreted as t/ha per 1 SD.

**Primary test statistic:** cluster-robust **Wald test of H8-0: beta = 0** (5 degrees of
freedom) — the incremental contribution of the block over a model already containing the
seasonal rainfall total and both sets of fixed effects.

**Primary p-value:** **restricted wild cluster bootstrap, Rademacher weights, 9,999
replications**, clustered on district. This matches the procedure used in Experiment 6, and is
used because 31 clusters is too few to rely on asymptotic cluster-robust inference alone. CR1
cluster-robust and HC3 p-values are reported alongside it.

**Secondary outcome:** incremental within-R-squared of the block.

### 4.2 Why two-way fixed effects is primary, and what it costs

Measured at Checkpoint 2, predictor side only:

| Specification | Rainfall variance surviving | Residualised SD |
|---|---|---|
| Raw | 100 % | 272.8 mm |
| District FE only | 48.3 % | 189.7 mm |
| **District + year FE (primary)** | **20.3 %** | **123.0 mm** |

Year fixed effects discard 58 % of the identifying variation that district fixed effects alone
retain. **This power cost is accepted deliberately.** Without year fixed effects, the 2000-2012
trend in yield (variety adoption, input intensification) could be confounded with any trend in
rainfall. The specification that cannot be attacked is chosen over the specification in which an
effect is easier to find.

District-FE-only is pre-registered as Robustness Arm 1. **If the two arms disagree, both are
reported, and the two-way FE result stands as primary regardless of which is more favourable.**

---

## 5. Pre-registered thresholds and power

### 5.1 Effect-size anchors

- **Anchor A1 (primary):** 10 % of the Experiment 4/5 cross-region yield gap
  = 0.10 x 0.8340 = **0.0834 t/ha per SD**. This retains the Experiment 6 convention for
  comparability across experiments.
- **Anchor A2 (secondary reference):** 10 % of the within-district yield standard deviation
  (0.4439) = **0.0444 t/ha per SD** — the more natural scale for a within-district question.

### 5.2 Power, published in advance

Minimum detectable effect, t/ha per SD, 80 % power, alpha = 0.05 two-sided
(check marks indicate powered for anchor A1):

| Specification | Independence | Design effect 1.5 | 2.0 | 2.5 |
|---|---|---|---|---|
| **Primary (two-way FE)** | 0.0656 | 0.0804 (powered) | 0.0928 (under) | 0.1038 (under) |
| Robustness Arm 1 (district FE) | 0.0757 | 0.0927 (under) | 0.1071 (under) | 0.1197 (under) |

**Joint test (the actual primary outcome; 5 numerator df, 309 denominator df):** minimum
detectable Cohen f-squared = **0.0364**, equivalent to an incremental within-R-squared of
approximately **0.031**. This detects a small-to-moderate incremental effect but **cannot**
detect a Cohen-small effect (f-squared = 0.02) at 80 % power.

**Stated plainly, before any result: this design is marginally powered for anchor A1.** If
district-level residual clustering produces a design effect of 2.0 or more, the
single-coefficient tests will be underpowered for A1 — the identical situation that made
Experiment 6 INCONCLUSIVE. The design is comfortably powered for A2. The joint test is the
primary outcome precisely because it carries more power than any individual coefficient.
**INCONCLUSIVE is a pre-registered and genuinely likely outcome of this experiment, not a
disappointment.**

### 5.3 Decision rules — fixed before estimation

| Outcome | Criteria (all must hold) |
|---|---|
| **MEANINGFUL SUPPORT** | Joint wild-bootstrap p < 0.05 **AND** incremental within-R-squared >= 0.031 **AND** at least one coefficient with absolute value >= A1 whose confidence interval excludes 0 **AND** sign agronomically coherent (longer dry spell -> lower yield; later onset -> lower yield) **AND** consistent across Arms 1-5 **AND** no leakage screen failure |
| **WEAK SUPPORT** | Joint p < 0.05, but the effect lies between A2 and A1, or is not stable across arms |
| **NO SUPPORT (precise null)** | Joint p >= 0.05 **AND** the confidence interval on every block coefficient **excludes A1** — a genuine, informative null |
| **INCONCLUSIVE** | Joint p >= 0.05 **AND** any confidence interval contains **both 0 and A1** — cannot distinguish no effect from a meaningful one |

**Multiplicity.** The joint 5-df test is the primary outcome and requires no correction.
Individual coefficients are secondary and are reported with **Holm-Bonferroni** correction
across the five. **No individual coefficient may be promoted to a headline finding if the joint
test does not reject.**

---

## 6. Robustness arms — fixed in advance

| Arm | Specification | Purpose |
|---|---|---|
| **1** | District FE only (no year FE) | The power / confounding trade-off quantified in §4.2 |
| **2** | District FE + region-specific linear year trends | Middle ground between Arms 0 and 1 |
| **3** | **Include** the 22 E1 boundary-mismatch rows | Demonstrates E1 is not driving the result (Safeguard 5) |
| **4** | Balanced panel only (districts observed in all 13 years, n = 20) | Unbalanced-panel sensitivity |
| **5** | Leave-one-district-out (31 refits) | No single district drives the result |
| **6** | Leave-one-year-out (13 refits) | No single monsoon year (e.g. the 2002 all-India drought) drives the result |
| **7** | 1 mm rain-day threshold in place of 2.5 mm | Threshold sensitivity for variables 2 and 3 |
| **8** | Within-region only (AP+TG estimated separately from TN) | **Mandatory.** Pooled and within-district correlations have opposite signs in this panel; Simpson's paradox is active and was confirmed at Checkpoint 1 |

---

## 7. IMD independent validation

ERA5-Land is a **reanalysis** (Tier 2 under the project source hierarchy), not gauge
observation. IMD's 0.25-degree gridded rainfall product
(`https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html`, 1950-2025, HTTP 200 verified
at Checkpoint 1) is **Tier 1 official** and covers the full window.

**Its role is an independent cross-check, not a replacement.** ERA5-Land remains primary because
its district aggregation is already implemented, documented and reproducible in this repository
(`ingestion/district_weather_pull.py`); substituting IMD would require a new aggregation method
whose only validation would be the very comparison being made.

**Procedure.** Aggregate IMD gridded rainfall to the same 31 district polygons by the same
documented method, compute the Kharif-window total, and report the district-level correlation
and mean bias against ERA5-Land — **separately by region**.

**Interpretation, fixed in advance:**

- If the two products agree comparably well in all three regions, the variable is not an
  artefact of a single product.
- **If agreement is systematically worse in one region, that is a region-correlated
  measurement-quality defect** — structurally the same failure mode that made Experiment 7 not
  feasible — and it will be reported as a threat to the cross-region interpretation, not buried.

This validation is reported whatever it shows. It does not gate the primary analysis, which is
pre-specified on ERA5-Land.

---

## 8. Leakage controls — verified at build time, not assumed

| Risk | Control |
|---|---|
| **Target leakage** | Assertion that no block variable's construction touches yield, production, area or productivity. Structural check that `final_yield_t_ha` never enters feature construction |
| **Future-year exposure** | Hard assertion that **no daily observation dated after 30 November of year Y** enters row Y; climatological baseline strictly 1971-2000 |
| **District fingerprinting** | **ICC computed and published for all five block variables.** Any variable with **ICC > 0.90** is reported as a fingerprint and **excluded from the primary model** — the rule that disqualified seasonal mean temperature (ICC = 0.939) at Checkpoint 1 |
| **Region proxy** | Standing project screen (**KS >= 0.95 or absolute SMD >= 3**) applied to all five. Any variable that fails is excluded from cross-region interpretation |
| **Boundary leakage** | E1 applied; Arm 3 tests its influence |
| **Denominator overlap** | None possible — rainfall is a physical depth with no denominator, and no rice area or production enters its construction |
| **Reverse causality** | None — rainfall is meteorologically exogenous. Yield cannot cause monsoon rainfall. This is reported as the design's principal advantage over Experiments 5-7, all of which studied farmer decisions that respond to expected output |
| **Simpson's paradox** | Arm 8 is mandatory |

---

## 9. Protected paths

**Files that will be created:**

```
ingestion/era5_climatology_pull.py
ingestion/kharif_rainfall_features.py
ingestion/imd_gridded_validation.py
experiments/run_experiment8_analysis.py
data/raw/weather/climatology_1971_2000/
data/processed/experiment8_rainfall_panel.csv     <- a SEPARATE file
experiments/EXPERIMENT_8_RAINFALL_REPORT.md
experiments/EXPERIMENT_8_LEAKAGE_AUDIT.md
experiments/experiment8_results.json
```

**Files that will NOT be modified:**

```
data/processed/district_multimodal_examples.csv
data/processed/district_multimodal_examples_v2.csv
training/          models/          backend/
every Experiment 1-7 report, script, dataset, result file and figure
```

New variables are **not** merged into the main modelling datasets (Safeguard 6). Compliance is
verified with `git diff` before and after execution.

---

## 10. Declared limitations — to appear in the report regardless of outcome

1. **The seasonal rainfall total's association with yield was observed at Checkpoint 1** and is
   therefore not a finding of this experiment.
2. **The design is marginally powered for anchor A1**, as stated in advance in §5.2.
3. **ERA5-Land is a reanalysis**, not gauge observation; the IMD comparison in §7 is the check
   on this.
4. **The Kharif window and the onset rule are conventions**, not per-district verified sowing
   dates.
5. **Causal language is prohibited.** Only "associated with" and "accounts for statistical
   variation" are permitted. Rainfall's exogeneity strengthens the causal interpretation but the
   design remains observational.
6. **Experiment 8 does not test the Experiment 5 cross-region gap question** unless Arm 8
   supports that extension.

---

## 11. Execution order

1. **Commit this pre-registration** — before any data construction.
2. Pull the 1971-2000 ERA5-Land climatology (31 districts x 30 years).
3. Construct only the five pre-registered block variables.
4. Run and publish the ICC and region-proxy diagnostics for all five.
5. **Only variables passing those screens enter the primary model.**
6. Apply exclusion rules E1-E3 and build the separate Experiment 8 panel.
7. Run Arm 0 **exactly once**.
8. Run robustness Arms 1-8 exactly as specified.
9. Perform the IMD independent validation.
10. Apply the §5.3 decision rules **without changing thresholds, variables, exclusions or
    specifications after seeing results.**

---

## 12. Signature

Pre-registered at Checkpoint 2, Experiment 8, on the HarvestWise project.

Committed before the climatology pull, before variable construction, before panel construction,
and before any regression. Verified by this document's position in the repository history: the
commit containing this file precedes every Experiment 8 data and analysis commit.

**Amendments (if any) must be appended below this line with a date and a reason. The text above
this line must not be edited after results are seen.**

*(no amendments)*
