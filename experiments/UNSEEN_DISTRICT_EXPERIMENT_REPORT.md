# Unseen-district generalization experiment — report

**The question**: can a model trained on some agricultural districts predict rice yield in districts it has never seen? Not "can it predict a held-out year in a district it already memorized" — this project's own Experiment 1 found a soil-only control statistically matching a full multimodal model at field scale, i.e. the model was reading location identity rather than agronomy. This experiment is built to expose that failure mode if it is still present, not to hide it.

**Leakage audit: PASS (9 of 9).** No model was trained until the audit passed — the runner refuses to proceed otherwise (this actually fired once during development, on a bug in the audit itself, and training was blocked until it was fixed). Full evidence in [`UNSEEN_DISTRICT_LEAKAGE_AUDIT.md`](UNSEEN_DISTRICT_LEAKAGE_AUDIT.md).

## Dataset

| | |
|---|---|
| Collected rows in the aligned CSV | 868 |
| **Used (fully aligned: real weather AND satellite AND soil)** | **561** |
| Excluded | 307 |
| Target column (verified from the CSV, not assumed) | `final_yield_t_ha` |
| Missing values in the 561 used rows, across all 12 features | **0** |
| Districts | 58 |
| Examples by state | Andhra Pradesh 260 (46.3%), Telangana 227 (40.5%), Tamil Nadu 74 (13.2%) |

**Exclusion reasons**: all 307 excluded rows lack both weather and satellite coverage for their season window (the 1997–1999 / 2013–2014 environmental gap documented in `ENVIRONMENTAL_COVERAGE_RECOVERY_REPORT.md`). Soil is available for all 868, but **every configuration is scored on the same 561 rows** — letting the soil-only control quietly use all 868 would have made it incomparable to the others.

**No imputation was performed anywhere**, because none was needed: the used subset has zero missing feature values. Rows lacking a modality were excluded up front and counted, never filled in.

### Features (12, in three explicitly-named groups)

- **Weather (4)**: `weather_temp_c_mean`, `weather_precip_mm_sum`, `weather_humidity_pct_mean`, `weather_wind_speed_ms_mean`
- **Satellite (3)**: `satellite_ndvi_mean`, `satellite_evi_mean`, `satellite_ndwi_mean`
- **Soil (5)**: `soil_phh2o`, `soil_soc`, `soil_clay`, `soil_sand`, `soil_nitrogen`

Everything else in the CSV is excluded with a stated reason (see `training/district_dataset.py`'s module docstring). Two exclusions deserve highlighting because they are not obvious:

- **`year` and `season` are deliberately excluded.** In this dataset every Tamil Nadu example is `Whole Year` in 2019 or 2024, while every Andhra Pradesh and Telangana example is Kharif/Rabi in 1999–2012. Either column alone identifies the region with perfect accuracy, which would defeat the entire unseen-district design. They are kept as metadata and never enter the feature matrix.
- **Data-quality metadata is excluded** (`satellite_scenes_observed`, `satellite_date_range_coverage`, `weather_days_observed/expected`). These describe how the data was *fetched*, not how the crop grew — and they separate regions almost perfectly (every Tamil Nadu row has coverage 0.504; every Andhra Pradesh row has 1.0).

## Split design

Districts — not rows — are split, grouped on `state | canonical_district_name`. The composite key is used because district names can repeat across Indian states (verified: 0 currently do in this dataset, but the key stays correct if a state is added).

Splits are **stratified by state**, which is a deliberate design choice, not a default: districts are wildly unequal in size (Andhra Pradesh and Telangana districts carry ~25–26 examples each, Tamil Nadu districts ~2), so an unstratified draw would produce test folds that are sometimes nearly all Tamil Nadu (a few dozen rows) and sometimes nearly all Andhra Pradesh (several hundred). Stratifying keeps every fold comparable and guarantees all three regions appear in every split.

| Split | Districts | Examples | By state |
|---|---|---|---|
| Train | 34 | 325 | AP 156, Telangana 127, TN 42 |
| Validation | 12 | 118 | AP 52, Telangana 50, TN 16 |
| Test | 12 | 118 | AP 52, Telangana 50, TN 16 |

*(Seed 42; the other seeds have the same district counts. Example counts vary slightly between seeds — seed 46's test fold has 95 rows — because individual districts hold different numbers of examples, e.g. Hyderabad contributes only 2.)*

Test districts, seed 42 (district names are geographic research metadata already present in the official published dataset): Kurnool and Prakasam (AP); Mahbubnagar and Medak (Telangana); Chengalputtu, Dharmapuri, Kallakurichi, Thanjavur, Thiruvallur, Tirunelveli Kattabo, Tirupathur and Tiruppur (TN). Every seed's full assignment is stored in `unseen_district_results.json`.

**5 repeated grouped splits** (seeds 42–46). Within a seed, every configuration receives the identical split, so configurations differ only in which feature columns they see.

## Model

A small MLP, sized to the data rather than to ambition: `n_features → 32 → 16 → 1`, ReLU, dropout 0.2, ~950 parameters at the widest (12-feature) configuration — fewer parameters than the 325 training rows would support overfitting against, chosen so results reflect signal in the features rather than network capacity. MSE loss, Adam (lr 1e-3, weight decay 1e-4), batch size 32, up to 300 epochs with early stopping (patience 30) **on validation loss only**. Identical hyperparameters for every configuration and seed — no per-configuration tuning, and nothing selected using test data.

## Results

Mean ± standard deviation over the 5 repeated grouped splits. Every seed's test fold is reported, not just the best.

| Configuration | MAE (t/ha) ↓ | RMSE (t/ha) ↓ | R² ↑ |
|---|---|---|---|
| Baseline (train mean) | 0.599 ± 0.088 | 0.746 ± 0.121 | −0.088 ± 0.173 |
| A — Weather only | 0.562 ± 0.124 | 0.706 ± 0.148 | 0.028 ± 0.238 |
| B — Satellite only | 0.593 ± 0.104 | 0.718 ± 0.122 | −0.015 ± 0.223 |
| **C — Weather + Satellite** | **0.525 ± 0.081** | **0.636 ± 0.083** | **0.205 ± 0.116** |
| D — Soil only (control) | 0.756 ± 0.250 | 0.980 ± 0.363 | −0.863 ± 0.849 |
| E — Full multimodal (W+S+Soil) | 0.563 ± 0.108 | 0.699 ± 0.104 | 0.040 ± 0.154 |

No p-values are reported: 5 repeated grouped splits over 58 districts do not satisfy the independence assumptions a significance test would need, and the standard deviations above carry the relevant uncertainty honestly.

### Per-state performance (test-fold predictions pooled across all 5 seeds)

| Configuration | Andhra Pradesh (n=260) | Telangana (n=227) | Tamil Nadu (n=78) |
|---|---|---|---|
| Baseline | MAE 0.636, R² −0.076 | MAE 0.448, R² −0.377 | MAE 0.900, R² −1.594 |
| **C — Weather + Satellite** | **MAE 0.558, R² 0.290** | **MAE 0.379, R² −0.007** | **MAE 0.821, R² −1.218** |
| D — Soil only | MAE 0.930, R² −1.539 | MAE 0.468, R² −0.610 | MAE 1.002, R² −2.933 |
| E — Full multimodal | MAE 0.602, R² 0.123 | MAE 0.402, R² −0.210 | MAE 0.870, R² −1.637 |

## Interpretation

**1. Weather + Satellite is the best configuration, and beats the baseline — modestly.** MAE 0.525 vs 0.599 (a 12% reduction), R² 0.205 vs −0.088. It is also the *most stable* configuration on all three metrics (lowest standard deviation), and it beats the baseline on MAE in all three states individually. This is a real positive result, but it is a modest one and should be described that way: an R² of 0.205 means roughly a fifth of the variance in yield across unseen districts is explained, and four fifths is not.

**2. Season-varying environmental features do contribute — and the two modalities are complementary.** Weather alone (MAE 0.562, R² 0.028) and satellite alone (MAE 0.593, R² −0.015) are each barely distinguishable from the baseline. Their *combination* is clearly better than either (MAE 0.525, R² 0.205). Neither modality alone carries the signal; the combination does. Per the interpretation rule this is evidence that season-varying environmental features contribute useful information for unseen districts.

**3. Soil-only is the worst configuration by a wide margin, and this is the most important result here.** MAE 0.756 and R² −0.863 — substantially *worse than predicting the training mean*, and by far the most unstable (MAE ±0.250, R² ±0.849). The same pattern holds in every state separately.

This is the direct opposite of what Experiment 1 found at field scale, and the reason is instructive rather than contradictory: **soil is constant per district**, so under a split where test districts are never seen in training, the model has no memorized soil→yield mapping to fall back on, and static soil values actively mislead it. Experiment 1's soil-only control succeeded precisely *because* its split let the same fields appear on both sides. **The unseen-district design does exactly what it was built to do: it destroys the location shortcut.** Confirming that a shortcut which previously scored well now collapses is positive evidence that this evaluation is measuring generalization rather than memorization.

**4. Full multimodal does NOT improve over Weather + Satellite — it degrades it.** MAE 0.563 vs 0.525, R² 0.040 vs 0.205, and worse in every state individually (AP 0.123 vs 0.290; Telangana −0.210 vs −0.007; TN −1.637 vs −1.218). Adding soil to a working weather+satellite model consistently hurts unseen-district generalization, presumably because the network partially latches onto a district-constant signal that does not transfer. **This is reported as a negative result and must not be presented as a multimodal win.** The best model in this experiment is the one *without* soil.

**5. Satellite alone performs poorly — reported honestly.** R² −0.015 means satellite-only is indistinguishable from predicting the mean. A season-mean NDVI/EVI/NDWI triplet aggregated over an entire district is evidently too coarse a summary to carry yield signal on its own, however useful it is alongside weather.

**6. Tamil Nadu is a genuine failure case.** Every configuration, including the baseline, has a deeply negative R² there (−1.2 to −2.9). The model does not capture Tamil Nadu's yield variance at all. Likely contributors, none verified here: only 74 examples across 38 districts (≈2 each, so almost no within-district signal), a different era (2019/2024 vs 1999–2012), a different season definition (Whole Year vs Kharif/Rabi), and only ~50.4% environmental window coverage for every Tamil Nadu row (documented in the recovery report). The headline aggregate is carried by Andhra Pradesh and Telangana; describing this as validated "Southern India" generalization would overstate it.

## Figures

All in `experiments/figures/unseen_district/`:

1. `unseen_district_mae.png` — model comparison, MAE
2. `unseen_district_rmse.png` — model comparison, RMSE
3. `unseen_district_r2.png` — model comparison, R²
4. `unseen_district_actual_vs_predicted.png` — Weather + Satellite, actual vs predicted

**Method for figure 4, stated explicitly**: test-fold predictions **pooled across all 5 repeated grouped splits** (n=565), not a cherry-picked best split. Because these are 5 independent repeated grouped splits rather than a single k-fold partition, a district can appear in more than one seed's test fold — so this is "pooled across repeated splits", not strict out-of-fold, and is labeled as such on the figure. The plot shows clear regression to the mean: predictions compress into roughly 2.4–3.6 t/ha while actuals span 1.2–5.3, which is what an R² of 0.205 looks like.

## Reproducibility

`experiments/unseen_district_results.json` stores the seeds, every seed's full district-level split assignment, the model and training configuration, per-seed and aggregated metrics, per-state pooled metrics, dataset sizes and exclusion reasons, figure paths, the audit result, and the torch version. Re-running `python -m experiments.run_unseen_district_experiment` reproduced identical metrics to three decimal places.

## Final answers

**1. Is unseen-district evaluation scientifically valid here? YES.** All 9 leakage checks pass with concrete evidence; districts are disjoint across train/val/test in all 5 seeds; scalers and the baseline mean are fit on training data only; the training function cannot structurally see test data; and identifiers, provenance strings, year and season are all excluded from features. The collapse of the soil-only control is independent behavioural confirmation that the split removes the memorization route.

**2. Does Weather + Satellite beat the baseline? YES, modestly.** MAE 0.525 vs 0.599 (−12%), R² 0.205 vs −0.088, with lower variance than any other configuration and a consistent MAE advantage in all three states.

**3. Does Weather + Satellite beat Soil Only? YES, decisively.** MAE 0.525 vs 0.756; R² 0.205 vs −0.863. The gap is far larger than either configuration's spread across seeds.

**4. Does Full Multimodal genuinely improve over Weather + Satellite? NO.** It is worse on every metric overall and in every state individually. Adding soil degrades unseen-district generalization.

**5. Is there evidence of soil/location shortcut behaviour? YES — and this experiment removes it rather than benefiting from it.** Static soil information is worse than useless for unseen districts (worse than the training mean), and adding it to a working model actively hurts. Combined with Experiment 1's finding that the same feature type *succeeded* under a split where fields recurred, the evidence is that soil functions as a location fingerprint in this project's data, not as agronomic signal.

**6. Is the dataset sufficient for a conference-paper experiment? QUALIFIED YES — for this specific claim, not for a general one.** 561 examples across 58 districts and 3 regions, with a passing leakage audit, repeated grouped splits and a mandatory control that behaves exactly as a shortcut-detector should, is enough to support a careful negative-plus-modest-positive result: *season-varying environmental features generalize to unseen districts where static soil features do not, and the combination is better than either modality alone*. It is **not** sufficient to claim strong yield-forecasting accuracy (R² 0.205 is weak), nor validated "Southern India" generalization (Tamil Nadu fails outright and supplies 13% of examples), nor any multimodal-fusion improvement (full multimodal is worse than weather+satellite). Those limits must appear in the paper alongside the result.

**Recommended next step**: the largest identified constraint is data, not method — closing the 1997–1999 and 2013–2014 environmental gap would raise the usable set from 561 toward 868 and add temporal depth to Andhra Pradesh and Telangana, and fetching the missing half of Tamil Nadu's Whole-Year windows (January–June of each following year) would address the region that currently fails. Both are mechanical, already-scoped fetches described in `ENVIRONMENTAL_COVERAGE_RECOVERY_REPORT.md` §9.
