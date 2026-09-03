# Experiment 1: Baseline Data-Source Comparison — Final Report

Reproduce with: `python -m experiments.run_experiment1 --seeds 5 --epochs 30`

---

## 1. Existing pipeline inspection

- **Target**: `training/dataset.py`'s `SeasonExample.final_yield` (float, t/ha), one scalar per real season. The model predicts it via a per-week (low, median, high) quantile head; the point forecast used everywhere in this project is the **last week's median quantile** (`quantiles[:, -1, 1]`, see `train_forecast_model.py::predict_final_yield`).
- **Features currently used** (`training/dataset.py`, `SOIL_COLS`/`WEATHER_COLS`, confirmed by reading the code):
  - `vision_x` (T×4): `ndvi, ndvi_delta, evi, ndwi`
  - `weather_x` (T×4): `temp_c, precip_mm, humidity_pct, wind_speed_ms`
  - `soil_x` (5): `phh2o, soc, clay, sand, nitrogen`
  - `growth_stage` (T): calendar-derived, not a raw data source — held fixed (never zeroed) in every experiment below, since it is architectural conditioning, not one of the data sources being compared.
- **Satellite-derived**: all 4 `vision_x` channels (`ndvi_delta` is a derived diff, not separately fetched).
- **Weather-derived**: all 4 `weather_x` channels (ERA5-Land daily aggregates).
- **Soil-derived**: all 5 `soil_x` channels (ISRIC SoilGrids). Confirmed by direct inspection this session: **soil is a static constant per field** — every field has exactly one distinct soil vector across all its seasons (`build_dataset_from_processed()` output checked directly, not assumed).
- **Forecast data**: **not available**. `ingestion/weather_fetch.py` and `district_weather_pull.py` pull ERA5-Land, which is historical reanalysis, not a forward-looking forecast product. No configuration in this experiment claims to use forecast data.
- **Existing train/val/test split**: `random_split` (PyTorch), non-chronological, used in `evaluation/ablation/run_ablation.py` and `evaluation/run_model_comparison.py`. `run_model_comparison.py` additionally trains on 100% synthetic data and evaluates on 100% of the real examples as a pure holdout — not usable for this experiment, which is required to use only real data for training.
- **Temporal leakage risk**: within-season leakage was already fixed by causal attention masking in `SpatioTemporalBackbone` (`RESULTS.md` §7) — not a concern here. The concern relevant to this experiment is different: the existing *random* train/val split can place a field's *later* season in train and an *earlier* season of the *same field* in test. This is not future-information leakage in the strict sense (each season's satellite/weather window is self-contained), but combined with the static soil vector, it lets a model recover a field's label via field-identity rather than genuine within-field seasonal variation — confirmed as a real, active mechanism by this experiment (§8 below), not just a theoretical risk.
- **Metrics already implemented**: MAE (`evaluation/run_model_comparison.py`, `evaluation/label_granularity/`), R² (`evaluation/ablation/run_ablation.py`, `evaluation/baselines/*.py`), Wilcoxon signed-rank + Cohen's d (`evaluation/statistical_tests/paired_significance.py`, used only for the RL-vs-static comparison). **RMSE was not implemented anywhere before this experiment** — confirmed by grep; added here (`sklearn.metrics.mean_squared_error(...) ** 0.5`), a standard metric requiring no architectural change.
- **Existing checkpoints reusable?** **No.** `backend/checkpoints/fusion_backbone.pt` was trained on all 21 real examples together, with no modality masking, using a random (non-chronological) split. Reusing it for any single-modality configuration below would be invalid — a model must be trained *with* a modality zeroed out for a zero-input evaluation of that modality to be a fair test, matching the existing convention in `evaluation/ablation/run_ablation.py`. Each configuration here is trained from scratch; `backend/checkpoints/` is untouched by this experiment.

## 2. Dataset and target

`training.dataset.build_dataset_from_processed()`, default (mixed) label tier — the same 21 real season examples used throughout `RESULTS.md`. No synthetic data of any kind is generated or used. Target: `final_yield_t_ha`.

## 3. Feature groups discovered

| Group | Columns | Source |
|---|---|---|
| Satellite | `ndvi, ndvi_delta, evi, ndwi` | Sentinel-2, real |
| Weather | `temp_c, precip_mm, humidity_pct, wind_speed_ms` | ERA5-Land, real |
| Soil | `phh2o, soc, clay, sand, nitrogen` | ISRIC SoilGrids, real, **static per field** |
| (Not a source) | `growth_stage` | Calendar-derived, held fixed in every configuration |
| (Not available) | forecast weather | Does not exist in this project |

## 4. Experiment configurations

Each configuration trains the **same, unmodified** `ForecastModel` architecture; the only difference is which inputs are zeroed (`evaluation/ablation/run_ablation.py::zero_modality`, extended this session to support masking soil in addition to the existing vision/weather masking — see that file's docstring for the one-line change).

| Experiment | Data sources included | Zeroed |
|---|---|---|
| A — Weather only | weather | vision, soil |
| B — Satellite only | satellite | weather, soil |
| C — Weather + Satellite | weather, satellite | soil |
| D — Full multi-source | weather, satellite, soil | (none) |
| E — Soil only (control) | soil | vision, weather |

No configuration includes forecast data (none exists). All five configurations are real; none was skipped for insufficient data. **E was added specifically as a control** after D's result raised the question in §8: since soil is a static per-field constant (zero season-varying signal), a model given *only* soil cannot possibly forecast a season-specific outcome — it can only ever emit a per-field constant. Measuring how close that control gets to D's score is a direct, quantitative test of how much of D's apparent performance soil-driven field identity explains on its own.

## 5. Train/validation/test split strategy

**Chronological, global, contiguous** — computed by sorting all 21 real examples by `season_start_date` ascending and cutting into three blocks:

| Split | n | Date range |
|---|---|---|
| Train | 13 | 2019-06-16 → 2023-08-06 |
| Val | 3 | 2023-08-06 → 2024-06-16 |
| Test | 5 | 2025-06-15 → 2025-08-03 |

Every test example's date is later than every train example's date — a genuine temporal holdout, chosen specifically because the task instructions prefer one for agricultural seasons. **Documented limitation**: this is a *global*, not per-field, split. Two fields (F005, F007) have only one real season each, so a per-field chronological holdout is impossible for them; F005 and F007 appear only in train, never in val or test. The split boundary also falls on a date (2023-08-06) shared by two different fields (F002 in train, F003 in val) — not a leakage issue (different fields, independent inputs) but noted for exactness.

Same split, same 5 seeds (0-4), same 30 epochs, same optimizer (AdamW, lr=1e-3), same batch size (8) used identically across all four experiments. **One documented training-procedure simplification**: unlike the production training script, this experiment does not do validation-based best-epoch checkpoint selection — it trains for a fixed 30 epochs and evaluates the final model. This was a deliberate choice, not an oversight: the validation set here has only 3 examples, and selecting a checkpoint on 3 points would introduce its own unstable, hard-to-interpret noise on top of an already-small experiment.

## 6. Actual results

Mean ± sd over 5 seeds (0-4), evaluated on the same fixed 5-example test set:

**Naive baseline** (predict the training-set mean, 3.467 t/ha, for every test example): MAE 0.545, RMSE 0.595, R² −0.224.

| Experiment | MAE | RMSE | R² |
|---|---|---|---|
| A — Weather only | 0.186 ± 0.126 (range 0.082-0.399) | 0.221 ± 0.154 | 0.765 ± 0.329 |
| B — Satellite only | 0.562 ± 0.077 (range 0.497-0.680) | 0.683 ± 0.128 | −0.659 ± 0.613 |
| C — Weather + Satellite | 0.207 ± 0.098 (range 0.142-0.379) | 0.257 ± 0.111 | 0.738 ± 0.244 |
| D — Full multi-source | 0.085 ± 0.041 (range 0.055-0.152) | 0.105 ± 0.041 | 0.957 ± 0.033 |
| **E — Soil only (control)** | **0.093 ± 0.046** (range 0.043-0.155) | 0.119 ± 0.052 | 0.943 ± 0.048 |

Samples: **13 train / 3 val / 5 test**, identical across all five experiments.

**E is the result that settles §8's question.** A model given *only* a static, per-field constant — no weather, no satellite, nothing that varies by season — scores MAE 0.093, statistically indistinguishable from D's 0.085 (both well inside the other's seed-to-seed spread). Weather and satellite, added on top of soil, buy essentially nothing beyond noise. This is no longer an inference from inspecting individual predictions (as in the first version of this report); it is a direct, controlled measurement.

## 7. Results table

| Experiment | Data Sources | MAE | RMSE | R² |
|---|---|---|---|---|
| Naive | (none) | 0.545 | 0.595 | −0.224 |
| A | Weather | 0.186 | 0.221 | 0.765 |
| B | Satellite | 0.562 | 0.683 | −0.659 |
| C | Weather + Satellite | 0.207 | 0.257 | 0.738 |
| D | Weather + Satellite + Soil | **0.085** | **0.105** | **0.957** |
| E | Soil only (control) | 0.093 | 0.119 | 0.943 |

## 8. Best-performing configuration — and why the obvious headline is wrong

**D (full multi-source) has the lowest MAE.** Reporting this alone as "multi-source fusion improves performance" would repeat exactly the kind of overclaim this project has already retracted twice before (`RESULTS.md` §2, §3). Investigated before writing this section, per the task's explicit instruction:

Inspecting D's actual seed-0 test predictions against the real train-set labels for the same fields:

| Field | Test actual | D's prediction | Train-set values already seen for this field |
|---|---|---|---|
| F004 | 4.193 | 4.313 | 4.366, 4.366, 4.366, 4.34, **4.193** (repeated) |
| F006 | 3.393 | 3.251 | **3.393**, **3.393** (repeated exactly) |
| F001 | 2.825 | 2.848 | 2.735 |
| F002 | 2.825 | 2.793 | 2.607, 2.735, 2.78 |
| F003 | 2.825 | 2.832 | 2.735, 2.78 |

Two of the five test targets (F004, F006) are values that **already appear, exactly, multiple times in the training set for that same field.** The other three (F001/F002/F003) share the same national yield series, which rises in a smooth, nearly-linear year-over-year sequence (2.735 → 2.78 → 2.825) — trivially extrapolable without modeling any real weather-to-yield or vegetation-to-yield relationship.

This matches, and is independently corroborated by, the SHAP feature-attribution finding already on record for this project (`RESULTS.md` §5e): soil — a static per-field constant — dominates feature importance by roughly an order of magnitude over any weather or vegetation feature. **The most defensible reading of D's low MAE is that adding soil gives the model a clean field-identity signal, which lets it recall each field's own repeated or near-linear regional label rather than genuinely fusing weather and satellite signal to forecast a season-specific outcome.** This is consistent with, not contradicted by, C (weather+satellite, no soil) scoring worse than A (weather only) — satellite adds noise without soil to anchor field identity, and weather alone (climatologically distinct per region) already carries a usable, if cruder, region-identifying signal of its own.

**The soil-only control (E) confirms this directly, not just by inference.** A model given *nothing but* the static 5-value soil vector — no weather, no satellite, no season-varying signal of any kind — scores MAE 0.093 ± 0.046, R² 0.943 ± 0.048: statistically indistinguishable from D's MAE 0.085 ± 0.041, R² 0.957 ± 0.033 (each comfortably inside the other's seed spread). Since E cannot possibly be forecasting a season-specific outcome — it has no input that varies within a field across seasons — its near-parity with D means weather and satellite, layered on top of soil, are contributing essentially nothing measurable beyond noise. This also explains why C (weather+satellite, no soil, MAE 0.207) scores *worse* than E (soil alone, MAE 0.093): the two genuinely informative, season-varying data sources are, on their own, less useful for this metric than one static field-identity constant.

**Therefore: this experiment does not demonstrate that multimodal fusion improves yield-forecasting performance in the sense the phrase usually implies** (learning a real, transferable weather/vegetation-to-yield relationship). It demonstrates that adding a field-identifying constant to a smooth, regionally-aggregated label makes the label easier to recall, and the soil-only control shows that constant is doing essentially all of the work D gets credit for. Both are real, measured results; only the first is the one worth citing without this caveat attached.

**B (satellite-only) performing worse than the naive baseline** is a genuine, independently interesting negative result, consistent with `RESULTS.md` §3's earlier finding that vegetation signal alone does not carry usable yield information at this label resolution.

## 9. Data leakage verification

Checked directly against this pipeline's actual code (`experiments/run_experiment1.py::verify_no_leakage()`), not assumed. Full output: `experiments/leakage_verification.json`.

**Normalization is not a fitted scaler — a more precise finding than the question as originally framed.** `training/dataset.py`'s `VISION_NORM`, `WEATHER_NORM`, and `SOIL_NORM` are fixed literal constants (e.g. `WEATHER_NORM = [(25.0, 8.0), (5.0, 8.0), (65.0, 15.0), (2.0, 1.0)]`), applied identically to every example in every split, in every experiment this project has ever run. They are never computed — via `.fit()` or otherwise — from this experiment's training data or any other data. This means the specific failure mode the leakage check is usually written to catch (a scaler's mean/std computed over data that includes the test set) **cannot occur here by construction**, but it is worth being precise rather than declaring victory on the question as asked: there is no "scaler fitted only on the 13 training samples" step in this pipeline at all, in either direction. If a genuinely fitted, data-driven scaler were introduced in the future, it would need to be fit on `train_examples` only and reused (not refit) for `val_examples`/`test_examples` — this codebase does not yet do that, because it does not fit a scaler anywhere.

**A real leakage vector was found — and has now been fixed, not just flagged.** `training/dataset.py`'s soil-imputation step previously pooled *all* examples (train+val+test) to compute a fill-in mean for any field with missing soil, and ran automatically inside `build_dataset_from_processed()` *before* this script's chronological split even happened. Fix applied: `impute_missing_soil()` (renamed from the previous `_impute_missing_soil()`) now takes an explicit `fit_examples` argument, and `build_dataset_from_processed()` takes a new `impute: bool = True` parameter so a split-aware caller can opt out of its internal auto-impute. This script now calls `build_dataset_from_processed(impute=False)`, performs the chronological split, and only then calls `impute_missing_soil(examples, fit_examples=train_examples)` — the fill-in mean, if ever needed, can now only be computed from the 13 training examples; val/test examples can supply a value to be *filled*, never to help *compute* the fill value. Re-ran the full experiment after the fix: **all reported numbers in §6/§7 are byte-identical to before the fix** — expected, since zero of the 21 real examples currently have missing soil, so imputation does not run either way today. The fix changes the code path's correctness for the day a field's soil pull fails, not any number reported here.

**Confirmed no test/validation information reaches training.** `train_one_config()` is called with only `train_ds`; `val_ds`/`test_ds` are never passed to it and never appear in an `optimizer.step()` call. Both are read only inside `predict()`, which is decorated `@torch.no_grad()` and is called strictly after training for that seed has finished. No early-stopping or best-epoch checkpoint selection on val is performed (§5) — every seed trains for the same fixed 30 epochs, so val cannot even indirectly influence which weights are kept. Split disjointness was checked directly by object identity: 0 overlap between train/val, train/test, and val/test.

| Check | Result |
|---|---|
| Scaler fit only on training samples | N/A — no fitted scaler exists in this pipeline; fixed constants used everywhere (see above) |
| Validation data only transformed, never fit on | True by the same construction — nothing is ever fit |
| Test data only transformed, never fit on | True by the same construction |
| Soil-imputation cross-split pooling | **Fixed** — `impute_missing_soil(fit_examples=...)` now restricts the fit pool to train only; currently a no-op either way (0 of 21 examples need imputation) |
| Test/val used during training (backprop or checkpoint selection) | **No** — confirmed structurally (§9 above) |
| Train/val/test sample overlap | **0** (confirmed by object-identity check) |

## 10. Test set documentation

The exact 5 real examples every configuration in this experiment (including the soil-only control) is scored against:

| Field ID | Field name | Crop | Season (year) | Actual yield (t/ha) |
|---|---|---|---|---|
| F004 | Ajnala, Amritsar | rice_punjab | 2025-06-15 | 4.193 |
| F006 | Amalapuram, East Godavari | rice_andhra_pradesh | 2025-07-06 | 3.393 |
| F001 | Sulur | rice | 2025-08-03 | 2.825 |
| F002 | Kinathukadavu | rice | 2025-08-03 | 2.825 |
| F003 | Annur | rice | 2025-08-03 | 2.825 |

All 5 are the chronologically latest real seasons in the dataset (2025), consistent with the chronological split in §5. Full machine-readable version: `experiments/test_set_documentation.json`.

## 11. Statistical validity

Test set size: **n = 5** paired observations per configuration. Per the task's explicit rule: **statistical significance cannot be reliably established with the available sample size.** No paired significance test was run and no p-value is reported. The seed-to-seed spread reported in §6 (5 seeds per configuration) is the only rigor available at this sample size, and it should be read as showing whether a configuration's ranking is stable under re-initialization, not as a hypothesis test against another configuration.

## 12. Figures created

- `experiments/figures/figure1_mae_comparison.png` — MAE by configuration (all 5, including the soil-only control), mean ± sd bars, explicitly captioned "n_test=5 — too small for a stable ranking."
- `experiments/figures/figure2_rmse_comparison.png` — same, for RMSE.
- `experiments/figures/figure3_actual_vs_predicted_best_model.png` — actual vs. predicted scatter for D (seed 0) on all 5 test points, individually annotated, explicitly captioned "ONLY 5 TEST POINTS — not a reliable calibration plot" rather than presented as a clean diagonal-fit result.

## 13. Files created

- `experiments/run_experiment1.py` — the experiment runner (this report's exact source of every number above), now including the soil-only control config, `verify_no_leakage()`, and `document_test_set()`
- `experiments/__init__.py`
- `experiments/baseline_weather_only/results.json`
- `experiments/baseline_satellite_only/results.json`
- `experiments/baseline_weather_satellite/results.json`
- `experiments/full_harvestwise/results.json`
- `experiments/baseline_soil_only/results.json`
- `experiments/naive_baseline.json`
- `experiments/leakage_verification.json` — the machine-readable form of §9
- `experiments/test_set_documentation.json` — the machine-readable form of §10
- `experiments/reproducibility_log.json` — per-experiment record: name, data sources, feature list, dataset version, n_train/val/test, split strategy, seeds, model/training configuration, evaluation metrics, timestamp
- `experiments/figures/figure1_mae_comparison.png`, `figure2_rmse_comparison.png`, `figure3_actual_vs_predicted_best_model.png`
- `experiments/EXPERIMENT_1_REPORT.md` (this file)

## 14. Files modified

- `evaluation/ablation/run_ablation.py` — `zero_modality()` extended to support masking `soil_x` (previously only `vision_x`/`weather_x`), and `AblatedLoader` extended to accept a list of modalities to zero rather than only one. Documented in the file's own comments. No change to model architecture, hyperparameters, or existing callers' behavior (verified: re-ran `python -m evaluation.ablation.run_ablation --epochs 3 --seeds 1` after the change, output unchanged in form).
- `training/dataset.py` — the soil-imputation leakage fix (§9): `_impute_missing_soil()` renamed to public `impute_missing_soil()` and given a `fit_examples` parameter (defaults to `examples` itself, preserving every existing caller's exact prior behavior); `build_dataset_from_processed()` given a new `impute: bool = True` parameter so a split-aware caller can request unimputed examples and impute after splitting. Backward compatible by default — verified directly: `build_dataset_from_processed()` with no arguments still returns 21 examples, and every other caller in the project (`train_forecast_model.py`, `run_model_comparison.py`, `run_ablation.py`, `run_granularity_sweep.py`) calls it with no `impute` argument, so it keeps its original pre-fix behavior unchanged.
- `ingestion/align_pipeline.py`, `ingestion/soil_fetch_ee.py` — one-line docstring references updated from `_impute_missing_soil` to the new public name `impute_missing_soil`. No functional change.

**Not modified**: `training/train_forecast_model.py`, `models/`, `backend/checkpoints/` (production checkpoints untouched), any real yield-label or harvest-outcome file.

## 15. Limitations

- **n=21 total, n=5 test, n=3 val.** Every number above should be read as indicative, not conclusive — explicitly acknowledged rather than dressed up with a misleadingly precise-looking table.
- **F005 and F007 appear only in train**, never in val or test, because each has only one real season — the global chronological split cannot give them a fair per-field holdout.
- **D's apparent win is a field-identity/regional-trend shortcut, confirmed (not just inferred) by the soil-only control (E)** (§8) — this is the single most important limitation of this experiment, and the reason the results table above must not be quoted without §8's caveat in any paper draft.
- **The soil-imputation leakage vector has been fixed** (§9, §14) — no longer a limitation, listed here for the change record: `impute_missing_soil()` is now fit-pool-aware and this script uses `fit_examples=train_examples`.
- **Regional label resolution.** As throughout this project, the target itself is a national or state yield average, not a field-specific measurement (`RESULTS.md` §1) — this experiment inherits that limitation entirely; it was not designed to fix it (that is `RESULTS.md` §5d's job, a separate, already-reported experiment).
- **A single fixed split.** The chronological cut was computed once, not repeated across multiple temporal folds (a rolling-origin cross-validation would need far more real seasons than 21 to be meaningful) — the reported spread reflects only re-initialization (seed) variance, not split variance.
- **No statistical significance testing** was possible or attempted (§11).

## 16. Conference-paper interpretation

This experiment adds a *specific, mechanistic, and now directly confirmed* explanation to a claim `RESULTS.md` already makes more generally (§5e, via SHAP): the project's yield labels are regional averages with very low within-field year-to-year variance, so a model that can identify *which field or region* an example belongs to has a large, easy advantage over one that must learn genuine weather/vegetation causality — and soil, being a static per-field constant, is the cheapest possible way to identify a field. The soil-only control (E) turns this from an inference into a measurement: a model with zero season-varying input scores within noise of the full multi-source model. Framed this way, D's MAE 0.085 is not evidence that HarvestWise's multimodal architecture has learned to forecast yield from climate and canopy signal; it is evidence that the label-granularity problem identified in `RESULTS.md` §5d is severe enough that a model can score very well by *not* solving the intended problem. This strengthens, rather than competes with, this project's central label-granularity thesis (`paper/HarvestWise_paper.md`) — it is a second, independent line of evidence for the same conclusion (finer, field-specific labels are necessary before a multimodal fusion claim can be trusted), obtained by a completely different method (a real, chronological, small-n ablation with an explicit control) than the granularity sweep was. It should be reported in any paper draft as exactly that: corroborating evidence for the resolution thesis, not a fusion win — and the soil-only control is the single figure most worth including if space allows only one from this experiment.
