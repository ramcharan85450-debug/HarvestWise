# Experiment 3 — Overlapping-year data recovery and satellite sensor harmonization analysis

Code: `ingestion/tamil_nadu_overlap_extract.py`, `ingestion/district_alignment_overlap.py`, `experiments/sensor_inventory_probe.py`, `experiments/run_experiment3_analysis.py`
Results: `experiments/experiment3_results.json`, `experiments/sensor_inventory.json`
Coverage matrix: `experiments/OVERLAP_COVERAGE_MATRIX.md` · Validation: `data/raw/external/official_yield/OVERLAP_COLLECTION_VALIDATION.md`
Figures: `experiments/figures/experiment3/`

Experiments 1 and 2 are unchanged. `data/processed/district_multimodal_examples.csv` was **not** regenerated; the new dataset is written to `district_multimodal_examples_v2.csv`. The field-level pipeline was not touched.

---

# 1. Objective

Not to improve accuracy. To **remove or measure** the four confounds Experiment 2 identified: geography, era, season structure, and satellite sensor generation. Experiment 2 could report only "CANNOT ISOLATE"; this experiment's job is to change that where the data allows and to say so plainly where it does not.

# 2. Existing confounds

Before this experiment: AP/Telangana had 1999–2012 Kharif/Rabi; Tamil Nadu had 2019 & 2024 Whole Year. **Zero overlapping years, zero overlapping seasons.** Sensor identity was never recorded at all. Any AP/TG → TN result therefore mixed geography, era, season and sensor inseparably.

# 3. Coverage matrix

Full matrix in `OVERLAP_COVERAGE_MATRIX.md`. Key facts established there:

- The state × year matrix had a **block structure** — no non-zero column shared between TN and AP/TG.
- Every Tamil Nadu row had satellite window coverage of **0.503–0.504**, passing the 50% floor by ~0.4 points, because `Whole Year` spans Jul–Jun but only calendar 2019 and 2024 were fetched.
- **Sensor identity is not recoverable from the stored data.** The satellite CSVs carry only `date, mean_ndvi, mean_evi, mean_ndwi, cloud_cover_pct`; `landsat_fetch.py` merges four missions and writes only the reduced means. Nor is date sufficient — every year present falls in a multi-mission window (1999–2012 = L5+L7; 2019 = L7+L8; 2024 = L8+L9).

# 4. Overlap-year opportunities

| | Strategy A: TN for 2000–2012 | Strategy B: AP/TG for 2019–2024 |
|---|---|---|
| Official source available | **Yes** — same data.gov.in resource `35be999b` already used for AP/TG | **No** — that resource ends at 2014 |
| Years available | 1997–2013 (Kharif) | Would require new, unvalidated sources |
| Districts | 31 | unknown |
| Season coverage | Kharif — **matches AP/TG** | Kharif/Rabi |
| Units | Same fields, same corroborated units | Would need fresh unit verification |
| Verifiable | Yes — identical publisher and fetch path | Uncertain |
| Already on disk | **Yes** | No |

# 5. Strategy comparison — ranking

**Strategy A wins decisively**, on scientific grounds rather than convenience:

1. It creates overlap in **both** year and season simultaneously (Kharif exists on both sides), breaking two confounds at once. Strategy B could match years but Tamil Nadu's recent rows are `Whole Year`, so the season confound would survive.
2. It holds the **satellite sensor era** fixed as a side effect: 2000–2012 is the L5/L7 era on both sides, so the sensor confound is also neutralised for this comparison.
3. It introduces **no new publisher**. Strategy B would have removed a temporal confound while adding a source confound.

Strategy B is also currently blocked: the resource ends in 2014.

# 6. Official data sources found

Government of India, Ministry of Agriculture and Farmers Welfare, district-wise season-wise crop statistics, via data.gov.in resource `35be999b-0208-4354-b557-f6ca9a5355de`. Tamil Nadu Rice rows exist in it for 1997–2013 — they were simply never extracted, because the earlier Tamil Nadu collection targeted TN DES Season and Crop Report PDFs for 2019/2024 instead.

# 7. Data successfully collected

**381 official Tamil Nadu district Kharif rice records, 2000–2012, across 31 districts.** No fabrication, no interpolation, no synthetic rows.

# 8. Data validation

Full report: `OVERLAP_COLLECTION_VALIDATION.md`. Summary: 0 duplicates, 0 missing values, 0 rows outside the project's existing 0.1–15.0 t/ha bound, 0 rows where the recomputed `production/area` disagreed with the source's own derived yield, and 0 of 31 districts failing to match the registry after 5 explicitly-declared name aliases.

**Four extreme values are disclosed and kept** (Coimbatore 2008 at 9.89 t/ha, Perambalur 2008 at 9.18, Ramanathapuram 2003 at 0.17 and 2007 at 0.24). 9.9 t/ha is at or beyond the realistic ceiling for a district average and may be a source error. They were kept because discarding them would apply a stricter filter to Tamil Nadu than was applied to AP/Telangana, biasing the very comparison this data exists to support.

# 9. Satellite sensor inventory (Phase 5)

Sensor identity had to be **recovered by re-querying Earth Engine per collection**, because it is not stored. Sampled district-seasons, real archive counts:

| State | Year | Landsat 5 TM | Landsat 7 ETM+ | Landsat 8 | Landsat 9 |
|---|---|---|---|---|---|
| Andhra Pradesh | 2003 | 2 | 31 | 0 | 0 |
| Andhra Pradesh | 2007 | 29 | 43 | 0 | 0 |
| Telangana | 2003 | 2 | 18 | 0 | 0 |
| Telangana | 2007 | 12 | 28 | 0 | 0 |

This is a **sample, not a census** — Earth Engine is in restricted (throttled) mode for this project. Two findings are already clear: the 1999–2012 features are a **mixture** of L5 and L7 rather than "the L5 era", and Landsat 7 dominates the scene count in the sampled years, including 2003 where L5 contributes almost nothing.

# 10. Satellite processing pipeline inspection (Phase 6)

Read directly from `ingestion/landsat_fetch.py`:

| Aspect | What the pipeline actually does | Verdict |
|---|---|---|
| Product | Collection 2 Level-2 **surface reflectance** (`T1_L2`) for all four missions | Consistent |
| Band mapping | Explicit per-mission map to BLUE/RED/NIR/SWIR1 (L5/L7: B1,B3,B4,B5; L8/L9: B2,B4,B5,B6), renamed **before** any index is computed | **Correct** — avoids the classic silent NIR/RED vs RED/GREEN error |
| Scaling | `DN × 0.0000275 − 0.2` applied before indices | **Correct**, and necessary for EVI, whose additive constants make unscaled DNs meaningless |
| Cloud masking | `QA_PIXEL` bits 1/3/4/5 (dilated cloud, cloud, shadow, snow) + `CLOUD_COVER ≤ 70` | Consistent across missions |
| Index definitions | NDVI, EVI (2.5·(N−R)/(N+6R−7.5B+1)), NDWI (Gao, NIR/SWIR1) — one definition applied to all | Consistent |
| Compositing | None — per-scene means, later averaged over the season window | Consistent |
| **Cross-sensor radiometric harmonization** | **NOT APPLIED** | **This is the real gap** |

The pipeline harmonizes band *names, scaling and index definitions* — which is more than many pipelines do — but it does **not** apply cross-sensor reflectance transforms (e.g. Roy et al. 2016 OLI↔ETM+ coefficients). Band renaming is not radiometric harmonization. As the task warned: consistent NDVI arithmetic does not by itself guarantee cross-sensor comparability, because the underlying spectral response functions differ.

# 11. Sensor comparability analysis (Phase 7)

**Genuine isolation was possible here.** Landsat 5 and Landsat 7 imaged the *same districts* in the *same years* over the *same season windows*. Comparing them pairwise holds geography, time and season fixed by construction, so a residual difference **is** a sensor effect.

Paired same-district, same-year, same-season comparison (n = 6 district-years, identical processing):

| Index | L7 − L5 mean difference | SD | Cohen's dz | Paired t p-value |
|---|---|---|---|---|
| NDVI | **+0.0323** | 0.0684 | +0.47 | 0.300 |
| EVI | −0.0038 | 0.0655 | −0.06 | 0.892 |
| NDWI | −0.0195 | 0.0708 | −0.28 | 0.530 |

**Interpretation, stated conservatively:** the sensor effect is *measurable in direction and magnitude* — L7 reads NDVI about +0.03 higher than L5 on the same ground on the same dates — and its sign matches the known ETM+/TM relationship. But at n = 6 it is **not statistically resolved** (p = 0.30) and the pair-to-pair scatter (SD 0.068) is twice the mean effect.

Two things follow, and neither is "apply a correction":

1. **The effect is small relative to the shifts that matter.** +0.03 NDVI is roughly 4% of the ~1.5 SD NDVI shift Experiment 2 measured between AP/TG and Tamil Nadu. Sensor generation cannot explain that shift.
2. **No correction is applied.** A 6-pair estimate that fails significance is not a basis for altering real observations, and the task's instruction not to harmonize silently is the right one. What the project should do instead is **record the sensor per scene going forward** — a one-line change to what `landsat_fetch.py` writes — so the question becomes answerable at scale rather than by sampling.

# 12. Sensor-aware diagnostic results (Phase 8)

A row-level sensor-stratified training experiment is **not possible**, and I will not simulate one: sensor identity does not exist per row in the stored features, so rows cannot be partitioned by sensor without re-fetching the entire archive. What *was* achievable — and is stronger than a stratified train/test split — is holding the sensor era fixed across the whole cross-region comparison, which Isolation 1 below does: both sides of that experiment are drawn from the same L5/L7 era.

# 13. New alignment results (Phase 9)

| Stage | Count |
|---|---|
| Collected (new TN Kharif 2000–2012) | 381 |
| Geometry matched | 381 |
| Weather matched | 381 |
| Satellite matched | **143** |
| Soil matched | 381 |
| **Fully aligned** | **143** |

The binding constraint is satellite: at the time of this run, only **15 of 39** Tamil Nadu districts had completed their 2000–2012 Landsat pull, because Earth Engine is in restricted (throttled) mode. **This is an incomplete fetch, not a data limitation** — the remaining districts have imagery in the archive and the pull is resumable, so this number is expected to rise on a re-run without any change to method. Reported as-is rather than waited out.

Critically, the baseline cohort re-aligned to **exactly 561** — identical to Experiment 1 — confirming the v2 pipeline reproduces the old dataset and that the new rows are additive, not disruptive. Total aligned: **704** (561 + 143). Every row carries `dataset_version` (`experiment1_baseline` / `experiment3_overlap_addition`) so the cohorts remain separable.

# 14. Confound reduction analysis (Phase 10)

| Confound | Before | After | Status |
|---|---|---|---|
| **Year** (region × era) | 0 overlapping years | **13 overlapping years (2000–2012)** | **BROKEN** |
| **Season** (region × season) | 0 overlapping seasons | **Kharif shared by all three states** | **BROKEN** |
| **Satellite sensor era** | TN = L7/L8/L9 era, AP/TG = L5/L7 era | Both sides in the L5/L7 era for the overlap comparison | **BROKEN for the overlap comparison** |
| **Per-row sensor identity** | Not recorded | Still not recorded | **UNCHANGED** |
| Rabi / Whole Year cross-region | No overlap | Still no overlap | **STILL PERFECTLY COLLINEAR** |
| TN satellite window coverage (2019/2024) | 0.504 | Still 0.504 for those rows | **UNCHANGED** |

All three states now share Kharif 2000–2012. That is a real structural change to the dataset, not a reinterpretation of the old one.

# 15. What can now be tested — and the two isolations' results

## Isolation 1 — PURE CROSS-REGION GENERALIZATION (geography isolated)

Train AP+Telangana Kharif 2000–2012 (239 rows, 20 districts) → test Tamil Nadu Kharif 2000–2012 (143 rows, 12 districts). **Same 13 years. Same season. Same sensor era. Only the state differs.** Hyperparameters unchanged from Experiment 1.

| Configuration | MAE ↓ | R² ↑ |
|---|---|---|
| **Baseline (train mean)** | **1.052 ± 0.022** | **−0.676 ± 0.055** |
| Weather only | 1.055 ± 0.076 | −0.777 ± 0.199 |
| Satellite only | 1.059 ± 0.038 | −0.700 ± 0.093 |
| Weather + Satellite | 1.075 ± 0.038 | −0.835 ± 0.093 |
| Soil only | 1.439 ± 0.179 | −2.031 ± 0.633 |
| Full multimodal | 1.134 ± 0.112 | −1.051 ± 0.365 |

**Tamil Nadu still fails, with era, season and sensor all held fixed.** No configuration beats the baseline. This is the single most important result of Experiment 3, and it **rules out** the most attractive hypothesis from Experiment 2 — that Tamil Nadu's failure was an artefact of comparing 2019/2024 against 1999–2012.

## The decomposition this makes possible

| Quantity | Experiment 2 (confounded) | Experiment 3 Isolation 1 (geography only) |
|---|---|---|
| Max feature SMD | **1.50** | **0.55** |
| Satellite NDVI SMD | +1.47 | −0.55 |
| Humidity SMD | +1.42 | −0.14 |
| **Yield SMD** | **+1.36** | **+1.00** |

The **feature** shift was mostly era/season/coverage: it collapses by ~two-thirds once those are held fixed, and NDVI even reverses sign. The **yield** shift does not collapse — Tamil Nadu really does out-yield AP/Telangana by ~0.83 t/ha (3.586 vs 2.761) in the same years and same season.

## Isolation 2 — ERA + SEASON within one region

Tamil Nadu Kharif 2000–2012 (n=143) vs Tamil Nadu Whole Year 2019/2024 (n=74), **12 districts shared between the two cohorts**:

- Yield SMD: **+0.214** — small. Tamil Nadu's yield level is stable across two decades.
- Satellite NDVI SMD: **+1.52**, EVI +1.16, NDWI +1.02 — large.

Same state, same districts: the satellite features shift by ~1.5 SD while yields barely move. This **confirms from the other direction** that the large satellite shift Experiment 2 attributed ambiguously to "region or era or sensor" is an era/season/window-coverage effect, not a geographic one.

# 16. What still cannot be tested

1. **Sensor effects at scale, or per row.** Sensor identity is still unrecorded; the n=6 probe measures a small effect that does not reach significance.
2. **Era separated from season.** Isolation 2 varies both together (Kharif 2000–2012 vs Whole Year 2019/2024), so it bounds their joint contribution only.
3. **Cross-region generalization for Rabi or Whole Year.** Isolation 1 is Kharif-only. Nothing here licenses claims about other seasons.
4. **Whether Tamil Nadu's yield advantage is explainable at all** by any environmental feature — only that these 12 features do not explain it.
5. **The 2013–2018 gap.** Neither region has data there, so the L8 transition year (2013) is unobserved on both sides.

# 17. Limitations

- The satellite pull for the new cohort is **incomplete (15/39 districts)**, so 143 of 381 collected rows aligned. The result is real but the sample is smaller than it will be after a re-run.
- Isolation 1's test set is 12 Tamil Nadu districts, not 31 — a consequence of the same incomplete pull.
- The sensor probe is a 6-pair sample from 2 states × 2 years, chosen in registry order rather than by result, but still a small sample.
- Four extreme yield values (1.05% of rows) are retained and may be source errors.
- Isolation 1 holds season fixed at Kharif by design, which is a strength for internal validity and a limit on external validity.

# 18. Recommended next experiment

**Record the satellite sensor per scene, then complete the pull.** One added column in `landsat_fetch.py`'s `write_csv` (the collection ID, already known server-side) converts sensor from an unanswerable question into a per-row covariate, enabling a properly powered sensor-stratified experiment instead of a 6-pair probe. Completing the 24 outstanding Tamil Nadu districts would simultaneously raise Isolation 1 from 143 to a projected ~381 test rows.

After that, the scientifically correct next question is no longer "is it geography or era?" — Experiment 3 answered that — but **"what explains Tamil Nadu's persistent ~0.83 t/ha yield advantage that these 12 environmental features miss?"** The candidates (irrigation fraction, cropping intensity, delta alluvial soils, varietal differences) are all measurable district-level covariates from official sources.

---

# Final questions

**1. Which overlapping-year strategy is scientifically better? — Strategy A (Tamil Nadu 2000–2012).**
It breaks the year *and* season confounds simultaneously, holds the sensor era fixed as a side effect, and adds no new publisher. Strategy B is additionally blocked — the resource ends in 2014.

**2. Were new official records successfully collected? — YES.**
381 official district-level Tamil Nadu Kharif rice records, 2000–2012, 31 districts, from the same GoI/data.gov.in resource already used for AP/Telangana. 0 duplicates, 0 missing values, units corroborated not guessed, 4 extreme values disclosed and retained.

**3. Do AP, Telangana and Tamil Nadu now share overlapping years? — YES.**
All three share **Kharif 2000–2012**, 13 years. Before: zero shared years and zero shared seasons.

**4. Can geographic and temporal effects now be separated? — YES, for Kharif.**
Isolation 1 holds year, season and sensor era fixed and varies only the state. The answer it gives is a negative one: **Tamil Nadu still fails**, so its failure is *not* an artefact of the era gap. Separately, Isolation 2 shows the large satellite feature shift *is* era/season-driven, since it appears within the same 12 Tamil Nadu districts. This does not extend to Rabi or Whole Year.

**5. Is satellite sensor shift measurable? — PARTIALLY.**
L7 reads NDVI +0.032 higher than L5 on the same district, same dates (dz = +0.47), with the expected sign. But p = 0.30 at n = 6, so it is **measurable in magnitude, not statistically resolved**. It is also ~4% of the shift Experiment 2 observed, so it cannot explain that shift.

**6. Can sensor effects be isolated from geography/time? — YES in principle, and the probe did it — but the sample is too small to conclude.**
The paired L5-vs-L7 design genuinely isolates the sensor (same district, year, season, processing). The limitation is statistical power (n = 6), not confounding. This is the one place in this project where isolation was achievable and the obstacle is merely sample size — which is fixable by recording the sensor per scene.

**7. Is the dataset now stronger for cross-region evaluation? — YES, materially.**
704 aligned examples (up from 561), three states sharing 13 common years and a common season, and a cross-region test whose confounds are controlled rather than merely acknowledged. The strength is in the *design*, not the score: the model still fails, but the failure now means something specific.

**8. What is the next scientifically correct experiment?**
Record per-scene sensor identity and complete the Tamil Nadu pull (both mechanical); then investigate what district-level covariate explains Tamil Nadu's persistent yield advantage, since Experiment 3 has now shown it is genuinely geographic and not an era artefact.

---

## Honest summary

Experiment 3 did what it set out to do: it **broke three of four confounds** and **measured the fourth**. The scientific payoff is not a better score — the score got worse, and that is reported rather than buried. It is that Tamil Nadu's failure is now a *specific, isolated* finding (a genuine cross-region yield gap the current features do not capture) instead of an *uninterpretable* one (some mixture of geography, era, season and sensor). A negative result with the confounds removed is worth considerably more than the same negative result with them intact.
