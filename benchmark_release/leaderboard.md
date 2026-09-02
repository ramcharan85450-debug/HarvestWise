# Leaderboard

Results on the HarvestWise Climate-Shock Benchmark v1.0 — rice and wheat across
Tamil Nadu, Punjab, West Bengal and Andhra Pradesh, India.

Every number below is copied from
`evaluation/climate_shock_benchmark/results.json`, the output of
`python -m evaluation.climate_shock_benchmark.run_climate_shock`. Do not
hand-edit this table; regenerate it.

## Setup

Models are fit on **20 real NORMAL field-seasons** (plus synthetic
pretraining, identically for every model) and scored on **4 real CLIMATE-SHOCK
field-seasons** they never saw. Shock membership is decided by ERA5
growing-season anomalies per field, not by hand — see
`splits/field_year_labels.json`.

Held-out shock seasons:

| Field | Year | Label | Actual yield (t/ha) |
|---|---|---|---|
| F004 (Ajnala, Punjab — rice) | 2025 | wet_extreme | 4.193 |
| F005 (Burdwan, West Bengal — rice) | 2022 | drought | 2.995 |
| F005 (Burdwan, West Bengal — rice) | 2024 | wet_extreme | 3.057 |
| F006 (Amalapuram, Andhra Pradesh — rice) | 2025 | drought | 3.393 |

## Results

MAE in t/ha on the shock seasons. **Lower is better.**

Mean ± sd over 5 seeds.

| Model | MAE on shock seasons (t/ha) | Range |
|---|---|---|
| Random Forest (baseline) | **0.189 ± 0.060** | 0.143 – 0.294 |
| XGBoost (baseline) | 0.222 ± 0.044 | 0.173 – 0.289 |
| HarvestWise multimodal | 0.366 ± 0.146 | 0.221 – 0.566 |
| Naive baseline (predict the fit-set mean) | 0.460 ± 0.011 | 0.450 – 0.479 |

The Random Forest / XGBoost ordering is **not** established: the top-two gap
(0.034) is smaller than the pooled seed-to-seed spread (0.052).

**Context from the wider holdout.** On the full 28-season real holdout (not
just shock seasons), also over 5 seeds, the multimodal model scores
0.681 ± 0.264 MAE against a naive mean-predictor's 0.672 ± 0.010: there it
does **not** beat predicting the mean, and its seed-to-seed range
(0.449–1.134) is wider than every gap in this table. Report both settings —
the model's advantage on shock seasons does not generalise to the full set.

## Reading these results honestly

**The multimodal model does not win this benchmark**, though on shock seasons
it does beat a naive mean-predictor (0.366 vs 0.460) — unlike on the full
28-season holdout, where it does not. Random Forest remains roughly 2x more
accurate. This is reported as measured.

A correctness fix landed between two runs of this table and is worth recording
because it did *not* move the numbers: the spatio-temporal backbone was a
bidirectional Transformer encoder with no causal mask, so each week's forecast
attended to later weeks in the same season — data unavailable at that week's
real decision time. Masking it made the model exactly causal (verified: 0.0
change at week 0 when only week 19's inputs are corrupted) and raised the
weekly curve's variation from 0.9% to 5.7% of mean yield, but shock-season MAE
moved only 0.429 → 0.447, i.e. within noise at n=4. The leaked information was
barely being used; the model's weakness here is sample size, not the leak.

Two things bound how much can be concluded either way:

1. **n = 4 shock seasons.** The ordering is indicative, not statistically
   powered. No significance test on four points would mean anything, so none
   is claimed.
2. **Label granularity.** Punjab, West Bengal and Andhra Pradesh yield labels
   are state-level annual figures, and 2019–2021 state-specific labels were
   unavailable, so those seasons carry a borrowed label. See
   `data/raw/yield_labels/README.md`.

Widening the ingested ERA5 record (in progress, back to 2019) increases the
number of qualifying shock seasons and gives each field a climatology baseline
estimated from years outside its own test set. That is the change that would
make this table publication-strength.

_Last updated: from `results.json` covering ERA5 2022–2025. Regenerate after
the 2019–2021 backfill completes._
