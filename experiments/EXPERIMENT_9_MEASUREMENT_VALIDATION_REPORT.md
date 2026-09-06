# Experiment 9 — Measurement validation report

**Instrument validation and construct feasibility only.** No yield variable was loaded, joined,
correlated, or modelled at any point. Nothing in this document is an effect, a cause, a proof, or
a significant result. No Experiment 1–8 artefact is modified or reinterpreted.

Governed by `experiments/EXPERIMENT_9_MEASUREMENT_PRESPECIFICATION.md`, written before the daily
comparison and before any Tmax construct screen.

---

## 1. Completed validation

### 1.1 Existing IMD rainfall material — verified intact

| Check | Result |
|---|---|
| Files present | **13 / 13** |
| Filenames match committed inventory | **13 / 13** |
| SHA-256 match committed inventory | **13 / 13** |
| Byte sizes match | **13 / 13** |
| `.grd` files in Git history | **0** |
| `.gitignore` still excludes `data/raw/weather/imd_gridded/` | **Yes** (`.gitignore:16`) |

Zero inconsistencies. No repair was needed and none was attempted.

### 1.2 Rainfall disagreement — diagnosis carried forward

The Experiment 8 Tamil Nadu rainfall disagreement was characterised in the preceding phase and is
restated here because it frames the temperature question. It survives **every** control tested:
district size (size-matched AP 0.900 / TG 0.813 / TN 0.453; size coefficient t = 0.10 against
`is_TN` t = −2.84), rainfall amount (regions have near-identical means, 141.0 / 141.7 / 139.9 mm,
and TN is lower in every rainfall bin), aggregation method (centre / nearest / bbox), and spatial
resolution (0.25° → 0.50°).

It is concentrated in the **dry south-west-monsoon months** (TN June r = −0.085, July 0.188)
and best in the wet north-east monsoon (November 0.763) — the reverse of the obvious
north-east-monsoon explanation — and geographically in the Western Ghats rain-shadow interior.
**This remains unresolved as to which product is closer to truth**, because two products cannot
adjudicate each other. That would require a third independent reference.

---

## 2. Newly acquired data

### 2.1 IMD gridded daily maximum temperature

| Field | Value |
|---|---|
| Institution | **India Meteorological Department, Pune** |
| Product | Gridded daily maximum temperature, **1.0° × 1.0°**, binary |
| Source page | `https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html` |
| Retrieval | HTTP POST `maxtemp=<year>` → `https://www.imdpune.gov.in/cmpg/Griddata/maxtemp.php` |
| Retrieval date | **2026-09-04 / 2026-09-05** |
| Official filenames | `MaxT_<year>.GRD` |
| Years | 2000–2012 (13 files) |
| Total size | **18,255,156 bytes (18.3 MB)** |
| Format (verified empirically) | float32 little-endian, (days, 31 lat, 31 lon); lat 7.5–37.5, lon 67.5–97.5 at 1.0° |
| **Missing sentinel** | **99.9** — *differs from the rainfall product's −999.0* |
| Day counts | Correct in all 13 years, including all four leap years |
| Valid range observed | −1.2 °C to 47.6 °C (physically plausible) |
| Storage policy | **CITED-NOT-STORED**, consistent with the Experiment 8 raw-data policy |

Per-file SHA-256 hashes were computed for all 13 files and are reproduced in §7.

### 2.2 ERA5-Land daily maximum temperature

| Field | Value |
|---|---|
| Collection / band | `ECMWF/ERA5_LAND/DAILY_AGGR` / `temperature_2m_max` |
| Units | Kelvin → °C (−273.15) |
| Spatial reduction | District-polygon mean at 11,132 m (ERA5-Land native ~0.1°) |
| Polygons | The **same** geometries used by Experiment 8 |
| Window | 1 June – 30 November, unchanged from Experiment 8 |
| Rows | **73,749** = 31 districts × 13 years × 183 days, **exactly** |
| Nulls | **0** |
| Days per district-year | min 183, max 183 |
| Range | 20.3 °C – 44.6 °C |

**`temperature_2m_max` is fully and reproducibly constructible** for every required district and
year, with no missingness of any kind.

**Acquisition note.** The pull was interrupted twice — once by a wrapper timeout at 19/31
districts, and once by an Earth Engine *"noncommercial compute quota exceeded — restricted mode"*
throttle. The throttle was verified to be a throughput limit rather than a hard block (trivial
requests continued to succeed in ~1.5 s) and the pull was resumed to completion. **No partial
result was reported as complete at any stage**, and no analysis was run until all 31 districts
were present.

### 2.3 Aggregation methodology (fixed in the pre-specification, not after)

IMD cells are assigned to a district by **cell-centre-inside-polygon**, identical to the
Experiment 8 rainfall rule; the district value is the unweighted mean over assigned cells; a
district containing no cell centre uses the **nearest cell to its centroid** and is flagged
`CELL_FALLBACK_NEAREST`. Missing-flagged cells are dropped, never zero-filled.

Observed: mean **1.23** cells per district; **12 of 31** districts required the nearest-cell
fallback. IMD–ERA5 matching succeeded for **73,749 of 73,749** daily pairs (100.0 %).

---

## 3. Measurement findings — ERA5 vs IMD maximum temperature

### 3.1 Pre-specified primary comparison (district-year level)

| Region | Districts | Years | District-years | Within-district r | Mean abs diff | Bias (ERA5 − IMD) |
|---|---:|---:|---:|---:|---:|---:|
| Andhra Pradesh | 10 | 13 | 130 | **0.873** | 1.737 °C | −1.529 °C |
| **Tamil Nadu** | 12 | 13 | 156 | **0.705** | 1.982 °C | −1.242 °C |
| Telangana | 9 | 13 | 117 | **0.818** | 2.116 °C | −2.021 °C |
| **OVERALL** | 31 | 13 | 403 | **0.793** | 1.942 °C | −1.560 °C |

At **daily** resolution (all 73,749 pairs): AP **0.884**, TN **0.841**, TG **0.900**.

### 3.2 Single-cell re-test (pre-specified condition 3b)

Restricted to districts resolving to exactly one 1° IMD cell:

| Region | Districts | Within-district r |
|---|---:|---:|
| Andhra Pradesh | 6 | 0.864 |
| **Tamil Nadu** | 12 | **0.705** |
| Telangana | 6 | 0.796 |

**The Tamil Nadu shortfall survives.** It is not an artefact of the coarse grid.

### 3.3 Regional-evenness determination

Applying the rule fixed in §3 of the pre-specification — both conditions required:

- **(a)** One region materially below the others — **YES.** TN 0.705 against AP 0.873 and TG 0.818.
- **(b)** Shortfall survives the single-cell re-test — **YES.**

# MEASUREMENT-VALIDITY WARNING: RAISED

**It must not be softened, and it must not be overstated.** Against the calibration precedent
recorded in advance — Experiment 8's rainfall case, TN/AP ratio **0.58**, adjudicated a CONFIRMED
limitation — the temperature ratio is **0.81** (0.705 / 0.873), and at daily resolution
**0.95** (0.841 / 0.884). Three further facts bound its severity:

1. **Tamil Nadu's temperature agreement (0.705) exceeds Andhra Pradesh's *rainfall* agreement
   (0.770) only marginally, but its daily-resolution agreement (0.841) exceeds every regional
   rainfall figure in the project.**
2. On **mean absolute difference and bias, Tamil Nadu is not the outlier — Telangana is**
   (2.116 °C and −2.021 °C). This is the opposite of the rainfall pattern, where TN was worst on
   both.
3. ERA5 runs **consistently cooler than IMD in all three regions** (−1.24 to −2.02 °C). A
   systematic offset present everywhere is a calibration difference, not a region-correlated defect.

### 3.4 The shortfall is a terrain belt, not a state

| Region | mean r | min | max |
|---|---:|---:|---:|
| Andhra Pradesh | 0.870 | 0.803 | 0.951 |
| Tamil Nadu | 0.696 | **0.401** | **0.916** |
| Telangana | 0.837 | 0.754 | 0.916 |

The six lowest districts are Coimbatore **0.401**, Erode **0.457**, Madurai **0.463**,
Kanniyakumari **0.544**, Dindigul **0.610**, Karur **0.753** — all Tamil Nadu, and all in the
**Western Ghats rain-shadow / interior belt**. But Tamil Nadu's best district reaches **0.916**,
equal to Telangana's best and close to Andhra Pradesh's.

**This is the same geography that produced the rainfall disagreement.** The defect tracks terrain,
not administrative boundaries; it appears as a "Tamil Nadu effect" only because that terrain lies
inside Tamil Nadu. Monthly agreement is lowest in July for every region (AP 0.774, TN 0.636,
TG 0.781), consistent with monsoon-season cloud and convection degrading both products together.

---

## 4. Construct feasibility screening

All constructs computed from **daily ERA5 Tmax only**. The rejected daily-mean-temperature
versions were **not** revived.

**403 district-years · 31 districts · 13 years · 183 days each · 0 nulls · 0 missing.**
Region coverage: AP 10, TN 12, TG 9. Denominator: none — every construct is an absolute
meteorological quantity with no area, production, or yield term.

| Construct | Unit | Obs | ICC | Within % | KS | SMD | Zero-rate | Screen result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `t_sd_daily_tmax` | °C | 403 | **0.499** | 50.1 % | 0.185 | −0.267 | — | **PASS** |
| `t_range_season_tmax` | °C | 403 | **0.477** | 52.3 % | 0.385 | −0.931 | — | **PASS** |
| `t_p95_tmax` | °C | 403 | **0.611** | 38.9 % | 0.326 | −0.518 | — | **PASS** |
| `tdays_gt32_tmax` | days | 403 | 0.884 | 11.6 % | 0.432 | +0.578 | 4.2 % | **PASS with caution** |
| `tdays_gt30_tmax` | days | 403 | 0.847 | 15.3 % | 0.295 | **−0.012** | **0.0 %** | **PASS** |

No construct exceeds the ICC > 0.90 fingerprint threshold. None approaches the KS ≥ 0.95 or
|SMD| ≥ 3 region-proxy thresholds.

### 4.1 Using true Tmax repaired the binding defect

This is the most consequential result of the phase. The heat-stress counts were **rejected** in
the previous phase for region-correlated zero-inflation when built from daily **mean**
temperature. Rebuilt from actual **daily maximum** temperature:

| Construct | Zero-rate AP / TN / TG | Districts always zero | Season mean |
|---|---|---:|---:|
| `tdays_gt32` **daily-mean** *(rejected)* | 43.8 % / **69.4 %** / 25.9 % | **6 of 31** | 4.7 d |
| `tdays_gt32_tmax` | 0.0 % / **10.3 %** / 0.9 % | **0 of 31** | 54.0 d |
| `tdays_gt30_tmax` | **0.0 % / 0.0 % / 0.0 %** | **0 of 31** | 105.0 d |

`tdays_gt30_tmax` has **no zeros anywhere** (minimum 7 days across all 403 district-years), **no
always-zero districts**, and an SMD of **−0.012** — the regional distributions are almost
indistinguishable. It is the cleanest construct screened in this project to date.

`tdays_gt32_tmax` retains **mild but real region-correlated zero-inflation** (TN 10.3 % against
AP 0.0 % and TG 0.9 %; 17 district-years at zero, 16 of them Tamil Nadu, spread over 4 districts,
none always zero). Under the pre-specified rule this is a **caution, not a clean pass** — far
milder than the defect that rejected the daily-mean version, but the same kind.

### 4.2 One caveat not covered by the screens

`tdays_gt30_tmax` is markedly more dispersed in Tamil Nadu (sd **49.7** days) than in Andhra
Pradesh (22.0) or Telangana (33.0), with a range of 7–170 days. Its *means* are similar across
regions, which is why SMD is near zero, but its *variances* are not. Any future design would need
heteroscedasticity-robust inference; this is a modelling consideration, recorded here so it is
not discovered later.

---

## 5. Rejected candidates

| Candidate | Status | Binding reason |
|---|---|---|
| `tdays_gt32` / `tdays_gt30` from **daily mean** temperature | **REJECTED** *(unchanged)* | Region-correlated zero-inflation, 6 always-zero districts. Not revived. |
| IMD Tmax as a district-level **predictor** | **REJECTED** | 1.0° resolution: 12/31 districts contain no cell centre, 31 districts → 24 distinct cells, 45 % share a cell. Admissible as a validation reference only. |
| Swapping IMD in as the primary **rainfall** product | **REJECTED** | Disagreement between two products does not establish which is correct. A swap relabels the problem rather than resolving it. |
| Satellite phenology, cross-region | **REJECTED** *(unchanged)* | Observation density: TN 17.5 % thin rows against TG 0.9 %. |
| Rabi-season questions | **NOT FEASIBLE** *(unchanged)* | Tamil Nadu Rabi rows = 0. |

---

## 6. Unresolved questions

1. **Which rainfall product is closer to truth in the Ghats rain shadow.** Unanswerable with two
   products. Requires a third independent reference.
2. **Whether the six low-agreement Tamil Nadu districts should be excluded, flagged, or retained**
   in any future temperature design. This is a **scoping decision**, not a measurement question —
   the measurement evidence is now complete, and the choice affects what a future experiment can
   claim. It is not mine to make unilaterally.
3. **Whether the terrain-correlated measurement pattern warrants a separately scoped audit of
   prior experiments** — see §8.

---

## 7. Raw-data inventory and policy

**13 IMD Tmax files, 18,255,156 B (18.3 MB) total.** Per-file: `imd_maxtemp_<year>.grd`,
official name `MaxT_<year>.GRD`, ~1.40 MB each, SHA-256 recorded for all 13 (2000
`9c959ec9129b4edf3952…`, 2001 `e8565453a49fe0741b31…`, 2002 `7c5086161618c597f088…`,
2003 `12ce3042e4809b25fd02…`, 2004 `a66a1adad12f5cb6d132…`, 2005 `7b96f31dcb61b7c849a8…`,
2006 `7926666aae02b20aa1e9…`, 2007 `1b4a760583bae5a9979f…`, 2008 `a80bfd892b2a471d1044…`,
2009 `13db294a906e25cbf484…`, 2010 `7d82ecb95f82a4606f11…`, 2011 `642d337d4aa4ab0c4b16…`,
2012 `0f55a48c4ca1b6558e60…`).

**Reproducibility plan.** All 13 files regenerate from the official IMD Pune endpoint by POSTing
`maxtemp=<year>`; format, grid geometry and the 99.9 sentinel are documented in §2.1. Every
number in §3 and §4 is reproducible from the ERA5 JSON files plus these grids.

**Recommendation (not a decision).** At 18.3 MB the raw files are small enough to commit
comfortably, which would make the temperature validation reproducible without depending on a
government host that has been intermittently unreachable in this project. Consistency with the
Experiment 8 rainfall precedent argues instead for cited-not-stored. **Nothing has been staged
either way.** They are currently untracked and uncommitted.

---

## 8. New audit finding — classification

**Finding.** Two independently constructed measurement systems — ERA5-Land reanalysis and IMD
gauge-interpolated grids — agree materially less well over the Western Ghats rain-shadow interior
of Tamil Nadu, for **both** rainfall (already established) and **maximum temperature** (new,
milder). The pattern tracks terrain rather than administrative boundaries: Tamil Nadu's best
district agrees as well as Andhra Pradesh's and Telangana's best.

**Scope.** This finding **affects the proposed Experiment 9 directly** and must be pre-registered
as a known limitation of any temperature design.

**Whether it requires a separately scoped audit of prior experiments:** it **extends**, and does
not replace, the audit flag already recorded by Experiment 8. Experiment 8 flagged
region-correlated *rainfall* measurement disagreement for prior experiments using the ERA5
rainfall feature. This phase adds that (i) a milder version of the same pattern is present in
temperature, and (ii) the mechanism is better described as terrain-correlated than
region-correlated.

**No prior experiment is invalidated, modified, rerun or reinterpreted by this finding.** The
existing audit question stands unchanged and unanswered, and the recommended amendment is to
widen its wording from "rainfall" to "ERA5-derived weather features" when that separately scoped
audit is eventually commissioned. **That audit is not performed here.**

---

## 9. Recommendations

1. Treat **`t_sd_daily_tmax`, `t_range_season_tmax`, `t_p95_tmax` and `tdays_gt30_tmax`** as the
   surviving candidates. `tdays_gt30_tmax` is the strongest on every screen.
2. Treat **`tdays_gt32_tmax` as a secondary** construct only, with its mild zero-inflation
   documented.
3. Any future design must **pre-register the terrain-correlated measurement limitation up front**,
   with the six low-agreement districts named — the opposite of Experiment 8, where the analogous
   limitation was found only at validation.
4. Resolve unresolved question 2 (exclude / flag / retain those districts) **before** any
   pre-registration is written, since it determines what the experiment can claim.
5. Plan for **heteroscedasticity-robust inference** given the regional variance differences in §4.2.

---

*Measurement validation only. No yield analysis was performed. No Experiment 1–8 artefact was
modified. Nothing committed or pushed.*
