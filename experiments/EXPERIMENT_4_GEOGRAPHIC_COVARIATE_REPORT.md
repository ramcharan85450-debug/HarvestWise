# Experiment 4 — Satellite provenance completion and geographic yield covariate investigation

Code: `ingestion/district_satellite_provenance_pull.py`, `ingestion/district_covariate_fetch.py`, `ingestion/district_terrain_fetch.py`, `experiments/run_experiment4_analysis.py`
Results: `experiments/experiment4_results.json` · Audit: `experiments/EXPERIMENT_4_LEAKAGE_AUDIT.md` (**10/10 PASS**)
Phase A docs: `SATELLITE_PROVENANCE_PIPELINE_INSPECTION.md`, `SATELLITE_PROVENANCE_COMPLETENESS_REPORT.md`
Figures: `experiments/figures/experiment4/`

Experiments 1–3 are unchanged. `district_multimodal_examples.csv` and `_v2.csv` were not regenerated; legacy satellite files are byte-identical; the field-level pipeline was not touched.

---

# 1. Objective

Answer the question Experiment 3 produced: **why does Tamil Nadu keep a ~0.83 t/ha yield advantage when year, season and broad satellite era are controlled?** And complete satellite provenance so sensor effects become investigable. Not to raise a score.

# 2. Background from Experiments 1–3

Experiment 1: 561 aligned examples, unseen-district evaluation, Weather+Satellite best (R² 0.205); static soil failed, revealing a location-fingerprint hazard. Experiment 2: Tamil Nadu failed everywhere; geography, era and season were perfectly confounded. Experiment 3: recovered TN Kharif 2000–2012, creating 13 shared years and a shared season — and found Tamil Nadu **still** failed, with the yield gap persisting at +0.825 t/ha while the *feature* shift collapsed.

# 3. Satellite provenance completion

A new fetcher queries each Landsat collection **separately** (the legacy path merges all four before reducing, which is what destroyed attribution) and records 15 fields per scene: `collection_id`, `sensor_name`, `satellite_platform`, `observation_year`, `composite_start_date`, `composite_end_date`, `image_count`, `valid_pixel_count`, `district_cropland_pixels`, `coverage_fraction`, alongside the original five.

Processing is deliberately **identical** to production (same band renaming, SR scaling, QA_PIXEL mask, cropland mask, `scale=100`), so provenance rows are directly comparable to legacy rows. Written to a **new directory**, leaving Experiments 1–3 reproducible.

`image_count` is 1 by construction: the pipeline does not composite — one row is one scene. `MULTI_SENSOR` therefore never arises for new fetches; it applies only to legacy aggregates.

# 4. Satellite coverage status

| State | Expected | Available | Missing | Coverage % |
|---|---|---|---|---|
| Andhra Pradesh | 481 | 260 | 221 | 54.1% |
| Telangana | 313 | 227 | 86 | 72.5% |
| Tamil Nadu | 455 | 217 | 238 | 47.7% |
| **Total** | **1,249** | **704** | **545** | **56.4%** |

New TN overlap cohort: **12 of 31 districts**, 143 of 381 rows. The three failure modes are recorded separately and the dominant one is unambiguous: **`DATA NOT FETCHED` (19/31 districts), with 0 `NO_SATELLITE_OBSERVATION_EXISTS` and 0 `EARTH_ENGINE_ACCESS_FAILURE`.** The gap is throttled throughput under Earth Engine's restricted mode, not missing imagery and not rejection. The pull is resumable and was still running at commit time.

# 5. Sensor provenance inventory

**17 districts, 8,161 scenes, 2000–2012**, sensor read from the archive:

| | Landsat 5 TM | Landsat 7 ETM+ | Landsat 8/9 |
|---|---|---|---|
| Scenes | 3,217 | 4,529 | 0 |

Year-by-year the mix is **not stable**: 2002 and 2012 contain **zero** Landsat 5 scenes, 2000–2003 is ~85–100% Landsat 7, and 2004–2009 is roughly balanced.

**This qualifies Experiment 3.** That experiment controlled for sensor by restricting both sides to "the L5/L7 era", treating it as homogeneous. It is not — sensor composition varies systematically within it. The control was partial. This does not overturn Experiment 3's conclusion (the measured L7−L5 NDVI offset was +0.032, p = 0.30), but the honest statement is that era was a coarser control than it appeared, and only now is it measurable.

**Backfill was assessed and refused.** Legacy rows keep no collection ID, the merge discarded the mission, no query log survives, and date is insufficient because both missions genuinely contribute in almost every year. Legacy provenance is labelled **UNKNOWN**, not guessed.

# 6. Candidate geographic covariates

| Category | Outcome |
|---|---|
| **1. Irrigation** | **NOT OBTAINED.** A portal-wide scan (25,000 resources) found 13 irrigation datasets. Twelve are **state-level**, which the rules forbid substituting for district values. The one district-level candidate (*Source-wise net Area Irrigated by Districts 2016-17*, `9678fb5e`) returned **HTTP 502 on three attempts** — a server-side failure. It is also 2016-17, outside the 2000–2012 window, so it would have been temporally inappropriate regardless. |
| **2. Agricultural intensity** | **OBTAINED.** Derived from the same official APY resource that supplies the yield labels, fetched without the rice filter: 28,824 crop records across the three states → 2,356 district-year-season rows. |
| **3. Agricultural inputs** | **NOT OBTAINED** at district level for this period. Not substituted with state values. |
| **4. Static terrain** | **OBTAINED.** NASA SRTM 30 m (`USGS/SRTMGL1_003`) via Earth Engine, reduced over **cropland pixels only**, 61/62 districts. |
| **5. Long-term climate** | **NOT ADDED**, deliberately — the model already carries season-window temperature, precipitation, humidity and wind. Adding long-run means of the same variables would duplicate existing features. |

# 7. Data source verification

| Covariate | Definition | Unit | Level | Coverage | Publisher |
|---|---|---|---|---|---|
| `non_rice_cropped_area_ha` | Σ area of all crops **except** Rice | hectares | district-year-season | 1997–2014 | GoI MoA&FW / data.gov.in |
| `n_crops_grown` | distinct crops with positive area | count | district-year-season | 1997–2014 | GoI MoA&FW |
| `n_rice_seasons` | distinct seasons rice is reported in | count | district-year | 1997–2014 | GoI MoA&FW |
| `gross_cropped_area_ha` | Σ area of **all** crops | hectares | district-year-season | 1997–2014 | GoI MoA&FW |
| `rice_area_share` | rice area / gross cropped area | fraction | district-year-season | 1997–2014 | GoI MoA&FW |
| `elevation_m_mean` | mean SRTM elevation over cropland | metres | district (static) | static | NASA SRTM |
| `slope_deg_mean` | mean slope over cropland | degrees | district (static) | static | NASA SRTM |

Units are hectares on the evidence already documented for this resource; no unit was guessed. Retrieval dates and source URLs are stored in `covariate_source_metadata.json`. **No state-level value is used as a district-level value anywhere.**

# 8. Geographic matching

Matched on `(state, district, year, season)` using the same five explicitly-declared aliases from Experiment 3 (Kanchipuram→Kancheepuram, Sivaganga→Sivagangai, Thiruvarur→Tiruvarur, Tiruchirappalli→Tiruchirapalli, Tuticorin→Thoothukudi). No fuzzy matching. Row count asserted unchanged by the merge.

- Agricultural covariates matched: **630 / 704** (89.5%)
- Terrain matched: **703 / 704** (99.9%)

# 9. Covariate coverage (B10)

| Covariate | Missing | Eligible (<20%) |
|---|---|---|
| all five agricultural | 10.51% | Yes |
| `elevation_m_mean`, `slope_deg_mean` | 0.14% | Yes |

Nothing was silently dropped; missingness is from district-year-seasons absent in the source.

# 10. Tamil Nadu vs AP/Telangana (matched Kharif 2000–2012; 382 rows — 143 TN, 239 AP+TG)

| Covariate | AP+TG mean | TN mean | SMD | KS |
|---|---|---|---|---|
| `n_rice_seasons` | 1.996 | 1.000 | **−21.77** | **0.996** |
| `gross_cropped_area_ha` | 377,369 | 101,702 | −1.93 | 0.800 |
| `n_crops_grown` | 16.19 | 8.80 | −1.40 | 0.589 |
| `non_rice_cropped_area_ha` | 254,204 | 49,974 | −1.32 | 0.626 |
| `rice_area_share` | 0.385 | 0.604 | +0.69 | 0.352 |
| `elevation_m_mean` | 262.97 | 223.68 | −0.21 | 0.218 |
| `slope_deg_mean` | 2.332 | 2.391 | +0.06 | 0.301 |

**Tamil Nadu districts are smaller, less crop-diverse, and far more rice-specialised** — rice is 60% of cropped area vs 39%.

## The `n_rice_seasons` trap, caught by a pre-stated screen

`n_rice_seasons` separates the regions almost perfectly (KS 0.996) and has **zero variance within Tamil Nadu**. That is not agronomy: the source reports Tamil Nadu rice under a single season in these years while reporting AP/Telangana rice under two. It is a **reporting-convention difference**, and a model given it would read region identity, not cropping intensity.

A pre-stated, symmetric screen (KS ≥ 0.95, or |SMD| ≥ 3.0, or zero within-region variance) flagged it and excluded it from every model. Two further covariates (`gross_cropped_area_ha`, `rice_area_share`) are built from rice area — the target's own denominator — and are barred from models on leakage grounds while still being reported descriptively.

# 11. Yield association analysis (B6) — ASSOCIATION, not causation

| Covariate | Pooled r | Pooled ρ | Within AP+TG | Within TN |
|---|---|---|---|---|
| `n_rice_seasons` | **−0.463** | −0.487 | **−0.01** | undefined (no variance) |
| `n_crops_grown` | −0.434 | −0.483 | −0.21 | −0.24 |
| `gross_cropped_area_ha` | −0.321 | −0.399 | +0.15 | −0.43 |
| `non_rice_cropped_area_ha` | −0.222 | −0.331 | +0.09 | −0.17 |
| `rice_area_share` | +0.185 | +0.205 | −0.02 | +0.09 |
| `slope_deg_mean` | +0.121 | +0.028 | −0.26 | +0.35 |
| `elevation_m_mean` | +0.044 | +0.036 | −0.02 | +0.21 |

**The strongest pooled correlation is entirely an artefact.** `n_rice_seasons` correlates −0.463 with yield pooled, but −0.01 within AP+Telangana and is undefined within Tamil Nadu. It is a textbook Simpson's paradox: the pooled association is a between-region difference wearing a covariate's clothing. Reporting it as "cropping intensity is associated with lower yield" would have been badly wrong.

`n_crops_grown` is the one covariate whose association **survives within both regions** (−0.21 and −0.24), which is what makes it credible rather than merely large. Several covariates reverse sign between regions (`gross_cropped_area_ha`, `slope_deg_mean`), which is itself a warning against pooled interpretation.

# 12. Geographic yield-gap analysis (B7)

Raw gap, matched year and season: **+0.825 t/ha** (TN 3.586 vs AP+TG 2.761). Present in **every one of the 13 years**, ranging +0.14 (2003) to +1.29 (2011) — persistent, not driven by a few years.

# 13. Controlled explanatory models (B8)

n = 382. Covariates entering: `non_rice_cropped_area_ha`, `n_crops_grown`, `elevation_m_mean`, `slope_deg_mean`.

| Model | Region coefficient (t/ha) | 95% CI | R² |
|---|---|---|---|
| **A — region only** | **+0.825** | [0.666, 0.984] | 0.216 |
| **B — region + covariates** | **+0.565** | [0.364, 0.765] | 0.282 |
| Ridge (λ=1, covariates penalised, region not) | +0.566 | — | — |

**The covariates statistically account for 31.6% of the gap.** The region term shrinks from +0.825 to +0.565 but its CI still excludes zero by a wide margin — roughly **two-thirds of the Tamil Nadu advantage remains unexplained**. Ridge agrees almost exactly (+0.566), so this is not an artefact of collinearity in OLS.

Covariate coefficients: `n_crops_grown` **−0.0401 t/ha per additional crop** (CI [−0.0554, −0.0248], excludes zero); `slope_deg_mean` +0.0901 (CI [0.0019, 0.178], marginal); `elevation_m_mean` +0.000416 (CI includes zero); `non_rice_cropped_area_ha` ~1.2e-07 (CI includes zero).

Only `n_crops_grown` is both statistically clear and consistent within regions. Interpreted carefully: **rice specialisation is associated with higher rice yield.** This is not established as causal — specialisation and favourable growing conditions plausibly share upstream causes such as irrigation access, which is precisely the variable that could not be obtained.

# 14. Extreme-value sensitivity analysis (B9)

Rule pre-stated and **symmetric across all states**: 1st/99th percentile winsorization of the target on the pooled subset. Nothing deleted; nothing Tamil Nadu-specific. 8 values clipped — **7 Tamil Nadu, 1 Andhra Pradesh** (that TN dominates is a consequence of the symmetric rule, not of targeting).

| Quantity | Main | Winsorized |
|---|---|---|
| Raw gap | +0.825 | +0.791 |
| Region coefficient, Model A | +0.825 | +0.791 |
| Region coefficient, Model B | +0.565 | +0.562 |
| % of gap accounted for | 31.6% | 29.0% |

**Conclusions are unchanged.** The gap, its persistence, and the partial-explanation finding all survive.

# 15. Optional prediction experiment (Phase C)

Run only after the audit passed. AP+Telangana → Tamil Nadu, Kharif, matched years; 239 train / 143 test rows; **hyperparameters unchanged from Experiment 1**; train and test share no district.

| Arm | MAE ↓ | RMSE ↓ | R² ↑ |
|---|---|---|---|
| Baseline (train mean) | 1.052 ± 0.022 | 1.323 | −0.676 |
| Weather + Satellite | 1.075 ± 0.038 | 1.385 | −0.835 |
| Covariates only | 1.041 ± 0.080 | 1.335 | −0.711 |
| **Weather + Satellite + Covariates** | **0.910 ± 0.050** | **1.222** | **−0.432** |
| **Static only (mandatory control)** | 1.223 ± 0.146 | 1.526 | −1.248 |
| Soil only | 1.439 ± 0.179 | 1.770 | −2.031 |

**This is the first configuration in this project to beat the baseline in cross-region transfer** — MAE 0.910 vs 1.052, a 13.5% reduction, consistent across all five seeds.

**And the mandatory C2 control clears it of shortcut behaviour.** If the gain came from static location fingerprinting, `static_only` should have performed well. It performs *worse than baseline* (1.223 vs 1.052), as does `soil_only` (1.439). The improvement therefore comes from the **time-varying** agricultural covariates interacting with environmental features, not from location identity.

**The honest ceiling:** R² is still **−0.432**. Predicting Tamil Nadu's own mean would score 0. So this is a real, controlled improvement in transfer that still does **not** produce a usable Tamil Nadu model.

# 16. Leakage audit

**10 of 10 PASS**, run before any Phase C training: no yield-derived covariates (the two rice-area-derived covariates are barred), no future information, no test districts in preprocessing, no test-driven feature selection, no state or district identifier as a feature, static covariates tested separately, geographic separation maintained, imputation train-only, scaling train-only.

The audit's most substantive catch is the `n_rice_seasons` region proxy — excluded by measurement, not by intuition.

# 17. What the data supports

1. Per-row satellite provenance is implemented and working; 8,161 scenes carry real sensor identity.
2. Sensor composition varies substantially within the "L5/L7 era" — 2002 and 2012 have zero L5 scenes — so Experiment 3's era control was partial.
3. Tamil Nadu's yield advantage is real, persistent in every one of 13 matched years, and robust to symmetric extreme-value treatment.
4. Available district covariates statistically account for **~30%** of it (31.6% main, 29.0% sensitivity).
5. `n_crops_grown` (rice specialisation) is the one covariate with a clear coefficient and a consistent within-region association.
6. Adding covariates genuinely improves cross-region transfer (MAE 1.052 → 0.910), and this is **not** static-location shortcut behaviour.

# 18. What the data does NOT support

1. **No causal claim.** Every relationship here is an association in an observational panel.
2. **Not** that cropping intensity lowers yield — the strongest pooled correlation is a Simpson's-paradox artefact of a reporting convention.
3. **Not** that the gap is explained. ~70% remains unaccounted for, and the region coefficient's CI still excludes zero.
4. **Not** that irrigation explains it — irrigation data was never obtained and remains the leading untested hypothesis.
5. **Not** that Tamil Nadu is now predictable. R² −0.432 is still worse than its own mean.
6. **Not** that sensor effects are resolved — provenance now exists but the measured effect is still the small, underpowered n=6 estimate from Experiment 3.

# 19. Limitations

- Tamil Nadu satellite collection incomplete (12/31 overlap districts); the analysis rests on 143 of 381 collected rows.
- District-level irrigation unavailable (HTTP 502, and temporally mismatched anyway) — the most agronomically plausible explanatory variable is absent.
- Covariates come from one publisher; a source-specific reporting convention already produced one near-fatal artefact (`n_rice_seasons`), so others may exist.
- Terrain is static and cropland-masked at a single 2006 land-cover snapshot.
- Analysis is Kharif-only, 2000–2012, three states.
- Four extreme yields retained in the main analysis (disclosed in Experiment 3), handled in B9.

# 20. Scientific conclusion

Experiment 4 converts Experiment 3's open question into a **partially answered** one. Tamil Nadu's ~0.83 t/ha advantage is real and stable across 13 matched years, and about **30%** of it is statistically accounted for by district agricultural-structure covariates — chiefly rice specialisation, the one covariate whose association holds within regions as well as between them. About **70% remains unexplained**, and the single most likely missing variable, district irrigation, could not be obtained.

The methodological result is as valuable as the substantive one: the strongest apparent signal in the data was a **reporting-convention artefact** that a pre-stated screen caught, and the one genuine predictive improvement in the project's cross-region history was validated against a **mandatory static-only control** that ruled out the location-fingerprint shortcut this project has been caught by before. Both guardrails earned their place.

---

# Final questions

**1. Was per-row satellite provenance successfully added? — YES.** 15 fields per scene, 8,161 scenes across 17 districts, sensor read from the archive rather than inferred.

**2. Is the Tamil Nadu satellite collection complete? — NO.** 12/31 overlap districts aligned (143/381 rows). The reason is recorded precisely: `DATA NOT FETCHED` for 19 districts, with **0** access failures and **0** empty collections. Throughput under Earth Engine restricted mode, not missing data. Resumable.

**3. Which sensor generations are represented? — Landsat 5 TM (3,217 scenes) and Landsat 7 ETM+ (4,529) for 2000–2012; zero Landsat 8/9.** Legacy 2019/2024 rows remain UNKNOWN.

**4. Can sensor effects now be measured? — YES in principle, for newly fetched data; NOT YET at scale.** Provenance exists, but only for TN 2000–2012, where both contributing missions are L5/L7. A powered test needs provenance on both sides of a comparison. The infrastructure is the deliverable here, not the answer.

**5. Which district-level covariates were successfully collected? — Five agricultural** (`non_rice_cropped_area_ha`, `n_crops_grown`, `n_rice_seasons`, `gross_cropped_area_ha`, `rice_area_share`) **and two terrain** (`elevation_m_mean`, `slope_deg_mean`). Irrigation and input covariates were **not** obtained and were not faked with state-level values.

**6. Does any covariate show a meaningful association with yield? — YES, one: `n_crops_grown`** (pooled r = −0.434, and −0.21/−0.24 *within* each region; coefficient −0.0401 t/ha per crop, CI excluding zero). The larger-looking `n_rice_seasons` association is an artefact and is rejected.

**7. Does any covariate statistically reduce the Tamil Nadu gap? — YES, partially: 31.6%.** Region coefficient +0.825 → +0.565, ridge concurring at +0.566. The remaining ~70% is unexplained and the CI still excludes zero.

**8. Does the conclusion survive the extreme-value sensitivity analysis? — YES.** Under symmetric winsorization the gap moves +0.825 → +0.791 and the accounted share 31.6% → 29.0%. No conclusion changes.

**9. Does adding covariates improve unseen-district prediction? — YES.** Weather+Satellite+Covariates reaches MAE 0.910 vs a 1.052 baseline — the first cross-region configuration in this project to beat baseline. But R² −0.432 is still worse than Tamil Nadu's own mean, so it is an improvement, not a usable model.

**10. Genuine or static-location shortcut? — GENUINE.** The mandatory `static_only` control performs *worse* than baseline (1.223), and `soil_only` worse still (1.439). The gain comes from time-varying covariates, not location identity.

**11. Strongest defensible explanation for Tamil Nadu's advantage?** Tamil Nadu's rice districts are **smaller, less crop-diverse and substantially more rice-specialised** (rice 60% of cropped area vs 39%), and specialisation is associated with higher rice yield within regions as well as between them. This accounts for roughly a third of the gap. The remaining two-thirds is most plausibly **irrigation access and water control** — Tamil Nadu's delta districts are canal-irrigated — but that is a **stated hypothesis, not a finding**: the data was not obtainable and the hypothesis is untested here.

**12. What is the next experiment?** Obtain **district-level irrigation** for 2000–2012 — the leading untested hypothesis and the largest identified gap. The data.gov.in route failed (502, wrong period); the correct next sources are the Tamil Nadu and Andhra Pradesh DES Season and Crop Reports, which publish net/gross irrigated area by district and source, and the Minor Irrigation Census. Secondarily, finish the resumable provenance pull to raise the test set from 143 toward 381 rows and enable a properly powered sensor experiment.
