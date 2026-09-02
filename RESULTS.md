# HarvestWise — measured results

Every number here is reproducible by the command shown beside it. Nothing in
this file is estimated, rounded from memory, or carried over from an earlier
run. Where a result is single-seed and should not be, it says so.

Last regenerated against: ERA5 2022–2025 (the 2019–2021 backfill was still
running; **all model results below must be regenerated once it lands**).

---

## 1. Data

| | |
|---|---|
| Real fields | 7 |
| States | 4 (Tamil Nadu, Punjab, West Bengal, Andhra Pradesh) |
| Crops | 2 (rice, wheat) |
| **Real season examples** | **21** (seasons with an unobserved satellite gap are dropped, see S2a) |
| Satellite weeks genuinely observed | 68% |

Sources: Sentinel-2 (`S2_SR_HARMONIZED`, ≤20% cloud) via Earth Engine; ERA5
reanalysis via Copernicus CDS; ISRIC SoilGrids REST API. Yield labels and
their provenance and caveats: `data/raw/yield_labels/README.md`.

**Label granularity is the project's central limitation.** Labels are national
(Economic Survey 2025-26, Table 1.17) and state-level annual averages, while
the inputs describe specific ~450 ha irrigated field polygons. Section 5
shows this is not a cosmetic caveat — it is what breaks the models.

---

## 2. Yield forecasting — the headline result

```
python -m evaluation.run_model_comparison --seeds 5
```

MAE (t/ha) on 21 real held-out season examples, mean +/- sd over 5 seeds:

| Model | MAE | Range over seeds |
|---|---|---|
| **Naive (predict the mean)** | **0.689 +/- 0.006** | 0.684 - 0.699 |
| Random Forest | 0.726 +/- 0.098 | 0.641 - 0.886 |
| HarvestWise multimodal | 0.727 +/- 0.131 | 0.609 - 0.952 |
| XGBoost | 0.764 +/- 0.181 | 0.526 - 0.997 |

**No model beats predicting the mean.** At n=21 with state/national aggregate
labels, neither the multimodal model nor the tree ensembles extract usable
signal. The top-two gap (0.037) is smaller than the seed spread (0.052), so no
ranking among them is established either.

### Retractions

Two earlier results in this project's history are withdrawn. Both were
measured correctly and both were wrong, for different reasons:

| Retracted claim | Why it fell |
|---|---|
| "MAE 0.532 / 0.635, beats naive" (n=28, single seed) | Seed luck. The 5-seed distribution was 0.449-1.134. |
| "MAE 0.569, beats naive by 21%" (n=43) | **Interpolated data.** 56% of the satellite series was gap-filled, and interpolated series are artificially smooth and therefore easy to predict. On observed-only data the advantage vanishes. |

The second is the more instructive failure: the fix that produced it (real
soil for 5 of 7 fields) was genuine, but it was measured on a dataset that was
more than half manufactured, so the improvement could not be attributed.

---

## 2a. Data quality - the satellite series was 56% interpolated

`ingestion/align_pipeline.py` bridged cloud gaps with
`interpolate(limit_direction="both")` - no length limit - while
`MAX_CLOUD_COVER_PCT = 20` discarded any scene more than 20% cloudy. That
second filter was redundant: the fetcher already masks cloud per pixel via
Sentinel-2's SCL band, so partly-cloudy scenes with a clear view of the field
were being thrown away and then reconstructed by interpolation.

| Field | Observed before | Observed after |
|---|---|---|
| F001 | 31% | 59% |
| F002 | 36% | 63% |
| F003 | 31% | 61% |
| F004 | 62% | 76% |
| F005 | 48% | 70% |
| F006 | 42% | 72% |
| F007 | 62% | 73% |
| **overall** | **44%** | **68%** |

Two changes: `MAX_CLOUD_COVER_PCT` 20 -> 70 (per-pixel masking remains the real
quality control), and interpolation capped at `MAX_INTERPOLATION_WEEKS = 3`.
Longer gaps stay NaN and `training/dataset.py` drops the season rather than
training on a fabricated flat line.

The effect on phenology is the clearest evidence the old data was wrong:

| | Before | After |
|---|---|---|
| Season examples | 43 | 21 |
| Seasons peaking in their final 3 weeks | 20/43 | 3/21 |
| Near-flat seasons (NDVI range < 0.05) | many | 0/21 |
| Mean within-season NDVI range | ~0.01 on flat seasons | 0.367 |
| Modal peak-NDVI week | 19 (impossible) | 10-15 (correct for Aug-sown rice) |

F001's 2022 season previously read NDVI 0.30 for all 20 weeks and trained
exactly like real data. Half the dataset was lost to this fix. That is the
honest cost of the correction, not a regression.

---

## 3. Multimodal fusion ablation

```
python -m evaluation.ablation.run_ablation --seeds 5
```

| Ablation | val R² (5 seeds) | Range |
|---|---|---|
| imagery-only | 0.027 | −0.554 – 0.606 |
| fused | −0.069 | −0.537 – 0.248 |
| weather-only | −0.119 | −0.271 – 0.073 |

**Fusion is not demonstrated to help.** Fused scores below imagery-only, and
all three sit at or under R² = 0 — worse than predicting the mean. An earlier
3-seed run reporting fused 0.500 vs 0.444 / 0.441 is **retracted** as seed
luck.

---

## 4. Climate-Shock Benchmark

```
python -m evaluation.climate_shock_benchmark.derive_labels
python -m evaluation.climate_shock_benchmark.run_climate_shock
```

Fit on 20 real NORMAL field-seasons (+ identical synthetic pretraining for
every model); scored on 4 real SHOCK field-seasons never seen in training.
Shock membership is decided by ERA5 growing-season anomalies against each
field's own climatology (drought <0.75×, wet_extreme >1.30×, heatwave >+1.0 °C),
never assigned by hand.

Held-out shock seasons: F004/2025 wet_extreme (4.193 t/ha), F005/2022 drought
(2.995), F005/2024 wet_extreme (3.057), F006/2025 drought (3.393).

Mean ± sd over 5 seeds (`--seeds 5`):

| Model | MAE on shock seasons (t/ha) | Range |
|---|---|---|
| Random Forest | **0.189 ± 0.060** | 0.143 – 0.294 |
| XGBoost | 0.222 ± 0.044 | 0.173 – 0.289 |
| HarvestWise multimodal | 0.366 ± 0.146 | 0.221 – 0.566 |
| Naive | 0.460 ± 0.011 | 0.450 – 0.479 |

Two things to report together:

- **On shock seasons the multimodal model does beat the naive baseline**
  (0.366 vs 0.460), unlike on the full holdout in §2 where it does not. Its
  variance is again the largest of any model (±0.146 vs the naive ±0.011).
- **The Random Forest / XGBoost ordering is not established**: the top-two gap
  (0.034) is smaller than the pooled seed spread (0.052).

Earlier single-seed numbers for this table (RF 0.143, XGBoost 0.224, naive
0.455, HarvestWise 0.566) were individual draws and are superseded.

---

## 5. Why the deep model fails — the synthetic-pretraining experiment

Synthetic examples supply ~91% of the gradient signal (300 synthetic vs 28
real). With the default generator, holding crop identity constant, the yield
label correlates with **nothing**:

| Input (rice archetype, n=150) | corr with yield |
|---|---|
| season mean temperature | −0.039 |
| season rainfall | −0.020 |
| peak NDVI | +0.021 |

So the loss-optimal fit is "predict the archetype mean", which is what the
model learns.

Enabling `build_synthetic_dataset(weather_coupling=True)` adds bounded,
correctly-signed agronomic stress to both the label and the canopy. It works
on the synthetic set (temperature −0.328, rainfall +0.424, peak NDVI +0.707)
— and makes real accuracy **monotonically worse**:

| Generator | n_syn | Real MAE | corr(pred, actual) |
|---|---|---|---|
| uncoupled | 300 | 0.532 | ~0 (near-constant predictions) |
| coupled | 300 | 0.931 | — |
| coupled | 3000 | 1.391 | +0.078 (bias −1.32) |

At n_syn=3000 overfitting is gone (train 0.128 / val 0.138), so the model
genuinely learned the synthetic relationship — and got worse in proportion.

**Interpretation.** A vigorous canopy genuinely implies a high yield for *that
field*, but the label is a state mean reflecting area-weighting, variety and
input use across a whole region. The two cannot be reconciled by any synthetic
prior. **Field-level yield labels, not architecture work, are the binding
constraint.**

---

## 5a. Real-outcome validation, via VDSA (partial)

`data/raw/harvest_outcomes/` was empty for most of this project and one input
could not be derived, downloaded, or modelled - see that directory's README.
It is no longer empty: 848 real plot-seasons (712 paddy, 136 wheat) were
obtained from ICRISAT's Village Dynamics in South Asia (VDSA) panel, 2010-2013,
Bihar/Jharkhand/Odisha, via free registration at vdsa.icrisat.org
(`ingestion/vdsa_outcomes.py`). Each record has a REAL sowing date, REAL
harvest date and REAL measured yield, collected by field investigators
visiting monthly - not survey recall.

**This does not fully satisfy the original blocker.** VDSA has no "recommended
window vs actual harvest vs fixed-date baseline" comparison, because no such
system existed when it was collected - it is a historical panel survey, not a
record of a deployed recommendation. And its 12 villages are in Bihar,
Jharkhand and Odisha, not this project's 7 named fields, so it validates the
METHOD on a different population, not those specific fields end to end.
Attempting to geocode the 12 village names to satellite pixels was tried and
abandoned: OpenStreetMap matched only 6 of 11, none with confirmed certainty
(India has many same-named villages), and a wrong match would silently corrupt
a plot-level comparison - worse than not attempting it.

**What it DOES support, with no geolocation risk:** a real check of this
project's own harvest-timing assumptions against real farmer behavior
(`evaluation/outcome_validation/vdsa_timing_check.py`).

| Crop | n | Real sow-to-harvest (median) | Old `season_len // 2` bound | That bound's percentile among real harvests |
|---|---|---|---|---|
| Paddy | 712 | 128 days | 77 days | **4th** |
| Wheat | 136 | 135 days | 70 days | **1st** |

Real growers harvested later than the project's old harvest-timing lower
bound on 96-99% of 848 real seasons. This independently corroborates the
IRRI-window finding in S6 below using a completely different source (real
farmer behavior vs published agronomic guidance) - both say the same bound was
far too early, which is why it was replaced.

## 5b. Real-outcome validation, via VDSA SATIndia (matched satellite + weather + outcomes)

A second, stronger real-outcome dataset was obtained from VDSA's SATIndia
round, which - unlike the EastIndia round in S5a - carries real VILLAGE,
DISTRICT and STATE metadata per site (`Gen_Info.xlsx`), so villages could be
geocoded with real confidence rather than abandoned as in S5a. Three villages
matched their district/state metadata exactly on lookup:

| Village | District, State | Real plot-seasons |
|---|---|---|
| Kalman | Solapur, Maharashtra | 471 |
| Kanzara | Akola, Maharashtra | 434 |
| Shirapur | Solapur, Maharashtra | 333 |

These are not arbitrary villages - Kalman, Kanzara, Kinkheda and Shirapur are
ICRISAT's original 1975 Village Level Studies sites, continuously surveyed
for 50 years and extensively used in published agricultural economics
research.

For these 3 villages, ALL THREE inputs are now real and matched to the same
location: real Landsat NDVI/EVI/NDWI (174/95/82 scenes respectively, cropland
-masked), real ERA5-Land daily weather (2190 days each, 2009-2014), and 1,238
real plot-season outcomes (sow date, harvest date, yield) extracted from
`Cult_ip_MH` (operations) joined to `2.Crop_info_op` (output), 2009-2013.

Crop mix (Sorghum, Pigeonpea, Soybean, Onion, Chickpea, Wheat) matches these
villages' documented rainfed semi-arid cropping pattern. Yield range
0.10-14.8 t/ha spans grain crops (~0.5-3 t/ha) and onion (~12-13 t/ha, a
correct range for onion, not an outlier).

Building this required fixing three real, non-obvious data-quality issues in
VDSA's own export, each verified before being worked around rather than
assumed:

1. **Household IDs carry different year digits in the input vs output
   files** (`IMH10A0001` in `Cult_ip_MH`, `IMH09A0001` in `2.Crop_info_op` for
   the SAME household) - joining on the full ID silently returns nothing;
   joining after stripping the year and pooling across all years silently
   over-matches (7053 "matches" for 973 real events, confirmed and rejected).
   The fix joins within one downloaded file-pair at a time, matched by
   real download timestamp, never pooled.
2. **The plot-code column's name is inconsistent across files** - `PLOT_CO`
   in some, `PLOT_CODE` in others, on both the input and output sides
   independently.
3. **The yield-quantity column mixes numeric and whitespace-only-string
   representations of blank** across the four downloaded crop-output files,
   which crashes a naive numeric multiplication rather than silently
   producing wrong numbers - caught at that point rather than coerced away
   without checking.

Next: replay these 3 villages' real inputs through the trained forecast model
and RL policy, and measure agreement against the real recommended-vs-actual
comparison this project could not build for its original 7 fields.

## 5c. Replaying real SATIndia inputs through the trained model — real agreement, and a real bug it exposed

`evaluation/outcome_validation/satindia_replay.py` runs the 3 villages' real
Landsat + ERA5 + SoilGrids (fetched for these village polygons the same way
as S5b) through the trained yield-forecast model and both harvest-timing
policies (RL and the static optimizer), then compares the recommended week
against the real harvest date.

**Scope**: only WHEAT plot-seasons are used (120 of 1,238). The forecast
model and the RL policy's agronomic window
(`models/heads/rl_harvest_policy/agronomic_window.py`) were both built for
this project's two crop archetypes, rice and wheat - these villages'
dominant crops (sorghum, soybean, pigeonpea, onion, cotton) have no basis for
comparison against a model that never saw them. Of the 120 wheat
plot-seasons, 35 have a fully-observed real satellite window (the other 85
fall outside the 2010-2014 Landsat pull, or still have an unfilled NDVI gap
after the same `MAX_INTERPOLATION_WEEKS=3` cap used everywhere else in this
project - dropped, not filled). All 35 are the same 2013-14 rabi wheat
season, split Kalman (2), Kanzara (18), Shirapur (15).

Pooled across all 35, agreement looks poor - static optimizer MAE 7.7 weeks
against real harvest timing, RL policy MAE 7.1 weeks. Splitting by village
shows why, and it is not a uniform failure:

| Village | n | mean real harvest week | mean recommended week | MAE (weeks) |
|---|---|---|---|---|
| Kanzara | 18 | 15.2 | 12.7 | **2.46** |
| Kalman | 2 | 15.6 | 4.5 | 11.07 |
| Shirapur | 15 | 18.7 | 5.1 | 13.64 |

Kanzara's 2.46-week MAE (56% of plots within 2 weeks) is a genuinely
plausible zero-shot result: this model was trained entirely on 7 fields in
Punjab, Tamil Nadu, West Bengal and Andhra Pradesh, never on Maharashtra, and
its predicted mean yield for Kanzara (2.68 t/ha) lands close to the real mean
(2.62 t/ha, MAE 0.67 t/ha).

Kalman and Shirapur fail for a specific, diagnosed reason, not a vague
"domain gap." `agronomic_window.py`'s heading proxy takes the week of peak
NDVI within the observed season as the heading date. On Kanzara's real NDVI
curve, that peak sits at week 8 (~56 days after sowing - a plausible wheat
heading date) and the resulting window tracks real harvest timing. On Kalman
and Shirapur, NDVI is already at its highest value in week 0 - the week of
sowing itself, most likely residual greenness from the plot's prior kharif
crop - and then declines for the rest of the observed window, so the "peak"
the proxy locks onto is week 0, not a wheat canopy peak that may never fully
form within the pulled window. That yields a `min_harvest_week` of 4-5,
agronomically meaningless for a wheat crop that needs 90-120 days, and both
policies duly return that same too-early week (`static_recommended_week` and
`rl_recommended_week` sit within 1-2 weeks of `min_harvest_week` on nearly
every Kalman/Shirapur row - the bound is binding again, the same failure mode
`agronomic_window.py`'s docstring describes fixing for the original 7
fields, now recurring on real field data the proxy was not validated
against).

This is exactly the kind of finding real-outcome validation exists to
surface: a peak-NDVI heading proxy that is only safe when the observed
window is known to start near bare soil, which held for this project's
original satellite pulls but does not hold in general on real smallholder
plots with crop rotation. It is reported here rather than patched, so the
failure stays visible instead of being quietly smoothed over by widening the
window or discarding the two affected villages.

Per-plot output: `evaluation/outcome_validation/satindia_replay_records.csv`.
Summary: `evaluation/outcome_validation/satindia_replay_results.json`.

## 5d. The label-granularity sweep — first real run

`evaluation/label_granularity/run_granularity_sweep.py --seeds 5`, the
project's central planned experiment (S5's finding motivated it: giving
synthetic pretraining a correct weather-to-yield relationship made real
accuracy monotonically worse, which points at label resolution rather than
sample size or architecture as the deep model's real problem). It ran
end-to-end for the first time after this session's soil, interpolation, and
causal-masking fixes.

A district tier now exists -
`data/raw/yield_labels/district/{F001..F006}_yield_labels.csv`, built by
`ingestion/build_district_yield_labels.py` from the same data.gov.in
district-wise crop statistics used for the granularity sweep's district-scale
Landsat/weather pull, filtered to each field's real district and season. It
has a real, stated limitation: this district source stops in 2013-2014 for
these districts, while the real satellite/weather data runs 2019-2026, so
every real season falls back to the nearest available year rather than an
exact match - the district tier tests spatial resolution only, with no
temporal label variation, unlike the national and state tiers. F007 (Punjab
wheat) has no district-level source and is correctly absent.

Comparable fields across all three tiers: F004, F005, F006 (Punjab, West
Bengal, Andhra Pradesh rice) - n=11 seasons at every tier, holding fields,
satellite/weather inputs, and models fixed, varying only the label's spatial
resolution.

```
tier                         Naive           Random Forest                 XGBoost             HarvestWise
----------------------------------------------------------------------------------------------------------
national             0.812 +/-0.024           0.292 +/-0.165           0.307 +/-0.206           0.337 +/-0.179
state                0.555 +/-0.007           0.983 +/-0.266           1.004 +/-0.281           1.065 +/-0.368
district              0.674 +/-0.024           0.285 +/-0.107           0.329 +/-0.189           0.295 +/-0.228

Deep-model gap to the best tree ensemble (positive = deep model is worse):
  national   +0.045 t/ha
  state      +0.081 t/ha
  district   +0.009 t/ha
```

Stated plainly: this is **not** a clean monotonic curve - state (+0.081) is
worse than national (+0.045), not a step in between it and district. The
state tier's labels (CEIC-sourced, mean 3.93 t/ha across the 11 seasons) sit
on a visibly different scale than national and district's (means 2.74 and
2.88 t/ha) for the same fields and years, which is a real confound: three
tiers here differ in more than resolution alone. That confound is stated, not
smoothed into a trend line that would overclaim what 11 seasons and 3 fields
can show.

What the result does support: at the finest tier tried, district, the deep
model's gap to the best tree ensemble (+0.009 t/ha) is an order of magnitude
smaller than at national (+0.045) or state (+0.081), and is well inside the
~0.1-0.2 t/ha seed spread at every tier - i.e. genuinely indistinguishable
from the tree ensembles at district resolution, where it is clearly, if not
dramatically, behind at the coarser tiers. Two data points and a confound
between them is a direction, not a proven threshold - the honest framing is
"district-resolution labels are the first tier at which this deep model
stops being worse than a tree ensemble," not "granularity smoothly closes the
gap."

Raw output: `evaluation/label_granularity/results.json`.

## 6. Harvest-window policy — the result that holds

```
python -m evaluation.statistical_tests.run_rl_vs_static
```

| | |
|---|---|
| Paired real trajectories | 28 |
| Mean RL outcome | 2.7414 |
| Mean static outcome | 2.7415 |
| Mean difference | −0.0000 t/ha |
| Wilcoxon p | 0.317 |
| Cohen's d | −0.189 |
| Significant at α=0.05 | No |

**The RL policy matches the static optimizer, and does not beat it.** The
defensible claim is that a policy with a 4-week forecast horizon matches a
grid search with full-season foresight — an information-constraint result, not
an accuracy win.

This comparison is fair only because two earlier confounds were fixed: the
static optimizer charged delay cost from season start while the RL env charged
from `min_harvest_week` (an earlier "RL wins on all 28 trajectories,
p<0.0001" result was entirely this artifact), and PPO optimised a discounted
return (γ=0.99) while evaluation measured undiscounted, which taught the agent
to always harvest immediately.

---

## 7. Correctness fixes with measured effect

**Temporal leakage in the backbone.** `SpatioTemporalBackbone` used
`nn.TransformerEncoder` with no attention mask, so each week's forecast
attended to *later* weeks of the same season — data unavailable at that week's
real decision time.

| | Before | After |
|---|---|---|
| Δ at week 0 from corrupting only week 19 | 1.3e−3 t/ha | **0.0** |
| Weekly curve variation (% of mean yield) | 0.91% | 5.71% |
| Shock-season MAE | 0.429 | 0.447 |

The fix is necessary for validity but did **not** improve accuracy — the
leaked information was barely being used.

**Precipitation units.** ERA5 `tp` is metres accumulated over the preceding
hour; it was being read as mm/day, giving 54.6 mm/yr for Punjab against a
~650 mm/yr climatology. This silently disabled the 25 mm weather-risk term in
both the RL reward and the static optimizer. Corrected (×1000×24); totals
still run ~2× high at the driest sites, which is stated rather than tuned away.

**Fabricated climate labels.** The benchmark's original `YEAR_LABELS` contained
invented entries (2019 "drought", 2021 "heatwave"). Replaced with ERA5-derived
per-field labels.

---

## 8. Climate sensitivity — an open problem

```
GET /scenario/F004?temp_shift_c=4&rainfall_change_pct=-40
```

| Scenario | Predicted yield change |
|---|---|
| +1 °C, −10% rain | −0.49% |
| +2 °C, −20% rain | −0.95% |
| +3 °C, −30% rain | −1.35% |
| +4 °C, −40% rain | −1.68% |

A −1.7% response to a severe drought-and-heat scenario is not consistent with
a climate-adaptive framing. This follows directly from §5: the model has
learned almost no weather→yield relationship, because there is none in the
labels it was trained against.

---

## 9. What is NOT established

- Real-outcome validation. `data/raw/harvest_outcomes/` is **empty**; the
  "recommended vs. actual harvest" claim has no evidence.
- Any accuracy advantage for the multimodal architecture.
- Any benefit from multimodal fusion.
- Meaningful climate adaptivity.
- The climate-shock benchmark ordering (single-seed, n=4).

## 10. What IS established

- A reusable, ERA5-derived, per-(field, year) Climate-Shock Benchmark across
  4 states and 2 crops, with a scoring harness and released splits.
- An RL harvest-timing policy that matches a full-foresight optimizer under a
  4-week information constraint.
- A rigorous negative result: multimodal deep learning fails to beat
  gradient-boosted trees *or* a mean-predictor for crop yield forecasting when
  labels are regional averages — with the mechanism identified in §5.
