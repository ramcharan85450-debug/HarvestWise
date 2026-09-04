# EXPERIMENT 8 — Kharif Rainfall Anomaly and Intra-Seasonal Distribution

# FINAL VERDICT: INCONCLUSIVE

**Primary objective.** Test whether rainfall anomaly and intra-seasonal rainfall-distribution
information explains within-district Kharif rice yield variation **beyond the existing seasonal
rainfall total**.

**Pre-registration:** `experiments/EXPERIMENT_8_PREREGISTRATION.md`, committed as **`04441c5`**
before any data was pulled, any variable constructed, any panel built, or any regression run.

---

## 1. What this experiment asked, and what it did not

**H8 (pre-registered):**

> Within districts, information about the **intra-seasonal distribution and climatological
> anomaly** of Kharif rainfall explains variation in Kharif rice yield **beyond** what the
> seasonal rainfall total (`weather_precip_mm_sum`) already explains.

This experiment is explicitly **NOT** asking *"does rainfall affect yield?"* The seasonal
rainfall total has been a model feature since Experiment 1
(`training/district_dataset.py`, `WEATHER_FEATURES`), and its association with yield had already
been inspected. The question is narrower and harder:

> **Does information destroyed by seasonal aggregation add explanatory value beyond the seasonal
> total?**

Two seasons each totalling 600 mm — one spread evenly, one delivered in three storms — are
identical to the existing feature. The five tested variables are the ones that can tell them
apart:

1. `precip_anomaly_z` — deviation from the district's own 1971-2000 Kharif normal, in SD units
2. `rain_days` — days with precipitation >= 2.5 mm (IMD's definition of a rainy day)
3. `max_dry_spell_days` — longest run of consecutive days below 2.5 mm
4. `precip_cv_10day` — coefficient of variation of the mean daily rate across 18 ten-day blocks
5. `onset_day` — day-of-year on which forward 7-day cumulative rainfall first reaches 25 mm

---

## 2. Pre-registration integrity

| Item | Status |
|---|---|
| Pre-registration committed before data construction | **Yes — commit `04441c5`** |
| Primary variables specified in advance | **Yes** — the five above; the block was capped at five and was not expanded |
| Exclusion rules specified in advance | **Yes** — E1, E2, E3 (§3) |
| Model specification specified in advance | **Yes** — two-way FE, seasonal total always retained |
| Decision thresholds specified in advance | **Yes** — anchor A1 = 0.0834 t/ha per SD, incremental within-R² >= 0.031, joint p < 0.05 |
| Inference procedure specified in advance | **Yes** — restricted wild cluster bootstrap, Rademacher, 9,999 reps, clustered on district |
| Power published in advance | **Yes** — the design was declared marginally powered for A1 *before* results |

### 2.1 Disclosure — the design was not completely blind

This is stated plainly rather than buried. During Checkpoint 1, as a **required leakage
diagnostic**, the within-district correlation between the *existing seasonal rainfall total* and
yield was computed (`r = +0.092`), along with the NDVI, EVI, NDWI and temperature correlations.

What this does and does not compromise:

- `weather_precip_mm_sum` is a **baseline control, not the tested variable.** Its association with
  yield has been observed and is therefore **not eligible to be reported as a finding of
  Experiment 8**.
- **The five tested variables had never been computed** in this repository when the
  pre-registration was written. No anomaly, rain-day count, dry-spell length, intra-seasonal CV
  or onset variable existed. **Their predictor-outcome relationships had not been estimated.**
  The primary test is clean.
- The outcome's marginal within-district dispersion was computed for the power calculation only.

---

## 3. Analytic sample

```
Initial panel:        382 district-years
Boundary exclusions:  -22   (E1)
Singleton exclusion:   -1   (E2)

Final sample:         359 district-years
Districts:             31
Years:                 13   (2000-2012)
Regions:                3
```

| Region | Rows | Districts |
|---|---|---|
| Andhra Pradesh | 130 | 10 |
| Tamil Nadu | 121 | 12 |
| Telangana | 108 | 9 |

### Exclusion rules, applied exactly as pre-registered

**E1 — boundary mismatch (22 rows dropped).** Rows where the modern district polygon post-dates
the district boundary the yield record represents: **Dharmapuri < 2004** (Krishnagiri split out
in 2004), **Coimbatore < 2009** and **Erode < 2009** (Tiruppur split out in 2009). In these rows
the rainfall would be measured over a polygon that is not the district the yield refers to.

**E2 — singleton (1 row dropped).** Hyderabad contributes only one observation after E1 and
therefore no within-district variation; it would be absorbed by its own fixed effect regardless.

**E3 — retained.** Krishnagiri (9 years) and Ariyalur (4 years) are **kept**. Both were formed
during the window and contribute **no** pre-formation observations, so their polygons are valid
for every year in which they appear.

> **No imputation, interpolation, carry-forward, state-average substitution or boundary
> redistribution was used.** Any row lacking a required component was dropped and counted, never
> filled. No missing value was converted to zero.

Andhra Pradesh and Telangana district boundaries are stable across 2000-2012; the Telangana
10 -> 31 district reorganisation occurred in October 2016, after the window.

---

## 4. Data construction validation

> **The recomputed Kharif seasonal rainfall total reproduced the existing
> `weather_precip_mm_sum` feature to within 0.005 mm across all 382 rows.**

This is the strongest reproducibility check in the experiment, and it matters for a specific
reason:

> The daily weather window used to construct Experiment 8 is **empirically verified** to reproduce
> the repository's existing seasonal rainfall pipeline, rather than merely *assuming* that the two
> implementations use the same temporal definition.

Had the windows differed even slightly, every one of the five variables would have been computed
over a different span than the control they are tested against, and the incremental test would
have been meaningless. The 0.005 mm agreement is rounding, not tolerance.

Supporting coverage facts:

- Daily weather: **2,379 of 2,379 Kharif days for 32 of 32 districts. Zero missing.**
- 1971-2000 climatology: **32/32 districts, 30/30 years each, 183 days per window, zero nulls,
  zero pull failures.**
- All 382 feature rows returned status `OBSERVED`; every anomaly computed, every onset reached.

The climatological normals are agronomically coherent: Anantapur lowest in AP at 485 mm (the
Rayalaseema rain shadow), Srikakulam highest at 1,049 mm (coastal north), Karur lowest in TN at
470 mm, Khammam highest in TG at 1,032 mm.

---

## 5. Variable validation screens

Published **before any model was fitted**, so the exclusion rule could not be chosen to suit a
result.

| Variable | ICC | Within-district variance | KS | SMD | Verdict |
|---|---:|---:|---:|---:|---|
| `precip_anomaly_z` | 0.107 | 89.3 % | 0.243 | +0.448 | **PASS** |
| `rain_days` | 0.515 | 48.5 % | 0.086 | +0.161 | **PASS** |
| `max_dry_spell_days` | 0.337 | 66.3 % | 0.347 | −0.817 | **PASS** |
| `precip_cv_10day` | 0.370 | 63.0 % | 0.213 | −0.280 | **PASS** |
| `onset_day` | 0.357 | 64.3 % | 0.171 | +0.390 | **PASS** |

Screens: a variable with **ICC > 0.90** is a district fingerprint and is excluded from the
primary model; a variable failing **KS >= 0.95 or |SMD| >= 3** is excluded from cross-region
interpretation.

> **All five variables passed the pre-specified district-fingerprinting and region-proxy screens.
> No variable was excluded from the primary block.**

> **`precip_anomaly_z` has ICC = 0.107 and is therefore strongly time-varying within districts** —
> 89.3 % of its variance is within-district. It is the least fingerprint-like variable in this
> project, against soil at ICC = 1.000 and seasonal mean temperature at ICC = 0.939 (the latter
> disqualified at Checkpoint 1 for exactly this reason). This is expected: the anomaly removes the
> district mean by construction.

---

## 6. Primary model

```
yield_it =  district fixed effect
          + year fixed effect
          + seasonal precipitation total   (weather_precip_mm_sum, RETAINED)
          + five-variable rainfall block
          + error
```

**Identification strategy:** within-district variation, with year fixed effects absorbing common
year-level shocks (national monsoon events, price and policy years, variety-adoption trend).

**The baseline seasonal rainfall total is retained in the model**, in the null model, in the full
model, and in every robustness arm. It is never removed — the hypothesis is defined as
incremental to it.

Block variables are standardised to unit SD within the analytic sample, so coefficients read as
t/ha per 1 SD.

**Primary test:** cluster-robust joint Wald test (5 df) of the null that every block coefficient
is zero, with the **restricted wild cluster bootstrap (Rademacher, 9,999 replications, clustered
on district)** as the pre-registered p-value of record. 31 clusters is too few to rely on
asymptotic inference alone.

**Why two-way FE was primary despite its cost**, recorded in advance: year fixed effects discard
58 % of the identifying variation that district fixed effects alone retain (residualised rainfall
SD falls from 189.7 mm to 123.0 mm). That power cost was accepted deliberately, because without
year fixed effects the 2000-2012 yield trend could be confounded with any trend in rainfall. The
specification that cannot be attacked was chosen over the one in which an effect is easier to
find.

---

## 7. Primary results

```
Joint Wald statistic (5 df):        7.658
Asymptotic chi-2 p-value:           0.1761
Wild cluster bootstrap p-value:     0.3418     <- pre-registered inference of record

Incremental within-R2:              0.0273
Pre-registered R2 threshold:        0.031
```

| Variable | β (t/ha per SD) | Cluster SE | 95 % CI | Holm-adjusted p |
|---|---:|---:|---|---:|
| `precip_anomaly_z` | +0.0294 | 0.1689 | [−0.3155, +0.3744] | 1.000 |
| `rain_days` | +0.1568 | 0.0923 | [−0.0318, +0.3453] | 0.499 |
| `max_dry_spell_days` | −0.0398 | 0.0271 | [−0.0953, +0.0156] | 0.611 |
| `precip_cv_10day` | −0.0197 | 0.0556 | [−0.1334, +0.0939] | 1.000 |
| `onset_day` | +0.0298 | 0.0309 | [−0.0333, +0.0929] | 1.000 |

### 7.1 One thing went better than pre-registered

The cluster design effects (cluster SE / iid SE) came in at **0.68 to 1.38**, not the 2.0-2.5
that the pre-registered power table warned about. **Clustering did not inflate the standard
errors.** The realised precision therefore sits at the favourable end of the published power
range. `max_dry_spell_days` reaches a minimum detectable effect of 0.076 t/ha per SD, below anchor
A1 = 0.0834, and still returns a null.

This is worth stating because it removes the easiest excuse: the result is not simply an artefact
of the clustering penalty being worse than expected. It was better than expected, and the joint
test still did not reject.

---

## 8. Primary decision — applying the pre-registered rules

| Criterion | Required | Observed | Met? |
|---|---|---|---|
| Joint bootstrap p | < 0.05 | **0.3418** | No |
| Incremental within-R² | >= 0.031 | **0.0273** | No |
| At least one coefficient >= A1 with CI excluding 0 | Yes | None | No |
| All CIs exclude A1 (precise-null route) | Yes | **No** — every CI contains A1 | No |
| Some CI contains both 0 and A1 | — | **Yes** | INCONCLUSIVE trigger |

# PRIMARY OUTCOME: INCONCLUSIVE

- The joint bootstrap p-value is **not below 0.05**.
- The incremental within-R² **does not reach 0.031**.
- The confidence intervals **do not establish meaningful support** — none reaches anchor A1 with
  an interval excluding zero.
- The experiment **cannot establish a precise null** across the tested block either: all five
  confidence intervals still contain A1, so a meaningful effect has not been ruled out.

This is **not** "no effect", and it is **not** "weak support". Both would misstate the evidence.
The verdict is INCONCLUSIVE.

---

## 9. Maximum dry-spell duration — the strongest coherent pattern

`max_dry_spell_days` deserves separate discussion because it is the one thread in this experiment
that holds together. The following are all true:

- The coefficient is **negative** (−0.0398 t/ha per SD).
- The direction is **agronomically coherent**: longer dry spells correspond to lower estimated
  yield. A mid-season break is the classic failure mode of a rainfed Kharif crop, and it is
  precisely the information a seasonal total cannot see.
- The **sign is stable across all 31 leave-one-district-out refits** (range −0.0550 to −0.0279).
  No single district produces it.
- The variable was **adequately powered for anchor A1** (MDE = 0.076 < 0.0834).
- The **confidence interval includes zero**: [−0.0953, +0.0156].
- Holm-adjusted p = 0.611.

> **This is the strongest coherent pattern in the experiment, but it is not a confirmed effect.**

It is **not** a discovery, and it is **not** statistically significant. It is reported here
because an agronomically correct, leave-one-out-stable sign is worth recording for whoever
designs the next experiment — as a lead, not as a result. The sign is *not* stable across
leave-one-year-out refits (range −0.0724 to +0.0070), which further weakens any claim.

---

## 10. Robustness results

| Arm | Specification | n | Clusters | χ² p | Bootstrap p |
|---|---|---:|---:|---:|---:|
| **0** | **Primary two-way FE** | 359 | 31 | 0.176 | **0.342** |
| 1 | District FE only | 359 | 31 | 0.019 | 0.052 |
| 2 | Region-specific trends | 359 | 31 | 0.006 | 0.030 |
| 3 | Include boundary rows | 381 | 31 | 0.724 | 0.772 |
| 4 | Balanced panel | 221 | 17 | 0.0000 | 0.002 |
| 7 | 1 mm rain-day threshold | 359 | 31 | 0.519 | 0.637 |
| 8 | AP + TG | 238 | 19 | 0.666 | 0.751 |
| 8 | Tamil Nadu | 121 | 12 | 0.0001 | 0.180 |

*(Arms 5 and 6 are leave-one-out refits, reported in §9 and in `experiment8_results.json`.)*

> **The robustness specifications are highly unstable.**

The spread is not marginal — it runs from p = 0.002 to p = 0.772 across defensible
specifications of the same hypothesis on the same data:

- **Primary p = 0.342**
- **Balanced panel p = 0.002**
- **Boundary inclusion p = 0.772**
- **1 mm threshold p = 0.637**

Two of these are particularly telling. Adding back 22 rows (Arm 3) moves the joint p from 0.342
to 0.772 — a genuine effect should not be destroyed by 6 % more data. Changing the rain-day
threshold from 2.5 mm to 1 mm (Arm 7) moves it to 0.637 — a genuine effect should not hinge on
which of two conventional thresholds defines a rainy day.

> **The result is highly specification-sensitive and does not provide stable evidence of a robust
> effect.**

---

## 11. Procedural deviation from the pre-registration

> **Wild cluster bootstrap inference was applied to every robustness arm, although this was not
> explicitly specified in the pre-registration.**

This is disclosed, not hidden. The details:

- **The primary Arm 0 procedure remained exactly as pre-registered** — restricted wild cluster
  bootstrap, Rademacher weights, 9,999 replications, clustered on district. The primary result is
  unaffected by this deviation.
- The pre-registration fixed the bootstrap only for the primary test and specified asymptotic
  values as reported "alongside". Bootstrap inference was **additionally** applied to the
  robustness arms (1,999 replications each).
- **Both asymptotic and bootstrap values are reported for every arm.** Neither is suppressed.
- The motivation is a **known statistical property, not the results**: chi-squared p-values are
  anti-conservative when the number of clusters is small, and the arms that rejected are exactly
  those with the fewest clusters.
- **The change makes inference more conservative in small-cluster settings**, not less. It moves
  results away from significance, not toward it.

**This report does not claim the robustness bootstrap procedure was pre-registered.** It was not.

---

## 12. The Tamil Nadu few-cluster result

```
Tamil Nadu (Arm 8):
    Asymptotic chi-2 p-value:   0.0001
    Wild bootstrap p-value:     0.180
    Clusters:                   12
```

> **The apparent strong Tamil Nadu result does not survive the more appropriate few-cluster
> inference.**

With only 12 clusters, the asymptotic chi-squared reference distribution is badly
anti-conservative, and the correction is dramatic: p moves from 0.0001 to 0.180 — from
"overwhelming" to "not significant".

**This report explicitly warns against interpreting p = 0.0001 as evidence of a confirmed Tamil
Nadu effect.** It is not. Had the asymptotic value been reported as the headline, this experiment
would have claimed a strong regional rainfall effect that correct inference does not support.

The asymptotic value is recorded only for transparency and for the methodological lesson it
carries.

---

## 13. IMD independent validation

ERA5-Land is a **reanalysis** (Tier 2 under the project source hierarchy) — a physical model
constrained by observations, not a gauge network. The Experiment 8 design rests on rainfall being
measured comparably across all three regions; that is precisely the property whose absence made
Experiment 7 not feasible. **A single product cannot demonstrate its own regional evenness.**

IMD's gridded rainfall is **Tier 1 official**, built from a gauge network by a different
institution using a different method, and covers the full window. Both products were reduced over
**identical district polygons** — the same Earth Engine geometries the ERA5-Land pull used.

| Region | n | Within-district correlation | Mean absolute difference | ERA5 − IMD bias |
|---|---:|---:|---:|---:|
| Andhra Pradesh | 130 | **0.770** | 154 mm | +61 mm |
| Telangana | 108 | **0.751** | 129 mm | +67 mm |
| **Tamil Nadu** | 121 | **0.446** | **254 mm** | −15 mm |

```
Overall within-district correlation: 0.615
Overall Pearson correlation:         0.662
```

# Tamil Nadu triggers the pre-registered measurement warning condition.

The independent products agree substantially better in **Andhra Pradesh** and **Telangana** than
in **Tamil Nadu**. Tamil Nadu has:

- substantially **lower within-district agreement** (0.446 against 0.770 and 0.751);
- substantially **larger mean absolute disagreement** (254 mm against 154 mm and 129 mm — roughly
  double Telangana's).

The within-district correlation is the relevant statistic, because within-district year-to-year
movement is exactly what this experiment identifies from.

Coverage note: one district (Hyderabad) was smaller than a 0.25 degree cell and used the
documented `CELL_FALLBACK_NEAREST` rule. Hyderabad is excluded by E2, so **the analytic sample
contains zero fallback districts.**

### 13.1 Required interpretation

> **The weaker ERA5-Land versus IMD agreement in Tamil Nadu represents a region-correlated
> measurement-quality limitation.**

This limitation is not hidden and is not a footnote. It affects cross-region interpretation, and
it is especially important because **Tamil Nadu was also the region carrying the apparent
asymptotic signal** (§12). The one region where an effect appeared is the one region where the
rainfall variable is least trustworthy.

Structurally this is the Experiment 7 failure mode arriving by a different route: a
region-correlated measurement property confounded with the regional contrast — there through a
reporting convention, here through reanalysis skill.

There is a physically coherent explanation. Tamil Nadu's rainfall is dominated by the northeast
monsoon and by localised coastal and Western Ghats convection, which reanalysis reproduces less
faithfully than the broad southwest monsoon, and the 1 June - 30 November Kharif window truncates
the northeast monsoon. That explains the disagreement; it does not repair it.

**What this report does NOT claim:**

- It does **not** claim Experiment 8 proves ERA5 is wrong.
- It does **not** claim IMD is automatically ground truth.

**The correct interpretation is:**

> Two independently constructed rainfall products show materially weaker agreement in Tamil Nadu
> than in Andhra Pradesh and Telangana, creating evidence of region-correlated measurement
> disagreement.

---

## 14. Potential Implication for Earlier Experiments — Audit Flag Only

> The identified Tamil Nadu measurement disagreement creates a **potential inherited
> measurement-validity question** for prior experiments that materially used the same
> ERA5-derived rainfall feature.

> **Experiment 8 does not retrospectively invalidate Experiments 2, 4 or 5.**

Accordingly, and by explicit decision:

- **No previous experiment is modified.**
- **No previous result is changed.**
- **No previous model is rerun.**
- **No previous report is edited.**
- **No previous conclusion is reinterpreted.**

Experiment 8 alone does not provide sufficient evidence to retrospectively invalidate earlier
work. It establishes a measurement property that earlier work did not test for, which is a reason
to *ask a question*, not to withdraw a result.

**The required future question, recorded for separate scoping:**

> **Does region-correlated ERA5 rainfall measurement disagreement materially affect conclusions in
> previous experiments that relied materially on the ERA5-derived rainfall feature?**

Status:

```
FUTURE AUDIT REQUIRED
```

**not**

```
PREVIOUS EXPERIMENTS INVALID
```

That audit is **not performed here** and is out of scope for Experiment 8. It must be
commissioned as a separately approved investigation.

---

## 15. Limitations

**Limitation 1 — Existing rainfall total.** The association between the existing seasonal rainfall
total and yield had previously been inspected as a leakage diagnostic (Checkpoint 1). It is a
baseline control, and **it is not a new finding of Experiment 8.**

**Limitation 2 — Power.** The design was declared **marginally powered for anchor A1 in advance**.
Realised design effects were better than the worst case (0.68-1.38), but several individual
coefficients remain imprecise — `precip_anomaly_z` in particular has a confidence interval
spanning ±0.37 t/ha per SD, which is uninformative at the scale of interest.

**Limitation 3 — ERA5-Land measurement.** ERA5-Land is a reanalysis rather than direct gauge
observation. It is a physical model constrained by assimilated data, and its skill varies by
region and by rainfall regime.

**Limitation 4 — Tamil Nadu measurement disagreement.** Independent IMD validation found
substantially weaker agreement in Tamil Nadu (within-district r = 0.446) than in Andhra Pradesh
(0.770) or Telangana (0.751). **This limits cross-region interpretation** and is the most
consequential limitation in this experiment.

**Limitation 5 — Kharif calendar.** The 1 June - 30 November window is a **standard agricultural
convention**, not a per-district verified sowing calendar. It is inherited unchanged from
`ingestion/district_season_calendar.py`, whose own docstring states the same caveat.

**Limitation 6 — Onset definition.** The 25 mm / 7-day onset rule is an **agronomic convention,
not observed sowing timing.** No per-district sowing dates were available.

**Limitation 7 — Observational design.** Rainfall is meteorologically exogenous to yield, which
is a genuine strength relative to Experiments 5-7 (irrigation and fertilizer are both farmer
decisions responsive to expected output). The design nevertheless remains **observational**, and
causal language is prohibited throughout. Permitted: *associated with*, *explains statistical
variation*, *incremental explanatory value*. Not permitted: *causes*, *proves*, *determines*.

**Additional note — Simpson's paradox.** Pooled and within-district correlations have opposite
signs for every variable examined in this panel. All reported estimates are within-district;
pooled estimates would be misleading and none is reported.

---

## 16. Conclusion

> **Experiment 8 is INCONCLUSIVE.**
>
> The pre-registered primary analysis does not provide meaningful support for the hypothesis that
> climatological rainfall anomaly and intra-seasonal rainfall distribution explain Kharif rice
> yield variation beyond the existing seasonal rainfall total. The joint five-variable block is
> not statistically significant under the pre-registered wild cluster bootstrap procedure
> (p = 0.3418), and the incremental within-R² (0.0273) does not reach the pre-registered threshold
> (0.031).
>
> The result does not establish that intra-seasonal rainfall structure is irrelevant to rice
> yield. The robustness analyses are highly specification-sensitive, ranging from p = 0.002 to
> p = 0.772 across defensible specifications, and several estimates remain imprecise.
>
> Maximum dry-spell duration provides the strongest agronomically coherent pattern, with a
> negative and leave-one-district-out stable coefficient, but the estimate remains statistically
> indistinguishable from zero.
>
> Independent validation against IMD gridded rainfall identifies an additional
> measurement-validity limitation: ERA5-Land and IMD agree substantially less well in Tamil Nadu
> (within-district r = 0.446) than in Andhra Pradesh (0.770) and Telangana (0.751). This
> region-correlated measurement disagreement limits cross-region interpretation and is especially
> important because the apparent regional signal was concentrated in Tamil Nadu.
>
> The Tamil Nadu finding is recorded as a **confirmed limitation of Experiment 8** and as a
> **future audit flag** for earlier analyses materially dependent on the same ERA5-derived
> rainfall feature. It does **not** retrospectively invalidate those experiments.
>
> **FINAL VERDICT: INCONCLUSIVE.**

---

## 17. Data sources and storage policy

### 17.1 Primary rainfall source — stored

| Field | Value |
|---|---|
| Collection | `ECMWF/ERA5_LAND/DAILY_AGGR` (Earth Engine) |
| Institution | ECMWF / Copernicus |
| Spatial resolution | 0.1 degree (~11 km) native, reduced to district polygon mean |
| Panel years | 2000-2012 (already in repository) |
| Climatological baseline | **1971-2000**, strictly prior to the panel |
| Baseline script | `ingestion/era5_climatology_pull.py` |
| Baseline artefacts | `data/raw/weather/climatology_1971_2000/` (32 JSON files, 144 KB) |

The 1971-2000 baseline shares **zero years** with the 2000-2012 panel, so the normal cannot
contain information about any year it is used to explain. **Future-year exposure is structurally
impossible**, and the feature builder asserts it rather than assuming it.

### 17.2 IMD validation source — CITED, NOT STORED

| Field | Value |
|---|---|
| Institution | **India Meteorological Department, Pune** |
| Product | Gridded Rainfall, 0.25 x 0.25 degree, daily binary |
| Source page | `https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html` |
| Retrieval procedure | HTTP POST `rain=<year>` to `https://www.imdpune.gov.in/cmpg/Griddata/rainfall.php` |
| Retrieval date | **2026-09-04** |
| Years retrieved | 2000-2012 (13 files) |
| Official filenames | `ind<year>_rfp25.grd` |
| Total size | **330,815,340 bytes (330.8 MB)** |
| Format (verified empirically) | float32 little-endian, shape (days, 129 lat, 135 lon); lat 6.5-38.5, lon 66.5-100.0 at 0.25 degree; missing = −999.0, never treated as zero |
| Processing script | `ingestion/imd_gridded_validation.py` |
| Storage policy | **CITED-NOT-STORED** |

**Per-file inventory with SHA-256 hashes** is committed at
`data/processed/experiment8_imd_file_inventory.json` (13 entries: filename, official filename,
year, byte size, SHA-256).

**Aggregation methodology.** District polygons were exported from the **same Earth Engine
geometries the ERA5-Land pull reduced over**, so both products are aggregated over identical
boundaries. An IMD grid cell contributes to a district when its **cell centre falls inside the
polygon** (ray-casting point-in-polygon; Earth Engine `GeometryCollection` results unwrapped
recursively so multi-part districts are not silently dropped). A district containing no cell
centre — the 0.25 degree cell is ~28 km, larger than the smallest districts here — is recorded
with an explicit `CELL_FALLBACK_NEAREST` status and uses the nearest cell to its centroid. That
status is reported, never silently absorbed. Only Hyderabad required it, and Hyderabad is excluded
by E2.

**District polygon methodology.** Polygons come from `data/metadata/district_registry.csv` via
`ingestion/district_env_pull._resolve_geometry` — FAO GAUL Simplified 500m (2015) for most
districts, cached geoBoundaries GeoJSON for the districts formed after GAUL's vintage. Exported
copies are committed at `data/metadata/boundary_sources/district_polygons_ee/` (588 KB).

**The raw 330.8 MB of `.grd` files are excluded from Git** via `.gitignore` and are fully
reproducible from the official IMD source using the committed script. Every number reported in
§13 is reproducible from the committed processed outputs without re-downloading them.

---

## 18. Reproducibility

Execution order, exactly as approved:

1. Commit pre-registration — **`04441c5`**, before any data construction
2. `python -m ingestion.era5_climatology_pull` — 1971-2000 baseline, 32 districts
3. `python -m ingestion.kharif_rainfall_features` — the five variables only
4. `python -m experiments.run_experiment8_analysis --stage screens`
5. `python -m experiments.run_experiment8_analysis --stage panel`
6. `python -m experiments.run_experiment8_analysis --stage primary` — Arm 0, run once
7. `python -m experiments.run_experiment8_analysis --stage robust` — Arms 1-8
8. `python -m ingestion.imd_gridded_validation` — Tier 1 cross-check

Fixed seed: `20260904`. Full numeric results, per-district and per-year leave-one-out refits, all
coefficients, all arms, deviations and provenance: `experiments/experiment8_results.json`.

---

## 19. Repository isolation

| Path | Status |
|---|---|
| `data/processed/district_multimodal_examples.csv` | **UNMODIFIED** |
| `data/processed/district_multimodal_examples_v2.csv` | **UNMODIFIED** |
| `training/` | **UNMODIFIED** |
| `models/` | **UNMODIFIED** |
| `backend/` | **UNMODIFIED** |
| Experiment 1-7 reports, scripts, datasets, results, figures | **UNMODIFIED** |

Experiment 8 variables were **not** merged into any existing modelling dataset. All Experiment 8
data lives in separate files. The primary specification, thresholds, variables and exclusions were
**not changed after results were seen**.

---

*Experiment 8 completed 2026-09-04. Pre-registered `04441c5`. Verdict: INCONCLUSIVE.*
