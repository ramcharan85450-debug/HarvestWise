# Experiment 4, Phase A1 — satellite pipeline inspection

Read directly from source, not assumed. Files inspected:
`ingestion/landsat_fetch.py`, `ingestion/district_env_pull.py`, `ingestion/district_landsat_pull.py`, `ingestion/district_alignment.py`.

## 1. Earth Engine collections queried

From `landsat_fetch.LANDSAT_COLLECTIONS`:

| Collection ID | Sensor | Platform |
|---|---|---|
| `LANDSAT/LT05/C02/T1_L2` | Landsat 5 TM | LANDSAT_5 |
| `LANDSAT/LE07/C02/T1_L2` | Landsat 7 ETM+ | LANDSAT_7 |
| `LANDSAT/LC08/C02/T1_L2` | Landsat 8 OLI | LANDSAT_8 |
| `LANDSAT/LC09/C02/T1_L2` | Landsat 9 OLI-2 | LANDSAT_9 |

All are **Collection 2, Tier 1, Level-2 surface reflectance** (`T1_L2`). One auxiliary collection is used for masking: `MODIS/061/MCD12Q1` (IGBP land cover), classes 12 (Croplands) and 14 (Cropland/Natural-vegetation mosaic).

## 2. Sensors included

All four missions above are **merged into a single ImageCollection** by `landsat_collection()`:

```python
for cid in LANDSAT_COLLECTIONS:
    coll = _harmonized(cid).filterBounds(region).filterDate(...).filter(CLOUD_COVER <= 70)
    merged = coll if merged is None else merged.merge(coll)
```

This merge is the root cause of the provenance gap: after it, the originating mission is no longer distinguishable in the reduced output.

## 3. Which years map to which sensors

Mission operating ranges overlap, so **a year does not determine a sensor**:

| Year range in this project | Missions that could contribute | Uniquely determined? |
|---|---|---|
| 2000–2012 | Landsat 5, Landsat 7 | **No** |
| 2019 | Landsat 7, Landsat 8 | **No** |
| 2024 | Landsat 8, Landsat 9 | **No** |

Every year present in this dataset falls inside a multi-mission window. Inferring the sensor from the year would be a guess, and Experiment 4 does not do it. Measured evidence confirms the mixture: across the 15 Tamil Nadu districts re-fetched with provenance for 2000–2012, **4,308 scenes came from Landsat 7 and 3,081 from Landsat 5** — both missions contribute substantially to the same period.

## 4. Bands used

| Role | L5/L7 (TM/ETM+) | L8/L9 (OLI) |
|---|---|---|
| BLUE | `SR_B1` | `SR_B2` |
| RED | `SR_B3` | `SR_B4` |
| NIR | `SR_B4` | `SR_B5` |
| SWIR1 | `SR_B5` | `SR_B6` |

## 5. How bands are renamed

`_harmonized()` selects the four mission-specific band names and renames them to `["BLUE", "RED", "NIR", "SWIR1"]` **before any index is computed**. This is correct and non-trivial: `SR_B4` is NIR on TM/ETM+ but RED on OLI, so computing an index from raw band numbers across missions would silently compute NIR/RED on one sensor and RED/GREEN on the other.

## 6. Scaling

`SR_SCALE = 0.0000275`, `SR_OFFSET = -0.2`, applied as `DN * scale + offset` inside `_harmonized()`. Correct for Collection 2 Level-2, and necessary rather than cosmetic: EVI's formula contains additive constants (`+1`, `-7.5*BLUE`), so feeding it unscaled integer DNs produces a quantity that is not EVI at all.

## 7. Cloud masking

`_mask_clouds()` reads the `QA_PIXEL` bitmask and rejects pixels where any of bits **1 (dilated cloud), 3 (cloud), 4 (cloud shadow), 5 (snow)** are set. A scene-level filter is also applied: `CLOUD_COVER <= MAX_CLOUD_COVER_PCT` (**70**, from `ingestion/config.py`). Identical for all four missions.

## 8. Compositing

**There is no compositing.** `fetch_vegetation_indices()` maps a `reduceRegion(Reducer.mean())` over each individual scene and returns one row per scene. Rows whose `mean_ndvi` is null are dropped by `ee.Filter.notNull`. Temporal aggregation happens much later and outside Earth Engine, in `district_alignment._aggregate_satellite()`, which averages the per-scene values falling inside a season window.

Consequence for provenance: each stored row corresponds to exactly one scene from exactly one mission, so per-row sensor attribution is well defined — `MULTI_SENSOR` is never needed for newly fetched rows. It is only needed for legacy rows, where the merge destroyed the attribution.

Spatial reduction uses `scale=30` by default but **`scale=100` for district pulls** (`district_env_pull.pull_satellite`), with `bestEffort=True` and `maxPixels=1e9`. Averages are restricted to MODIS cropland pixels via `cropland_mask_year(mid_year)`.

## 9. Indices produced

Computed in `_with_indices()`:

| Index | Formula |
|---|---|
| NDVI | `normalizedDifference(NIR, RED)` |
| EVI | `2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)` |
| NDWI | `normalizedDifference(NIR, SWIR1)` — Gao (1996), vegetation water content |

Stored columns in the legacy writer: `date, mean_ndvi, mean_evi, mean_ndwi, cloud_cover_pct`. **No sensor, no collection ID, no pixel counts.**

## 10. Assessment

What the pipeline gets right — band renaming, SR scaling, a uniform cloud mask, and one consistent index definition across all four missions — is more than many published pipelines do, and it means the indices are *arithmetically* comparable across sensors.

What is genuinely absent:

1. **Per-row provenance.** Fixed for new fetches by `ingestion/district_satellite_provenance_pull.py`, which queries each collection separately and records `collection_id`, `sensor_name`, `satellite_platform`, `observation_year`, window bounds, `image_count`, `valid_pixel_count`, `district_cropland_pixels` and `coverage_fraction`.
2. **Cross-sensor radiometric harmonization.** No Roy-style OLI↔ETM+ reflectance transform is applied. Band renaming aligns *wavelengths*, not *spectral response functions*. This remains unaddressed — deliberately, because Experiment 3 measured the L7−L5 NDVI offset at only +0.032 with p = 0.30 (n = 6), which is not a sufficient basis for altering real observations.
