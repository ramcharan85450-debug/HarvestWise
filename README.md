# HarvestWise

Multimodal Spatio-Temporal Deep Learning Framework for Climate-Adaptive Crop
Yield Forecasting and Dynamic Harvest Window Optimization.

## Project layout

```
HarvestWise/
├── ingestion/          Phase 1-2: pull + align satellite/weather/soil data
├── models/              Phase 3, 5-7: encoders, fusion, backbone, heads, RL policy, domain adaptation
├── training/            Phase 3: dataset building + training loop for the forecast model
├── evaluation/           Phase 4, 7-8: baselines, ablation, climate-shock benchmark, stats, explainability
├── backend/              Phase 9: FastAPI serving layer (done - see backend/README.md)
├── frontend/             Phase 9: Streamlit dashboard (done - see frontend/README.md)
├── benchmark_release/    Phase 10: the public, citable Climate-Shock Benchmark package
├── data/                 raw/ (untouched pulls) and processed/ (aligned weekly tables)
└── requirements.txt      root env for ingestion + training (run in Colab for GPU steps)
```

## Status

| Phase | What | Status |
|---|---|---|
| 0 | Setup | Done |
| 1 | Data acquisition | Done - real Sentinel-2 / ERA5 / SoilGrids pulls for 7 fields across 4 states, 2 crops. ERA5 backfill to 2019 in progress |
| 2 | Data pipeline | Done (`ingestion/align_pipeline.py`) |
| 3 | Core model | Trained on real data (`training/train_forecast_model.py`); checkpoints in `backend/checkpoints/` |
| 4 | Baselines + ablation | Done - **multi-seed ablation does NOT show a fusion benefit**: fused R2 -0.069 sits *below* imagery-only 0.027. The earlier 3-seed "fusion beats single-modality (0.500 vs 0.444 / 0.441)" was seed luck and is **retracted** |
| 5 | Static harvest optimizer | Done (`models/heads/static_harvest_optimizer.py`) |
| 6 | RL harvest policy | Trained on real replayed trajectories (`models/heads/rl_harvest_policy/`) |
| 7 | Climate-shock benchmark | Done, but underpowered at 4 shock seasons - re-run after the ERA5 backfill |
| 8 | Validation & stats | Wilcoxon RL-vs-static done. **Real-outcome validation blocked**: no harvest records secured |
| 9 | Serving/demo | Done - backend serves real model output over real data, or 503s; no placeholder path remains |
| 10 | Public release + report | `benchmark_release/` carries real splits and real results; draft paper in `paper/HarvestWise_paper.md` |

## Honest summary of results

This project has **two distinct evaluation tracks**. They use different units
of analysis and different samples, and their numbers must never be mixed:

- **Track A — field-level predictive evaluation.** Unit is a *(field, season)*.
  This is the headline yield-forecast result below, plus the fusion ablation
  and the harvest-timing policy.
- **Track B — district-level analytical experiments** (Experiments 2-9). Unit
  is a *(district, year)*; samples run 359-561 rows. These test explanatory
  associations, not predictive accuracy. See "Experiments 1-9" below.

### Track A — headline yield forecast (canonical)

**Measured over 5 seeds** (`python -m evaluation.run_model_comparison --seeds 5`),
on **21 real held-out season examples** across 7 fields, 4 states and 2 crops.
This is the canonical headline sample, matching `RESULTS.md` §2:

| Model | Real-holdout MAE (t/ha) | Range over seeds |
|---|---|---|
| **Naive (predict the mean)** | **0.689 +/- 0.006** | 0.684 - 0.699 |
| Random Forest | 0.726 +/- 0.098 | 0.641 - 0.886 |
| HarvestWise multimodal | 0.727 +/- 0.131 | 0.609 - 0.952 |
| XGBoost | 0.764 +/- 0.181 | 0.526 - 0.997 |

**No model beats predicting the mean.** The top-two gap (0.037) is smaller than
the seed spread (0.052), so no ranking among the three fitted models is
established either.

> **On the n=21 vs n=28 sample.** Earlier versions of this README quoted a
> **28**-example evaluation (naive 0.672, HarvestWise 0.681 +/- 0.264, range
> 0.449-1.134). That sample is **superseded, not an alternative result**. The
> series went 43 -> 21 examples when `RESULTS.md` §2a capped satellite
> interpolation at 3 weeks and dropped seasons with longer unobserved gaps
> instead of training on a fabricated flat line; the older samples rested on a
> satellite series that was 56% gap-filled. Both samples reach the same
> conclusion — the multimodal model does not beat naive — but **n=21 is the
> canonical figure** and the n=28 numbers should not be quoted going forward.

**The fusion ablation does not hold up either.** Re-run over 5 seeds
(`python -m evaluation.ablation.run_ablation --seeds 5`):

| Ablation | val R2 (5 seeds) | Range |
|---|---|---|
| imagery-only | 0.027 | -0.554 to 0.606 |
| fused | -0.069 | -0.537 to 0.248 |
| weather-only | -0.119 | -0.271 to 0.073 |

Fused is *worse* than imagery-only, and all three sit at or below R2 = 0, i.e.
worse than predicting the mean. An earlier 3-seed run reporting fused 0.500 vs
0.444 / 0.441 was seed luck and is retracted. Multimodal fusion is not
currently demonstrated to help on this data.

One supporting result does hold up:

- The RL harvest policy **matches** the full-foresight static optimizer while
  seeing only 4 weeks ahead: mean difference -0.0000 t/ha, p = 0.317,
  d = -0.189, not significant. "Matches an oracle under a tighter information
  constraint" is the defensible claim; "outperforms" is not.

## Experiments 1-9 — scientific status

Track B. District-level explanatory analyses on 359-561 district-years across
Andhra Pradesh, Telangana and Tamil Nadu, 2000-2012. Full reports in
`experiments/`; a consolidated reading is in
`experiments/EXPERIMENTS_1_TO_9_SYNTHESIS.md`. **These test statistical
association, not predictive accuracy** — none of them improves the Track A
result above.

| # | Result | Status |
|---|---|---|
| **1** | Unseen-district generalization. The field-level headline stays negative. On the district grouped split, **weather+satellite reaches MAE 0.5255 (R2 0.205) against a 0.5990 baseline** — a modest, genuine improvement. The **full multimodal model is worse** (0.5627), so fusion is not what produces it. | Modest positive, narrow |
| **2** | Tamil Nadu domain-shift diagnostic. Substantial regional shift, roughly 5x the within-AP/TG temporal drift. The contrast is **confounded** (cross-region *and* temporal), so no mechanism can be attributed. | Diagnostic |
| **3** | Pure geographic isolation — same years, season and sensor era, only the state differs. **The baseline (MAE 1.0523) beat every model**; all R2 below zero. No multimodal generalization superiority is established. | Clean design, negative |
| **4** | Geographic covariates account for **~31.6%** of the 0.8250 t/ha regional yield gap. `n_rice_seasons` was caught by a pre-stated screen as a **region proxy** and excluded. Read as a partial explanatory association, **not a causal decomposition**. | Partial |
| **5** | District irrigation and the residual gap. Irrigation coefficient **-0.0057** — the wrong direction. | Little / no support |
| **6** | Within-district irrigation, two periods. **beta = +0.0121, CI [-0.0536, +0.0778]** on 27 first-differences. The interval contains both zero and the meaningful-effect anchor. | **Inconclusive, underpowered** |
| **7** | Fertilizer intensity. Data was found for 31 of 32 districts, but AP publishes "Distribution" and TN "Consumption", and that definitional mismatch is **confounded with the regional contrast** being measured. | **Not feasible** |
| **8** | Intra-seasonal rainfall structure beyond the seasonal total. **Wild cluster bootstrap p = 0.3418**; incremental within-R2 0.0273 below the 0.031 threshold. Measurement validation found **important ERA5-IMD disagreement, concentrated in Tamil Nadu** (within-district r 0.446 vs 0.770 / 0.751). | **Inconclusive** + confirmed measurement limitation |
| **9** | Within-season temperature structure. Pre-registered primary association **beta = +0.17195 t/ha per SD, bootstrap p = 0.0211, CI [+0.04223, +0.32329]**. | **SUPPORTED UNDER THE PRE-REGISTERED PRIMARY SPECIFICATION, BUT SPECIFICATION-FRAGILE** |

**Experiment 9 needs its full label every time it is cited.** The
pre-registered criterion was met, and the association is fragile: removing year
fixed effects **reverses the sign** (-0.1263, p = 0.0034), region-specific
trends do the same (-0.0906, p = 0.0159), the **balanced panel essentially
eliminates it** (+0.0059, p = 0.9408), and neither Andhra Pradesh + Telangana
nor Tamil Nadu is statistically supported on its own. It is **not causal**, and
it is **not evidence that temperature structure improves HarvestWise's
predictive performance** — Experiment 9 measured an association and never
evaluated prediction.

## Scientific status summary

| Area | Status |
|---|---|
| **Prediction** | **No robust evidence that HarvestWise beats the naive mean** on the headline real-world held-out sample (0.727 vs 0.689, n=21). |
| **Fusion** | **No robust evidence of multimodal fusion superiority.** Fused R2 -0.069 sits below imagery-only 0.027; the earlier apparent advantage is **retracted**. |
| **Generalization** | Unseen-district performance remains challenging, and geography / domain shift matters: once era is held fixed, the baseline still beat every model (Experiment 3). |
| **Mechanisms** | Geographic covariates explain part of the regional difference (~31.6%); **irrigation is not supported** as the residual explanation; **fertilizer was infeasible**; **rainfall structure is inconclusive**; **temperature structure is supported only under the pre-registered primary specification and is specification-fragile**. |
| **Causality** | **No causal claim is established by Experiments 1-9.** Every design is observational; none used an identification strategy. |

Terminology used deliberately throughout: *predictive performance*,
*statistical association*, *measurement agreement* and *causal effect* are four
different things and are never used interchangeably.

Three limitations are load-bearing and should be stated in any write-up:

- **No real-outcome validation exists.** `data/raw/harvest_outcomes/` is empty,
  so the "recommended vs. actual harvest" claim has no evidence behind it.
- **The model's climate response is very weak** (-1.1% predicted yield at
  +4 C and -40% rainfall), which is hard to reconcile with a
  climate-adaptive framing.
- **Synthetic pretraining supplies ~91% of the gradient signal and teaches a
  relationship that contradicts the real labels.** Giving the generator a
  correct weather-to-yield coupling made real accuracy monotonically *worse*
  (0.532 -> 0.931 -> 1.391 as the model learned it better), with
  corr(pred, actual) = +0.078. See `build_synthetic_dataset`'s docstring in
  `training/dataset.py`. The root cause is label granularity: the labels are
  national/state annual averages while the inputs describe specific fields.
  **Field-level yield labels are the highest-value missing data item.**

## What's left before this produces real numbers

1. **Run the ingestion scripts** against your Earth Engine / CDS accounts:
   ```
   python -m ingestion.satellite_fetch
   python -m ingestion.weather_fetch
   python -m ingestion.soil_fetch
   python -m ingestion.align_pipeline
   ```
2. **Add real yield labels**: `data/raw/yield_labels/{field_id}_yield_labels.csv` (season_start_date, final_yield_t_ha) - from USDA NASS / your state's agri portal.
3. **Add real harvest-outcome records** (highest-priority data item): `data/raw/harvest_outcomes/{field_id}_outcomes.csv` - see `evaluation/outcome_validation/backtest_real_outcomes.py` docstring for the exact columns needed.
4. **Train in Colab** (GPU): `training/train_forecast_model.py`, then `models/heads/rl_harvest_policy/train_rl.py`.
5. **Run evaluation**: baselines, ablation, `evaluation/climate_shock_benchmark/run_benchmark.py`, `evaluation/statistical_tests/paired_significance.py`.
6. **Drop trained checkpoints into `backend/checkpoints/`** - the API switches from placeholder to real inference automatically (see `backend/app/models_registry/model_loader.py`).
7. **Publish `benchmark_release/`** to a public GitHub repo, fill in `leaderboard.md` with real numbers, fix `CITATION.cff`'s author fields.
8. **Write the report/paper** using the novelty framing already established: RL harvest-window policy + climate-shock benchmark + real-outcome validation, chained together - not the fusion architecture alone.

## Every model file that still needs real training data has a `TODO(model swap)` or `TODO(real data)` comment marking exactly where to plug it in - grep for those to find every remaining placeholder in one pass:

```
grep -rn "TODO(model swap)\|TODO(real data)" --include=*.py .
```
