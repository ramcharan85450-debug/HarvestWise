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
| 4 | Baselines + ablation | Done - multi-seed ablation shows fusion beats single-modality (R2 0.500 vs 0.444 / 0.441) |
| 5 | Static harvest optimizer | Done (`models/heads/static_harvest_optimizer.py`) |
| 6 | RL harvest policy | Trained on real replayed trajectories (`models/heads/rl_harvest_policy/`) |
| 7 | Climate-shock benchmark | Done, but underpowered at 4 shock seasons - re-run after the ERA5 backfill |
| 8 | Validation & stats | Wilcoxon RL-vs-static done. **Real-outcome validation blocked**: no harvest records secured |
| 9 | Serving/demo | Done - backend serves real model output over real data, or 503s; no placeholder path remains |
| 10 | Public release + report | `benchmark_release/` carries real splits and real results; draft paper in `paper/HarvestWise_paper.md` |

## Honest summary of results

**Measured over 5 seeds** (`python -m evaluation.run_model_comparison --seeds 5`),
on 28 real season examples across 7 fields, 4 states and 2 crops:

| Model | Real-holdout MAE (t/ha) | Range over seeds |
|---|---|---|
| Random Forest | 0.584 +/- 0.086 | 0.536 - 0.735 |
| XGBoost | 0.653 +/- 0.091 | 0.530 - 0.739 |
| Naive baseline (predict the mean) | 0.672 +/- 0.010 | 0.664 - 0.690 |
| **HarvestWise multimodal** | **0.681 +/- 0.264** | **0.449 - 1.134** |

**The multimodal model does not beat a naive mean-predictor on average.** It
wins on some seeds (0.449) and loses badly on others (1.134); its variance is
26x the naive baseline's. Earlier single-run results reporting that it "beats
the naive baseline" were seed luck, and are not reproducible. The top-two gap
(0.068) is smaller than the seed-to-seed spread (0.088), so even the Random
Forest / XGBoost ordering is not established at this sample size.

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
