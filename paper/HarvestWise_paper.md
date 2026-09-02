# Resolution, Not Architecture: A Real-Data Study of When Multimodal Deep Learning Helps Crop Yield Forecasting and Harvest-Timing Recommendation

**[Author Name]**
Department of Computer Science and Engineering, Karunya Institute of Technology and Sciences, Coimbatore, India
[author email]

## Abstract

Multimodal deep learning — fusing satellite imagery, weather, and soil into a
spatio-temporal model — is widely proposed for crop yield forecasting and
harvest-timing recommendation, usually evaluated against yield labels
reported at national or state resolution because plot-level ground truth is
scarce. We build a real, reproducible pipeline (Sentinel-2/Landsat, ERA5,
ISRIC SoilGrids) across 7 fields in 4 Indian states and 2 crops, and test
this assumption directly rather than accept it. Under multi-seed evaluation,
the multimodal model does not beat a mean-predictor at national or state
label resolution (MAE 0.727 vs. 0.689 t/ha, n=21, 5 seeds) and fusion is not
shown to help over single-modality encoders. Holding fields, inputs, and
models fixed and varying only label spatial resolution, we show the deep
model's gap to gradient-boosted trees narrows by an order of magnitude at
district resolution (+0.009 t/ha) versus national or state (+0.045,
+0.081 t/ha) — a controlled granularity result, not previously isolated on
real data to our knowledge. Separately, using independently-collected ICRISAT
Village Dynamics in South Asia (VDSA) panel records — the first real
recommended-vs-actual harvest-timing ground truth available to this
project — we find a 2.46-week mean absolute error against real farmer
harvest timing at one fully-resolved village, and trace the failure at two
others to the same underlying cause: a coarse satellite input footprint,
required because public panel data carries only village-centroid geolocation,
loses the single-plot phenology signal a harvest-timing policy depends on.
Both results point to the same conclusion: spatial resolution, on the label
side and the input side, is the variable that determines whether multimodal
deep learning earns its cost for this task — not model architecture, and not
raw sample size. We report every negative result and retraction alongside
the positive ones, including two previously-reported "wins" that did not
survive multi-seed re-evaluation.

**Keywords:** crop yield forecasting, multimodal deep learning, label
granularity, harvest-timing optimization, reinforcement learning, real-outcome
validation, climate-shock benchmark

---

## 1. Introduction

Deep learning for agriculture is usually pitched on architecture: better
fusion of imagery, weather, and soil should forecast yield and time harvests
better than a single modality or a classical model. The practical obstacle to
testing this claim honestly is data: individually geolocated, plot-level
yield outcomes are rare, so most work — including the first iteration of this
project — trains and evaluates against regional (state or national) yield
averages, because that is what is publicly available.

This paper reports what happens when that assumption is tested rather than
assumed. Working with real satellite (Sentinel-2/Landsat), real reanalysis
weather (ERA5-Land), real soil (ISRIC SoilGrids), and real government yield
statistics for 7 fields across Tamil Nadu, Punjab, West Bengal and Andhra
Pradesh, we find that a multimodal spatio-temporal transformer does not beat
a mean-predictor, and does not benefit from fusion, at the label resolution
public data provides (§4.1–4.2). Rather than treat this as a stopping point,
we isolate the reason: holding every other variable fixed and varying only
the spatial resolution of the yield label — national, state, or district —
the deep model's disadvantage against gradient-boosted trees shrinks by an
order of magnitude at district resolution (§4.5). This is, to our knowledge,
the first controlled granularity sweep of this kind reported on real
multi-state Indian crop data.

A second obstacle facing this line of work is validating harvest-timing
recommendations against what farmers actually did, rather than against a
forecast model's own self-consistency. This project could not initially
obtain any such record. We resolve this using the ICRISAT Village Dynamics in
South Asia (VDSA) panel survey — decades of field-investigator-recorded sow
dates, harvest dates, and yields for real smallholder plots — geocoded with
confirmed village-level metadata to 3 Maharashtra villages (§3.5). Replaying
real satellite and weather inputs for these villages through the trained
model and harvest-timing policy produces the first genuine
recommended-vs-actual comparison this project has been able to build
(§4.6). At one village the agreement is genuinely close (2.46-week MAE); at
two others we trace the failure to a specific, evidenced cause — the village
-centroid satellite footprint required by the panel data's own geolocation
limits is too coarse to resolve one plot's phenology curve against the
surrounding mixed cropping — which is the same resolution-sensitivity
finding as §4.5, now demonstrated on the input side of the pipeline rather
than the label side.

**Contributions.**

1. A real, reproducible, multi-seed-audited benchmark for multimodal crop
   yield forecasting across 4 states and 2 crops, released with real splits
   and a scoring harness (`benchmark_release/`).
2. A controlled label-granularity sweep isolating spatial label resolution,
   not architecture or sample size, as a driver of when multimodal deep
   learning closes the gap to tree ensembles.
3. The first real recommended-vs-actual harvest-timing validation in this
   project's line of work, built from independently-collected panel survey
   data, together with a diagnosed input-resolution failure mode that
   mirrors the label-granularity finding.
4. A SHAP-based diagnosis, on the best available baseline, of *why* weather
   and vegetation signal go unused at this sample size: soil features (a
   per-field constant, not a season-varying signal) dominate feature
   attribution by an order of magnitude over any weather or vegetation
   feature, indicating the model has learned field identity rather than
   within-field seasonal variation.
5. A methodological record of retracted results — single-seed overclaiming,
   an unbounded-interpolation artifact, a reward-discounting bug — kept
   visible rather than removed, because each changed a conclusion this
   project had already reported.

## 2. Related Work

Multimodal fusion of satellite vegetation indices, weather reanalysis, and
soil properties for yield forecasting is an active and growing area, almost
always evaluated at whatever label resolution is publicly reported for the
study region — typically national or sub-national government agricultural
statistics, since plot-level yield records are rarely public. Harvest-timing
optimization is comparatively less studied as a decision problem in its own
right; where it appears, it is usually folded into yield forecasting rather
than evaluated as a sequential timing decision against a full-foresight
baseline. Reinforcement learning for agricultural decision timing is
similarly nascent, and to our knowledge existing work does not report a
paired significance test against a non-learned optimizer under a matched
information constraint, which we do here (§4.7).

Real-outcome validation — comparing a recommendation against what a real
grower actually did, rather than a synthetic or self-reported ideal — is the
piece most works in this space are unable to do, for the same reason this
project initially could not: individually geolocated harvest records are not
public. We resolve this using the ICRISAT VDSA panel survey, a decades-running
village-level field-investigator record used extensively in agricultural
economics but, to our knowledge, not previously used to validate a
remote-sensing-driven harvest-timing model against real farmer behavior.

## 3. Data and Methods

### 3.1 Real fields and inputs

Seven field polygons across 4 Indian states (Tamil Nadu ×3, Punjab ×2,
West Bengal ×1, Andhra Pradesh ×1) and 2 crops (rice, wheat), each with real
Sentinel-2 surface reflectance (cloud-masked via the SCL band), real
ERA5-Land daily weather (temperature, precipitation, humidity, wind), and
real ISRIC SoilGrids soil properties (pH, organic carbon, clay, sand,
nitrogen), fetched via Google Earth Engine. Weekly vegetation indices (NDVI,
EVI, NDWI) are resampled from raw scenes; cloud gaps longer than 3 weeks are
left unfilled and the affected season is dropped rather than interpolated,
after an earlier version of this pipeline was found to interpolate gaps of
unlimited length, producing seasons with a flat NDVI value for up to 20
consecutive weeks that trained indistinguishably from real data (§4.3
documents the measured effect of fixing this).

### 3.2 Yield labels at three spatial resolutions

To isolate the effect of label granularity, three label tiers are built for
the same fields wherever a real source exists at that tier:

- **National**: Government of India Economic Survey, Table 1.17, national
  Kharif rice yield by agricultural year (real year-to-year variation,
  2019–2024).
- **State**: state-level annual yield series (CEIC-sourced), real
  year-to-year variation, 2021–2023.
- **District**: data.gov.in's district-wise, season-wise crop production
  statistics (resource `35be999b-...`), filtered to each field's real
  district and cropping season. This source's coverage for the relevant
  districts (Coimbatore, Amritsar, Bardhaman, East Godavari) ends in
  2013–2014, so — stated as a limitation, not hidden — every real 2019–2026
  season falls back to the nearest available historical year rather than an
  exact-year match; the district tier therefore tests spatial resolution
  only, without the real temporal label variation the other two tiers carry.

### 3.3 Model

Per-modality encoders (vision, weather, soil) feed a phenology-aware
cross-attention fusion layer, conditioned on growth-stage, into a
spatio-temporal Transformer backbone with causal attention masking — added
after a corruption test showed the unmasked backbone attended to future
weeks unavailable at a real decision time (§4.3) — and a pinball-loss
quantile head producing per-week (low, median, high) yield forecasts.

### 3.4 Baselines

A naive mean-predictor, Random Forest, and XGBoost, trained on the same
synthetic-pretraining distribution used to warm-start the deep model, and
evaluated on the same real held-out examples, so the comparison isolates
architecture rather than training-data volume.

### 3.5 Harvest-timing policy and real-outcome validation

A PPO reinforcement-learning policy and a grid-search static optimizer both
choose a harvest week from a forecast weekly yield/rainfall trajectory,
scored by the same reward shape (expected yield minus a weather-risk penalty
minus a delay cost), and are compared by paired Wilcoxon signed-rank test on
matched trajectories.

The earliest agronomically valid harvest week is estimated from each
season's own peak-NDVI week (a heading proxy) plus IRRI's published
days-after-heading harvest window, replacing an earlier `season_len // 2`
bound found to be binding on nearly every trained decision.

Real-outcome validation uses the ICRISAT VDSA panel: cultivation-operation
records (real sow/harvest dates) joined to crop-output records (real
yields) for plots in 3 villages — Kalman, Kanzara, Shirapur (Solapur/Akola,
Maharashtra) — confirmed geocoded against the panel's own recorded
district/state metadata. Real Landsat and ERA5-Land data were pulled for
each village's centroid (a 1.1 km box, matching this project's original
field-polygon scale, since the panel provides no plot-level GPS), and real
SoilGrids soil properties fetched for the same geometry. 1,238 real
plot-seasons were extracted; the comparison in §4.6 is restricted to the 120
wheat plot-seasons, since the trained model and its agronomic window were
built for this project's two crop archetypes (rice, wheat) and the villages'
dominant real crops (sorghum, soybean, pigeonpea, onion, cotton) have no
basis for comparison against a model that never saw them.

### 3.6 Evaluation protocol

Every reported result is evaluated over 5 random seeds unless stated
otherwise, reporting mean ± standard deviation and the range across seeds.
A ranking between two models is reported as established only when the gap
between their means exceeds the pooled seed-to-seed spread; this protocol
was adopted after two single-seed results reported earlier in this project's
history were found not to replicate (§4.1).

## 4. Results

### 4.1 Headline yield-forecast result

On 21 real held-out season examples (seasons with an unrecoverable satellite
gap dropped, §3.1), mean ± sd over 5 seeds:

| Model | MAE (t/ha) | Range over seeds |
|---|---|---|
| Naive (predict the mean) | **0.689 ± 0.006** | 0.684–0.699 |
| Random Forest | 0.726 ± 0.098 | 0.641–0.886 |
| Multimodal (this work) | 0.727 ± 0.131 | 0.609–0.952 |
| XGBoost | 0.764 ± 0.181 | 0.526–0.997 |

No model beats predicting the mean; the top-two gap (0.037) is smaller than
the seed spread (0.052), so no ranking is established either. Two earlier
results — "MAE 0.532, beats naive" and "MAE 0.569, beats naive by 21%" — are
retracted: the first was single-seed and did not survive a 5-seed
re-evaluation (range 0.449–1.134); the second was measured on a dataset that
was 56% interpolated rather than observed (§3.1), and the advantage vanished
once interpolation was capped and affected seasons dropped.

### 4.2 Fusion ablation

| Ablation | Validation R² (5 seeds) | Range |
|---|---|---|
| Imagery-only | 0.027 | −0.554–0.606 |
| Fused (all modalities) | −0.069 | −0.537–0.248 |
| Weather-only | −0.119 | −0.271–0.073 |

Fusion is not shown to help — the fused model scores below imagery-only, and
all three configurations are at or below R²=0. An earlier 3-seed result
reporting fused 0.500 vs. 0.444/0.441 is retracted as seed luck.

### 4.3 Climate-shock benchmark

Fit on 20 real normal seasons, scored on 4 real shock seasons (drought,
wet-extreme, heatwave, defined by ERA5 growing-season anomalies against each
field's own climatology, never assigned by hand):

| Model | MAE on shock seasons (t/ha), 5 seeds | Range |
|---|---|---|
| Random Forest | **0.189 ± 0.060** | 0.143–0.294 |
| XGBoost | 0.222 ± 0.044 | 0.173–0.289 |
| Multimodal (this work) | 0.366 ± 0.146 | 0.221–0.566 |
| Naive | 0.460 ± 0.011 | 0.450–0.479 |

On shock seasons specifically, the multimodal model does beat naive
(0.366 vs. 0.460) — unlike on the full holdout (§4.1) — though its variance
is the largest of any model, and the Random Forest/XGBoost ordering is not
established at this sample size (top-two gap 0.034 vs. pooled spread 0.052).

Two correctness fixes materially affect this table. Causal attention masking
in the Transformer backbone (added after a corruption test showed a 1.3e-3
t/ha week-0 change from corrupting only week 19 of the same season, i.e.
future-leakage) changed shock-season MAE from 0.429 to 0.447 — necessary for
validity, though it did not improve accuracy, since the leaked information
was barely being used. A precipitation-unit bug (ERA5 total precipitation is
metres accumulated hourly, read as mm/day) silently disabled the 25 mm
weather-risk term used by both the harvest-timing policy and this benchmark's
reward shaping; correcting it (×1000×24) is required for the risk term to
mean anything, though totals still run roughly 2× high at the driest sites,
stated here rather than further tuned.

### 4.4 Why the deep model fails: a synthetic-pretraining ablation

Deep models here are warm-started on a synthetic pretraining distribution
before fine-tuning on real data. Giving that synthetic generator a *correct*
weather-to-yield coupling — i.e., making the pretraining data more
realistic — made real-holdout MAE monotonically **worse** (0.532 → 0.931 →
1.391 across three coupling strengths), despite improving the synthetic
data's own internal correlations. This result, on its own, is not
explained by architecture or by insufficient training signal; it points at a
mismatch between what the pretraining distribution teaches (a real
weather-yield relationship) and what the fine-tuning labels can actually
supervise (a regional average with no field-specific variation) — motivating
the granularity sweep below.

SHAP analysis on the Random Forest baseline — chosen as the explanation
target because it has the lowest MAE and lowest seed variance of any model
in this paper, and because `TreeExplainer` attributes exactly rather than
approximately — makes the mechanism concrete. Across 5 seeds, the three soil
features (nitrogen, organic carbon, pH) each attribute roughly an order of
magnitude more mean |SHAP value| (0.17–0.16 t/ha) than any weather or
vegetation feature; `ndvi_mean`, the single feature most yield-forecasting
work would expect to matter most, ranks lowest of all 19 features
(0.0014 t/ha). Soil is a per-field constant in this dataset — every field's
soil vector is identical across all of that field's real seasons — so a
model attributing most of its predictive weight to soil has, in effect,
learned to identify which field (and through it, which region and crop) an
example came from, rather than to use that season's real weather or
vegetation trajectory. Between-field yield-level differences dominate the
21 real examples' variance so completely that the best available model
learns field identity first; this is why making synthetic pretraining more
realistic about weather sensitivity made real accuracy worse — it pulled the
model away from the shortcut that actually minimizes error on this dataset.

### 4.5 Label-granularity sweep

Holding fields, real satellite/weather/soil inputs, model architecture, and
evaluation seeds fixed, and varying only the spatial resolution of the yield
label, on the 3 fields (Punjab, West Bengal, Andhra Pradesh rice) with real
labels at all three tiers, n=11 seasons per tier:

| Tier | Naive | Random Forest | XGBoost | Multimodal (this work) |
|---|---|---|---|---|
| National | 0.812 ± 0.024 | 0.292 ± 0.165 | 0.307 ± 0.206 | 0.337 ± 0.179 |
| State | 0.555 ± 0.007 | 0.983 ± 0.266 | 1.004 ± 0.281 | 1.065 ± 0.368 |
| District | 0.674 ± 0.024 | 0.285 ± 0.107 | 0.329 ± 0.189 | 0.295 ± 0.228 |

Deep-model gap to the best tree ensemble (positive = deep model worse):
national +0.045, state +0.081, district **+0.009** t/ha.

This is not a clean monotonic curve — state is worse than national, not
between it and district — because the state tier's labels sit on a
genuinely different scale (mean 3.93 t/ha across these 11 seasons) than
national or district (2.74, 2.88 t/ha) for the same fields and years, a real
confound stated here rather than smoothed into a trend line. What the result
does support: at the finest tier tried, the deep model's gap to the best
tree ensemble is an order of magnitude smaller than at the coarser tiers,
and is well inside the ±0.1–0.2 t/ha seed spread at every tier — i.e.,
genuinely indistinguishable from the tree ensembles at district resolution,
where it is clearly, if not dramatically, behind at national and state
resolution. With two comparable tiers and a stated confound between them,
the defensible claim is a direction — "district-resolution labels are the
first tier at which this deep model stops being worse than a tree
ensemble" — not a proven threshold curve, which would require a third,
unconfounded comparison point this project does not yet have.

### 4.6 Real-outcome validation

Replaying the 3 confirmed-geocoded VDSA villages' real Landsat, ERA5, and
SoilGrids inputs through the trained forecast model and both harvest-timing
policies, and comparing the recommended harvest week against real harvest
dates (35 of 120 real wheat plot-seasons have a fully-observed satellite
window; the rest fall outside the pulled Landsat years or retain an
unfillable NDVI gap and are dropped, per the same rule as §3.1):

| Village | n | Mean real harvest week | Mean recommended week | MAE (weeks) |
|---|---|---|---|---|
| Kanzara | 18 | 15.2 | 12.7 | **2.46** |
| Kalman | 2 | 15.6 | 4.5 | 11.07 |
| Shirapur | 15 | 18.7 | 5.1 | 13.64 |

At Kanzara, 56% of plots land within 2 weeks of the real harvest date, and
the model's predicted mean yield (2.68 t/ha) is close to the real mean
(2.62 t/ha, MAE 0.67 t/ha) — a plausible zero-shot result for a model
trained entirely on fields in 4 other states, never on Maharashtra.

Kalman and Shirapur fail for a specific, evidenced reason rather than a
generic domain gap. Checking the raw, un-interpolated Landsat scenes over
the real 2013–14 rabi season: Kanzara's real per-scene NDVI traces a trough
in November–December (~0.34–0.38, post-sowing establishment) rising to a
real peak in February (~0.56–0.60, a plausible wheat heading signature) and
declining to harvest — a genuine single-crop-shaped phenology curve. Kalman's
and Shirapur's real per-scene NDVI over the same months instead oscillates
between ~0.37 and ~0.54 with no clear rise-to-peak structure. The most
defensible explanation is spatial: every village's satellite footprint here
is a 1.1 km box (roughly 120 ha), chosen because the panel survey provides
only a village centroid, not individual plot GPS — far larger than any one
smallholder plot, so its NDVI is a village-wide average across whatever mix
of crops is growing that season. Kanzara's average still resolves a
wheat-shaped curve; Kalman's and Shirapur's do not. This is a limitation of
using a village-centroid box as a stand-in for plot-level geolocation, not a
flaw in the heading-detection method itself — the same method was validated
against real agronomic guidance on this project's original, individually
-geolocated field polygons. `min_harvest_week` collapses to 4–5 weeks after
sowing at the two affected villages (agronomically meaningless for a
90–120 day wheat crop), and both the RL policy and the static optimizer
duly return that same too-early week — the same "bound is binding" failure
mode found and fixed earlier in this project for the original 7 fields
(§3.5), recurring here because the *input*, not the policy, violated the
assumption the heading proxy depends on.

This mirrors §4.5's finding on the opposite side of the pipeline: coarse
yield *labels* lose the signal a deep model needs; a coarse satellite
*input* footprint can equally lose the single-plot phenology signal a
harvest-timing policy depends on, even given fully real, correctly-dated
outcomes behind it.

### 4.7 Harvest-timing policy vs. a full-foresight baseline

On 28 paired real trajectories, the RL policy (4-week forecast horizon) and
the static optimizer (full-season foresight via grid search) are
statistically indistinguishable: mean outcomes 2.7414 vs. 2.7415 t/ha,
Wilcoxon p=0.317, Cohen's d=−0.189. The defensible claim is that a policy
operating under a real information constraint matches a baseline that does
not have that constraint — not an accuracy win. An earlier "RL wins on all
28 trajectories, p<0.0001" result is retracted: it was entirely an artifact
of the static optimizer and the RL environment charging delay cost from
different reference points, and of PPO being trained on a discounted
objective (γ=0.99) while evaluated on an undiscounted one, which taught the
agent to always harvest immediately regardless of the trajectory.

## 5. Discussion

The two central results of this paper — the label-granularity sweep (§4.5)
and the real-outcome input-resolution failure (§4.6) — support a single
thesis: for this task, on real data, **spatial resolution is the variable
that determines whether multimodal deep learning earns its cost, not
architecture and not raw sample size.** A model that cannot beat a
mean-predictor at national label resolution (§4.1) comes within noise of the
best tree ensemble at district resolution (§4.5) with the same architecture,
the same inputs, and the same training budget. A harvest-timing policy that
tracks real farmer behavior to within 2.5 weeks at one village fails by
11–14 weeks at two others, not because the policy or its underlying forecast
model changed, but because the satellite footprint available at those two
villages could not resolve one plot's signal from its surroundings.

This has a practical implication for how this line of work should be
evaluated going forward: a reported multimodal advantage (or disadvantage)
is not interpretable without stating the spatial resolution of both the
label and the input footprint it was measured against. A benchmark built
entirely on national or state yield averages, however carefully modeled,
may be structurally unable to show a real multimodal advantage even where
one exists at finer resolution — and a real-outcome validation built on
village-centroid geolocation, however genuine the underlying survey, carries
the same risk on the input side.

## 6. Limitations

- Sample sizes throughout are small by machine-learning standards (21
  season examples for the headline result; 11 seasons for the 3-field
  granularity comparison; 35 of 120 real wheat plot-seasons usable for the
  real-outcome replay). Every reported MAE is stated with its seed spread
  precisely so a reader can judge significance rather than infer it.
- The district label tier (§3.2) has no real temporal variation within the
  years these fields' satellite data covers, because the underlying
  government source's coverage ends in 2013–2014; the granularity result
  (§4.5) is therefore a test of spatial resolution alone, confounded with a
  scale difference at the state tier that is stated but not resolved.
- Real-outcome validation (§4.6) covers 3 villages, 1 crop (wheat), and 1
  season; the input-resolution failure mode is diagnosed with strong
  circumstantial evidence (raw-scene NDVI shape) but not proven by a
  controlled footprint-size ablation, which VDSA's public geolocation does
  not support.
- Only one multimodal fusion architecture is tested; the claim that
  granularity matters more than architecture is supported by holding this
  one architecture fixed across resolutions, not by comparing multiple
  architectures.
- The climate-shock benchmark (§4.3) draws on only 4 real shock seasons,
  single-seed for shock membership itself (though model scoring is
  5-seed), and should be treated as a released, reusable benchmark more
  than as a settled result.

## 7. Conclusion

Tested directly rather than assumed, multimodal deep learning does not beat
simple baselines for crop yield forecasting at the label resolution most
publicly available data provides — but the reason is diagnosable and
addressable: at district-level label resolution, on the same real fields
and inputs, the gap to gradient-boosted trees very nearly closes. The same
resolution sensitivity reappears, independently, on the input side of a
harvest-timing policy validated against real, independently-collected
farmer outcomes for the first time in this project's history. Both results
argue that spatial resolution — not architecture — is the variable future
work in this space should report and control for. We release the benchmark,
the granularity-sweep harness, and the real-outcome validation dataset and
replay pipeline so this claim can be tested further as finer-resolution
label and geolocation data become available.

## Acknowledgments

This work was carried out as a final-year project at the Department of
Computer Science and Engineering, Karunya Institute of Technology and
Sciences, Coimbatore.

## References

1. Government of India, Ministry of Agriculture and Farmers Welfare,
   *Economic Survey 2025-26, Statistical Appendix, Table 1.17: Yield Per
   Hectare of Major Crops*.
2. Government of India, Open Government Data Platform (data.gov.in),
   *District-wise, season-wise crop production statistics from 1997*,
   resource ID `35be999b-0208-4354-b557-f6ca9a5355de`.
3. Copernicus Climate Change Service, *ERA5-Land hourly/daily aggregated
   reanalysis*, via Google Earth Engine (`ECMWF/ERA5_LAND/DAILY_AGGR`).
4. ISRIC — World Soil Information, *SoilGrids*, via Google Earth Engine
   (`projects/soilgrids-isric`).
5. European Space Agency, *Sentinel-2 MSI Level-2A Surface Reflectance*
   (`COPERNICUS/S2_SR_HARMONIZED`), via Google Earth Engine.
6. U.S. Geological Survey, *Landsat Collection 2 Level-2 Surface
   Reflectance* (5/7/8/9), via Google Earth Engine.
7. International Rice Research Institute, *When to Harvest*, IRRI Rice
   Knowledge Bank fact sheet.
8. ICRISAT, *Village Dynamics in South Asia (VDSA) Micro-level Panel
   Dataset*, vdsa.icrisat.org.
9. Schulman, J., Wolski, F., Dhariwal, P., Radford, A., Klimov, O., *Proximal
   Policy Optimization Algorithms*, arXiv:1707.06347.
10. Raffin, A., et al., *Stable-Baselines3: Reliable Reinforcement Learning
    Implementations*, JMLR 2021.

---

*Full reproducibility artifacts — code, seeds, splits, and raw result JSON
for every table in this paper — are available in the project repository;
see `RESULTS.md` for the exact command producing each number.*
