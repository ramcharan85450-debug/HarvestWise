# Experiment 3, Phase 1 — coverage matrix of the current dataset

Source inspected: `data/processed/district_multimodal_examples.csv` (868 collected rows, 561 fully aligned) — the exact file Experiments 1 and 2 used. This document describes the dataset **before** any Experiment 3 collection, so the confound reduction in the final report has a fixed baseline to be measured against.

## 1. Collected vs aligned, by state

| State | Collected rows | Districts | Weather matched | Satellite matched | Soil matched | Fully aligned |
|---|---|---|---|---|---|---|
| Andhra Pradesh | 481 | 13 | 260 | 260 | 481 | 260 |
| Telangana | 313 | 10 | 227 | 227 | 313 | 227 |
| Tamil Nadu | 74 | 39 | 74 | 74 | 74 | 74 |
| **Total** | **868** | **62** | **561** | **561** | **868** | **561** |

Soil is 100% covered everywhere (it is static, one value per district). Weather and satellite are the binding constraints, and they fail together — a row is missing both or neither, because both were fetched per district-year and rejected by the same 50% window-coverage floor.

## 2. STATE × YEAR (fully aligned examples)

| State | 1999 | 2000 | 2001 | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2019 | 2024 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Andhra Pradesh | 10 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 10 | 0 | 0 |
| Telangana | 10 | 19 | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 0 | 0 | 0 |
| Tamil Nadu | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 36 | 38 |

**The confound is visible as a block structure.** The Tamil Nadu row and the AP/Telangana rows do not share a single non-zero column. This is the matrix form of Experiment 2's central limitation.

## 3. STATE × SEASON (fully aligned examples)

| State | Kharif | Rabi | Whole Year |
|---|---|---|---|
| Andhra Pradesh | 130 | 130 | 0 |
| Telangana | 109 | 118 | 0 |
| Tamil Nadu | 0 | 0 | 74 |

Season is confounded with region exactly as year is: no Tamil Nadu example shares a season label with any AP or Telangana example. A model cannot be given `season` as a feature without handing it region identity, which is why `training/district_dataset.py` excludes both `year` and `season`.

## 4. Satellite date-range coverage

| State | n | Mean coverage | Min | Max |
|---|---|---|---|---|
| Andhra Pradesh | 370 | 0.703 | 0.000 | 1.000 |
| Telangana | 313 | 0.715 | 0.000 | 1.000 |
| Tamil Nadu | 74 | **0.504** | 0.503 | 0.504 |

Every Tamil Nadu row sits at 0.503–0.504 — almost exactly half. This is structural, not coincidental: Tamil Nadu's season is `Whole Year`, whose window runs 1 July of year *Y* to 30 June of year *Y+1*, but only calendar years 2019 and 2024 were ever fetched. The Jan–Jun half of each window was never downloaded. Because the coverage floor is 50%, these rows pass by a margin of roughly 0.004 — they are the narrowest possible passes in the dataset.

This matters for interpretation: the Tamil Nadu satellite features are aggregates over the *first half* of each season window (Jul–Dec), while AP/Telangana Kharif features cover a fully-observed Jun–Nov window. The two are not aggregating comparable portions of a crop cycle.

## 5. SATELLITE SENSOR — what the data actually records

**Sensor identity is not stored anywhere in this dataset, and this is a genuine gap rather than an oversight I can resolve by inspection.**

The stored satellite files (`data/raw/satellite/**/*_landsat.csv`) have exactly these columns:

```
date, mean_ndvi, mean_evi, mean_ndwi, cloud_cover_pct
```

`ingestion/landsat_fetch.py:landsat_collection()` merges four collections — `LANDSAT/LT05`, `LE07`, `LC08`, `LC09` — into a single `ImageCollection` and then reduces each scene to a mean. The originating mission is available server-side but is never written out. The `satellite_source` column in the aligned CSV holds a **file path**, not a sensor.

Nor can the sensor be recovered from the date, because the missions overlap:

| Year | Missions operating | Uniquely determined? |
|---|---|---|
| 1999–2012 | Landsat 5, Landsat 7 | **No** — either |
| 2019 | Landsat 7, Landsat 8 | **No** — either |
| 2024 | Landsat 8, Landsat 9 (L7 retired 2022) | **No** — either |

Every year in this dataset falls in a multi-mission window. Assigning a sensor from the date would be a guess, which Phase 5 explicitly forbids. Sensor identity is therefore recovered by **re-querying Earth Engine per collection** (`experiments/sensor_inventory_probe.py`), and reported as a sampled inventory rather than a per-row label.

## 6. What this matrix establishes

1. Region, year and season are mutually confounded — a three-way block structure, not merely a two-way one.
2. Tamil Nadu's satellite windows are half-covered by construction, and pass the quality floor by ~0.4 percentage points.
3. Sensor generation is a fourth potential confound that the dataset **cannot currently report at all**, because it was never recorded.
4. Andhra Pradesh and Telangana lose ~30% of their collected rows to missing weather/satellite (1997–1999 and 2013–2014 gaps), which is a coverage problem but not a confounding one.

Items 1 and 3 are what Experiment 3 sets out to break or measure.
