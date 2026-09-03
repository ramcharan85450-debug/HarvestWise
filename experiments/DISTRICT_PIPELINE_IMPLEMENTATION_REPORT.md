# District-level multimodal pipeline — implementation report

Scope: implement the minimum scientifically correct architecture to support district-level multimodal agricultural forecasting, as an **extension alongside** the existing field-level pipeline, not a replacement of it. **No model was trained.** Real weather, satellite, and soil data were fetched for genuine gaps identified in the prior compatibility analysis (Telangana satellite, Tamil Nadu weather+satellite for 2019/2024), using the same Earth Engine / SoilGrids mechanisms already established in this project — this is new *environmental* data, not new *yield* data, and not a trained model.

## Phase 1 — Architecture plan (written before implementation)

Inspection of the existing pipeline found:

- `ingestion/config.py`: `FIELDS` is a hardcoded 7-entry list, each a hand-drawn ~1 km polygon with a fixed `field_id` (F001–F007). `CROP_CALENDARS` defines per-crop-tag (not per-season) planting windows.
- `ingestion/satellite_fetch.py` / `weather_fetch.py` / `soil_fetch.py` / `soil_fetch_ee.py`: all iterate `FIELDS`. `soil_fetch_ee.py` already has a `--districts` flag for a *different*, older 417-district registry (`data/raw/external/datagovin/district_registry.json`), built by `ingestion/district_fields.py` for a Kharif-only, 2000–2012-scoped national dataset unrelated to the three Southern India yield collections this task concerns.
- `ingestion/district_weather_pull.py` / `district_landsat_pull.py`: already-proven district-scale, polygon-based (not centroid) Earth Engine mechanisms, but wired to that same older registry.
- `ingestion/align_pipeline.py`: reads `{field_id}_ndvi.csv` + `{field_id}_weather_daily.csv` + soil, resamples to weekly, writes `{field_id}_aligned.csv`. Iterates `FIELDS` only.
- `training/dataset.py`: `build_dataset_from_processed()` iterates `FIELDS`, requires `data/processed/{field_id}_aligned.csv`. `WEATHER_COLS = [temp_c, precip_mm, humidity_pct, wind_speed_ms]`, `SOIL_COLS = [phh2o, soc, clay, sand, nitrogen]`. No code path reads a district registry or a `*_apy_clean.csv` file. `impute_missing_soil()` already takes a `fit_examples` parameter specifically to prevent train/val/test leakage (a real bug found and fixed earlier in this project) — the district pipeline must not regress that discipline.
- The Southern India source metadata/validation reports (re-read directly, not assumed) confirm: 868 real observations, 3 known boundary discontinuities (Telangana's retroactive pre-2014 state label, Tamil Nadu's Mayiladuthurai/Nagapattinam split, and — newly found during this task, see Phase 2 — GAUL's own inconsistent boundary vintage).

**Plan**: build a parallel, clearly-namespaced district pipeline that reuses the *proven mechanisms* (`district_geometry()`, `fetch_district_weather()`, `fetch_vegetation_indices()`, `cropland_mask_year()`, the SoilGrids REST/EE approach) via import, not duplication, but with its own registry, its own output directories, and its own alignment script — so nothing in the existing 7-field path is touched. New files only:

```
data/metadata/district_registry.csv                          (Phase 2)
ingestion/district_registry_build.py                          (Phase 2)
ingestion/district_season_calendar.py                         (Phase 3/4/7)
ingestion/district_env_pull.py                                (Phase 3/4)
ingestion/district_soil_pull.py                                (Phase 5)
ingestion/district_alignment.py                                (Phase 6/7/8)
data/raw/weather/southern_districts/{district_id}_weather_daily.csv
data/raw/satellite/southern_districts/{district_id}_landsat.csv
data/raw/soil/southern_district_soil_properties.csv
data/processed/district_multimodal_examples.csv                (Phase 6)
data/processed/DISTRICT_ALIGNMENT_VALIDATION_REPORT.md          (Phase 8)
```

## 2. Backward compatibility

Verified directly, not assumed: `PYTHONPATH=. python -c "from training.dataset import build_dataset_from_processed; print(len(build_dataset_from_processed()))"` still returns **21** (unchanged) after every change in this task. No existing file under `ingestion/`, `training/`, `data/raw/yield_labels/`, `data/processed/{F001..F007}_aligned.csv`, `backend/checkpoints/`, or `experiments/EXPERIMENT_1_REPORT.md` was modified. The old 417-district registry (`data/raw/external/datagovin/district_registry.json`) and its own weather/satellite/soil outputs (`data/raw/weather/districts/`, `data/raw/satellite/districts/`) are **read from**, never written to, by any new script.

## 3. District geography design

`ingestion/district_registry_build.py` builds `data/metadata/district_registry.csv` — one row per distinct `(state, district)` actually used by the three yield collections (62 total), matched against `FAO/GAUL_SIMPLIFIED_500m/2015/level2` by **normalized-name matching plus a short, individually-justified alias table** (documented renames/spelling variants only — e.g. Kadapa↔Cuddapah, a real 2011 rename; never a fuzzy matcher, per the same reasoning `ingestion/district_fields.py` already documents). Result: **53 of 62 districts matched** to a real GAUL polygon (centroid lat/lon stored; the polygon itself is used server-side for spatial aggregation, not stored in the CSV); **9 have no boundary source** and are recorded as such, not guessed:

`CHENGALPATTU, KALLAKURICHI, KRISHNAGIRI, MAYILADUTHURAI, RANIPET, TENKASI, TIRUPATHUR, TIRUPPUR, TIRUVARUR` (all Tamil Nadu).

**Two real boundary-source limitations were found and are recorded per-row in `administrative_boundary_notes`, not silently corrected:**

1. **GAUL's own boundary vintage is inconsistent, not uniformly "2015" despite the collection's name.** Krishnagiri (formed 2004) and Tiruppur (formed 2009) — both years before 2015 — have no GAUL entry at all, proving the dataset's actual boundary snapshot predates its own release-year label for at least some features. This means "GAUL 2015" cannot be treated as ground truth for any single specific year; it is a widely-used but imprecisely-dated administrative snapshot, documented as such rather than presented as authoritative.
2. **GAUL has no separate "Telangana" ADM1 entity.** All 10 Telangana districts match under `ADM1_NAME="Andhra Pradesh"` — Telangana's 2014 formation changed districts' state-level grouping, not their own boundaries, and GAUL has not been updated to reflect the new grouping. The district polygon itself is still usable (the physical boundary is correct), but this is recorded explicitly so no downstream code infers "Telangana" as a real historical state identity from this geometry match alone — consistent with the existing, separate finding in `data/raw/external/official_yield/telangana/source_metadata.md` that the yield source itself retroactively labels pre-2014 rows "Telangana".

## 4. Weather design

`ingestion/district_env_pull.py --kind weather` reuses `district_weather_pull.fetch_district_weather()` (ERA5-Land via Earth Engine, `ECMWF/ERA5_LAND/DAILY_AGGR`, real district polygons) unmodified — only the district list and target years are new. For Andhra Pradesh and Telangana, this task **reused the already-fetched 2000–2012 files** from the older registry (crosswalked by real GAUL district name, not re-fetched) rather than re-pulling identical data. For Tamil Nadu, **new data was fetched**: 30 GAUL-matched districts × 2 explicit years (2019, 2024 — not a wasted continuous range, since only those two years have yield labels), 60 successful pulls, 0 failures.

Temporal aggregation (`ingestion/district_season_calendar.py`, Phase 7): Kharif = June 1–Nov 30 of the label year; Rabi = Nov 1 of the label year–Apr 30 of the following year; Whole Year = Jul 1 of the label year–Jun 30 of the following year. These are **standard Indian agricultural-year conventions**, not per-district verified sowing dates — stated as such, matching the honesty standard `ingestion/config.py`'s own `CROP_CALENDARS` already sets (e.g. its `rice_punjab` entry: "general agronomic knowledge, not a cited government calendar document"). Every aggregation filters `window_start <= date <= prediction_cutoff_date` **before** computing any mean/sum — structurally, not by convention — so no post-harvest weather can enter a feature. A window whose observed days fall below 50% of the window's expected length (e.g. Tamil Nadu's Whole Year windows, which need data spanning into the following calendar year that was never fetched) is explicitly marked **unavailable**, not partially trusted — see `MIN_COVERAGE_FRACTION` in `ingestion/district_alignment.py`.

## 5. Satellite design

`ingestion/district_env_pull.py --kind satellite` reuses `landsat_fetch.fetch_vegetation_indices()` + `cropland_mask_year()` unmodified (the same district-polygon, cropland-masked, band-harmonized mechanism already proven for the older registry's Andhra Pradesh districts). **Polygon-based aggregation throughout — no district was ever approximated as a centroid point for weather or satellite matching**; centroids in `district_registry.csv` are for the registry/report only. New fetches this task ran: Tamil Nadu (2019, 2024 — in progress, see §9) and Telangana (2000–2012 — in progress, see §9). Sensor: Landsat 5/7/8/9 (same as the older registry, for methodological consistency across all three regions — not Sentinel-2, which only starts in 2017 and would create yet another cross-region inconsistency). Cloud/coverage limitation: recorded per-row via `scenes_observed` and `date_range_coverage` in the alignment output, not hidden — a district-season with satellite data but a coverage fraction below 50% is marked unavailable, same discipline as weather.

## 6. Soil-shortcut controls (Phase 5)

This project's own Experiment 1 found a soil-only control statistically matched full-multimodal accuracy (MAE 0.093±0.046 vs 0.085±0.041) — soil acts as a location fingerprint, not a genuine signal. The district pipeline is built so this **cannot be hidden**:

- `ingestion/district_soil_pull.py` fetches soil **completely separately** from weather/satellite, into its own file (`data/raw/soil/southern_district_soil_properties.csv`) with its own availability flag.
- `data/processed/district_multimodal_examples.csv` stores `soil_available` and all 5 `soil_*` columns independently of `weather_available`/`satellite_available` — a consumer can filter to exactly Weather-only, Satellite-only, Weather+Satellite, Soil-only, or Full-multimodal rows from the **same file**, by column selection alone, with no separate soil-only dataset to silently drift out of sync.
- Soil is **never imputed at alignment time** — a missing soil value stays `None` in the CSV. Any future imputation must go through `training/dataset.py`'s existing `impute_missing_soil(fit_examples=train_examples)` discipline (fit on train only), not a new, unaudited path.
- §10's evaluation plan explicitly requires a soil-only control be run and reported alongside every multimodal result, exactly as Experiment 1 already established — this report does not let a future run report only the multimodal number.

Soil result this task actually achieved: 47 of 53 GAUL-matched districts (89%) resolved via the ISRIC SoilGrids REST API; 6 failed (3 read-timeouts: Chittoor, Kurnool, Medak; 3 genuine nulls: Chennai, Salem, Hyderabad) — consistent with this project's own prior, documented finding (`ingestion/soil_fetch_ee.py`'s docstring) that the REST endpoint under-resolves relative to Earth Engine for Indian locations. The documented follow-up (not run in this task, to avoid Earth Engine quota contention with the concurrent weather/satellite fetches) is generalizing `soil_fetch_ee.py --districts` to the new registry for these 6.

## 7. Temporal leakage controls

Covered in detail in §4. Summary: **pre-harvest forecasting** is the one explicit task definition used throughout (features from season start through harvest/cutoff, nothing after) — no mid-season or post-harvest variant is mixed in. Every aggregation is date-filtered before computation, and a window with insufficient real coverage is marked unavailable rather than aggregated from a truncated, misleadingly-labeled sample.

## 8. Alignment statistics — COLLECTED vs MATCHED vs FULLY ALIGNED, never conflated

Snapshot at the time of writing this report (`ingestion/district_alignment.py`, output frozen in `data/processed/DISTRICT_ALIGNMENT_VALIDATION_REPORT.md`). **Two of the three new fetches this task launched (Telangana satellite, most of Tamil Nadu satellite) were still running in the background when this report was finalized — see §9 for exact re-run instructions to pick up more matches as they land.**

| | |
|---|---|
| 1. Official yield observations **collected** | **868** |
| 2. With real district geographic metadata (GAUL-matched) | **851** |
| 3. **Weather-matched** (real data covers ≥50% of the season window) | **544** |
| 4. **Satellite-matched** (same standard) | **270** |
| 5. **Soil-matched** (real SoilGrids value) | **733** |
| 6. **Fully aligned, weather+satellite** | **270** |
| — of which, fully aligned **multimodal** (+soil) | **219** |

**270 is the number to use for a weather+satellite study today. 219 for a full-multimodal study today. 868 is a data-collection count, not a training-set size — reporting it as one would be exactly the error this task's final rule warns against.** (These numbers were still climbing as the Tamil Nadu/Telangana satellite fetch launched by this task continued in the background after this report was written — see §9 for the exact re-run command; treat them as a floor, not a ceiling.)

Missing-data reasons (from the auto-generated validation report, not summarized away):

- 470 records: no satellite file exists for that district at all (Telangana: fetch in progress; unmatched TN districts: no boundary).
- 186 records: a weather file exists for the district but has no rows inside that specific season's window (mostly Rabi seasons whose window crosses into a year the continuous 2000–2012 pull doesn't reach, e.g. a 2012 Rabi season needing Jan–Apr 2013).
- 118 records: no soil match (109 = the 9 no-boundary districts × their record counts, plus the 6 REST failures' records).
- 111 records: no weather file exists for that district at all.
- 100 records: a satellite file exists but has no usable scenes inside the window.
- 17 records: no district boundary at all (the 9 unmatched TN districts).
- 25 records: weather or satellite file exists but covers under 50% of the window (the coverage-threshold rejection, mostly Tamil Nadu's single-calendar-year fetches falling short of a cross-year Whole Year window).

### Coverage by state

| State | Collected | Weather-matched | Satellite-matched | Soil-matched | Fully aligned (W+S) |
|---|---|---|---|---|---|
| Andhra Pradesh | 481 | 260 | 256 | 407 | 256 |
| Telangana | 313 | 227 | **0** (fetch in progress) | 272 | **0** |
| Tamil Nadu | 74 | 57 | 14 (fetch in progress, 30 targeted) | 54 | 14 |

### Coverage by year (selected)

1997–1998: 0 fully aligned each (pre-dates the 2000–2012 environmental pull entirely — a real, undisguised gap). 1999: 6. 2000–2011: 20/year, consistently (the fully-populated core of the AP+Telangana overlap window — Telangana's 0 satellite drags nothing down here because this row only counts AP). 2012: 10 (partial-year coverage in the source files). 2013–2014: 0 (outside the 2000–2012 environmental pull entirely — AP/Telangana's post-2012 years, another real, undisguised gap). 2019: 5 fully aligned of 36 collected (Tamil Nadu, satellite fetch in progress). 2024: 0 of 38 (satellite fetch had not yet reached 2024-window districts at snapshot time).

### Coverage by season

Kharif: 391 collected, 130 fully aligned. Rabi: 390 collected, 126 fully aligned. Whole Year: 87 collected, 7 fully aligned (the hardest season type to match, since it needs a window spanning two calendar years — see §4).

Full per-record detail, including every rejection reason attached to every individual observation, is in `data/processed/district_multimodal_examples.csv` (868 rows) and `data/processed/DISTRICT_ALIGNMENT_VALIDATION_REPORT.md`.

## 9. Data limitations

- **1997–1999 and 2013–2014 have zero weather/satellite coverage** for Andhra Pradesh and Telangana — the environmental pull this project has ever run (old or new) stops at 2000–2012. This is a real, unclosed gap, not fixed in this task.
- **Telangana satellite and the remaining ~23 of 30 Tamil Nadu satellite districts were still fetching when this report was written.** Re-running closes this gap further without any code change:
  ```
  python -m ingestion.district_env_pull --kind satellite --states "Tamil Nadu" --years 2019,2024
  python -m ingestion.district_env_pull --kind satellite --states "Telangana" --year-min 2000 --year-max 2012
  python -m ingestion.district_alignment
  ```
- **Tamil Nadu's Whole-Year windows are only ~50% fetchable with current data.** Its season is always "Whole Year" (Jul–Jun), but only the single calendar year matching the label year was fetched (Jan–Dec), not the following Jan–Jun. Closing this fully needs a second fetch for 2020 and 2025 partial ranges — not done in this task; flagged, not hidden behind a technically-true-but-partial "available" flag (the 50% coverage floor in §4/§7 already prevents that).
- **9 Tamil Nadu districts have no boundary source at all** (§3) — genuinely unmatchable with GAUL; a newer administrative boundary source (e.g. a post-2019 shapefile) would be needed, not attempted here.
- **6 districts have no soil match** (§6) — a documented, expected REST limitation with a known fix (Earth Engine) not run this pass.

## 10. Remaining blockers before training

1. Finish the in-progress Telangana/Tamil Nadu satellite fetches (§9) — mechanical, no design work left.
2. Extend AP/Telangana environmental coverage to 1997–1999 and 2013–2014, or explicitly restrict any district-scale model to 2000–2012 and state that restriction plainly.
3. Decide and implement a policy for Tamil Nadu's partial Whole-Year windows (fetch the missing half-years, or accept a documented Jan–Dec approximation instead of the true Jul–Jun window, stated as an approximation).
4. Build the actual PyTorch-side loader that reads `district_multimodal_examples.csv` into the model's existing input tensors — this report builds the data pipeline, not a new `SeasonExample`-equivalent loader; that is a distinct, not-yet-started task.
5. Only after 1–4: run the leakage-safe evaluation plan below.

## 11. Leakage-safe evaluation plan (for when training is authorized)

Per this project's own Experiment 1 finding (soil-only control matched full-multimodal accuracy) and this task's explicit requirement:

**Splits, headline first:**
1. **Unseen-district split (headline)** — hold out entire districts, never seen at any year during training. The only split design that tests a genuine environment→yield relationship rather than a per-district identity shortcut. Expect high variance at this scale (256 AP examples across 10 satellite-covered districts, 25–26 examples/district) — report it, don't hide it.
2. **Chronological split (secondary/continuity)** — train on earliest years, test on latest, matching Experiment 1's existing convention. Necessary but not sufficient (does not prevent district-identity leakage, since the same districts recur on both sides).
3. Random split — **not to be used as a headline result**, for the same reason Experiment 1 already established: at 10–13 satellite-covered districts, a random split all but guarantees the same district appears on both sides, rewarding memorization over generalization.
4. Unseen-state split — worth attempting once Telangana/Tamil Nadu satellite coverage closes, but state must be reported alongside the caveat that Tamil Nadu differs from AP/Telangana in era and season structure too, not just geography (already flagged in `experiments/SOUTHERN_INDIA_COMPATIBILITY_ANALYSIS.md` §6).

**Required baselines, every run:**
- Weather-only
- Satellite-only
- Weather + Satellite
- **Soil-only control** (mandatory, not optional — this is the check that would have caught Experiment 1's shortcut earlier if it had been run alongside the first multimodal result instead of after)
- Full multimodal (weather + satellite + soil)

A soil-only result that matches or beats weather+satellite on the **unseen-district** split, specifically, is the strongest possible evidence the shortcut is still present at district scale — that comparison, not the chronological or random split, is the one to trust.

## GO / NO-GO recommendation

**NO-GO for training. GO for completing §9's mechanical remaining fetches**, which are already running/queued and require no further design decisions.

The architecture is now real and working: 868 collected → 851 with real geography → 544/270/733 weather/satellite/soil-matched → **270 genuinely, mechanically aligned weather+satellite examples, 219 fully multimodal** — up from 0 at the start of this task, using real Earth Engine and SoilGrids data, with every non-match explained rather than hidden. That is still a modest number relative to 868, concentrated overwhelmingly in Andhra Pradesh 2000–2011 (256 of 270), with Telangana currently at 0 and Tamil Nadu at 14 pending an in-progress fetch. Training on ~270 examples this concentrated in one region and one 12-year window would produce a result that generalizes to little beyond that region and window — worth waiting for §9's fetches to land before drawing any conclusion, and worth running the unseen-district split, not a random or chronological one, as the very first thing once training is authorized.
