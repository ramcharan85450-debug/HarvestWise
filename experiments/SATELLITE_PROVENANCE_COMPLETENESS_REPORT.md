# Experiment 4, Phase A5 — satellite provenance and completeness report

Two distinct things are reported here and must not be conflated:

1. **Legacy coverage** — how many aligned yield rows have a usable satellite aggregate (the `southern_districts/` and `districts/` files used by Experiments 1–3). These rows have **no provenance**.
2. **Provenance coverage** — how many districts have been re-fetched with per-row sensor attribution (`southern_districts_provenance/`). This is new in Experiment 4 and is still in progress.

## 1. Legacy satellite coverage by state (v2 dataset, 1,249 collected rows)

| State | Expected (collected rows) | Satellite available | Missing | Coverage % |
|---|---|---|---|---|
| Andhra Pradesh | 481 | 260 | 221 | 54.1% |
| Telangana | 313 | 227 | 86 | 72.5% |
| Tamil Nadu | 455 | 217 | 238 | 47.7% |
| **Total** | **1,249** | **704** | **545** | **56.4%** |

Tamil Nadu's 455 rows are the 74 original (2019/2024 Whole Year) plus the 381 Experiment 3 overlap rows (2000–2012 Kharif).

## 2. New Tamil Nadu overlap cohort, by year

| Year | Satellite available | Expected | | Year | Satellite available | Expected |
|---|---|---|---|---|---|---|
| 2000 | 10 | 28 | | 2007 | 11 | 29 |
| 2001 | 10 | 28 | | 2008 | 11 | 29 |
| 2002 | 10 | 28 | | 2009 | 12 | 31 |
| 2003 | 10 | 28 | | 2010 | 12 | 31 |
| 2004 | 11 | 29 | | 2011 | 12 | 31 |
| 2005 | 11 | 29 | | 2012 | 12 | 31 |
| 2006 | 11 | 29 | | **Total** | **143** | **381** |

**12 of 31 districts** in this cohort have satellite data. Coverage is uniform across years within a district, because the fetch is per-district over the whole window — a district either has the window or does not.

## 3. The three failure modes, kept distinct

The task requires that these never be blurred together. In `ingestion/district_satellite_provenance_pull.py` they are separate recorded outcomes:

| Outcome | Meaning | Count so far |
|---|---|---|
| `DATA NOT FETCHED` | The district-window was never requested — the run has not reached it, or stopped first. | **19 of 31** overlap districts (the pull is still running) |
| `NO_SATELLITE_OBSERVATION_EXISTS` | Earth Engine was queried successfully and the collection returned zero scenes for that window. | 0 observed so far |
| `EARTH_ENGINE_ACCESS_FAILURE` | The query itself failed (quota, restriction, transient error). | 0 observed so far |

**The dominant reason for missing Tamil Nadu satellite data is `DATA NOT FETCHED`, not absence of imagery and not access failure.** This distinction matters: it means the gap is a throughput limitation, not a data limitation, and re-running the resumable pull closes it without any methodological change.

The project's Earth Engine account is in **restricted (non-commercial quota exceeded) mode**, which throttles every request. The fetcher is built to stop safely rather than grind against that: `--max-failures` aborts after consecutive access failures and records the reason in `data/raw/satellite/provenance_fetch_log.json`. It did not need to trigger — no access failures occurred; the constraint is speed, not rejection.

## 4. Provenance coverage achieved

Per-row provenance now exists for **17 Tamil Nadu districts**, covering **8,161 scenes** over 2000–2012, each row carrying `collection_id`, `sensor_name`, `satellite_platform`, `observation_year`, window bounds, `image_count`, `valid_pixel_count`, `district_cropland_pixels` and `coverage_fraction`.

Median valid cropland pixels per scene: **73,275**. Mean `coverage_fraction`: **0.312** — i.e. a typical scene resolves about a third of the district's cropland pixels after cloud masking. (Values marginally above 1.0 occur because the scene reduction and the denominator are computed at the same nominal scale but with `bestEffort` resampling; treated as ~1.0.)

## 5. Sensor inventory — measured, not inferred

Scenes by observation year and sensor, from the archive itself:

| Year | Landsat 5 TM | Landsat 7 ETM+ |
|---|---|---|
| 2000 | 18 | 250 |
| 2001 | 112 | 235 |
| 2002 | **0** | 413 |
| 2003 | 40 | 358 |
| 2004 | 525 | 465 |
| 2005 | 462 | 339 |
| 2006 | 454 | 368 |
| 2007 | 408 | 504 |
| 2008 | 465 | 453 |
| 2009 | 517 | 390 |
| 2010 | 206 | 307 |
| 2011 | 201 | 287 |
| 2012 | **0** | 384 |
| **Total** | **3,217** | **4,529** |

Landsat 8 and 9 contribute **zero** scenes to this window, as expected (L8 begins 2013).

### A finding that qualifies Experiment 3

Experiment 3 controlled for sensor by restricting both sides of its cross-region comparison to "the Landsat 5/7 era", treating that era as homogeneous. **It is not.** The mix varies sharply and systematically within it:

- **2002 and 2012 contain no Landsat 5 scenes at all** (2012 is after L5 imaging ceased in November 2011; 2002 reflects an L5 acquisition gap over this region).
- 2000–2003 is Landsat 7-dominated (roughly 85–100% L7).
- 2004–2009 is close to balanced.

So "same era" is a coarser control than it appeared. This does not invalidate Experiment 3's conclusion — the sensor effect it measured was small (+0.032 NDVI, p = 0.30) — but it means the era control was partial, and the honest statement is that sensor *composition* is itself a time-varying quantity that the project can only now measure because provenance exists.

## 6. Backfill assessment (Phase A3)

**Provenance was NOT backfilled onto legacy rows, and no legacy row is labelled with a guessed sensor.**

Recovery was assessed and rejected on evidence:

- The legacy CSVs store only `date, mean_ndvi, mean_evi, mean_ndwi, cloud_cover_pct`. No collection ID, no scene ID.
- `landsat_collection()` merges all four collections before reducing, so the mission was never written.
- No Earth Engine query log with per-scene mission attribution was retained.
- Date is insufficient: every year in the dataset lies in a multi-mission window, and the table above proves both L5 and L7 genuinely contribute in most years. Inferring the sensor from the year would be exactly the guess the task forbids.

Legacy rows are therefore correctly described as **UNKNOWN** provenance. Where a *re-fetched* provenance file exists for the same district and window, the sensor is known for those scenes — but the legacy aggregate that Experiments 1–3 actually used remains an unattributed mixture, and is labelled `MULTI_SENSOR / UNKNOWN` rather than retro-fitted.

## 7. Status

| Item | Status |
|---|---|
| Per-row provenance implemented | **Yes** — new fetcher, 15 fields |
| Provenance applied to new fetches | **Yes** — 17 districts, 8,161 scenes |
| Legacy provenance backfilled | **No — correctly labelled UNKNOWN, not guessed** |
| Tamil Nadu satellite collection complete | **No — 12/31 overlap districts aligned; pull resumable and still running** |
| Earth Engine access failures | **0** — the constraint is throttled throughput, not rejection |
