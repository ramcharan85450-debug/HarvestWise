# Southern India data — combined validation and integration compatibility analysis

Scope: validate the three district-level Rice/Paddy collections (Andhra Pradesh, Telangana region, Tamil Nadu) against each other and against HarvestWise's existing pipeline, and determine what can be scientifically integrated. **No model was trained. No new data was fetched. `training/dataset.py`, the yield-label files, and model checkpoints were not modified** — this is analysis performed by reading existing files and running read-only checks against them.

---

## 1. Combined dataset statistics

| | Andhra Pradesh | Telangana region | Tamil Nadu | Combined |
|---|---|---|---|---|
| Records | 481 | 313 | 74 | **868** |
| Districts | 13 | 10 | 36 (2019) / 38 (2024) | — |
| Years | 1997–2014 | 1997–2014 (2012 missing) | 2019, 2024 only | 1997–2014 and 2019, 2024 |
| Seasons | Kharif, Rabi, Whole Year | Kharif, Rabi | Whole Year only | — |
| Unit confidence | Corroborated | Corroborated | Explicit | — |

Full detail in `data/raw/external/official_yield/SOUTHERN_INDIA_DATA_INVENTORY.md`.

## 2. Data-quality findings (Task 1 checklist, run directly against the three clean CSVs)

1. **Total records: 868** (481 + 313 + 74), verified by direct row count, not summed from documentation.
2. **Duplicate records across datasets: 0.** Checked on `(state, district, crop, season, year)` across all three files combined — no row appears in more than one file.
3. **Duplicate observations within each dataset: 0** for all three (AP: 0, Telangana: 0, Tamil Nadu: 0), on the same key.
4. **State/region naming**: exactly three distinct `state` values (`"Andhra Pradesh"`, `"Telangana"`, `"Tamil Nadu"`), no variant spellings.
5. **District-name normalization**: no normalized-name collisions within any single region, and no cross-region collisions (no district name in one region normalizes to the same string as a district in another). District spelling is preserved per-source, not force-unified — e.g. Tamil Nadu's two source years spell "Tiruchirapalli"/"Tiruchirappalli" and "Kanniyakumari"/"Kanyakumari" slightly differently, which was already flagged (not fixed) in that collection's own validation report.
6. **Crop-name consistency**: `"Rice"` in all 868 rows. No `"Paddy"`, no case variants.
7. **Season consistency**: **not unified across regions.** AP has Kharif (234)/Rabi (234)/Whole Year (13); Telangana has Kharif (157)/Rabi (156), no Whole Year rows; Tamil Nadu has Whole Year (74) only, no Kharif/Rabi split in the clean file (it exists in the raw TN source and in `tamil_nadu/raw/parsed_extraction_log*.csv`, but was deliberately not decomposed into the clean CSV — see that collection's validation report). Any downstream code that assumes one season vocabulary across all three regions will misbehave silently on Tamil Nadu.
8. **Year coverage**: AP 1997–2014 (18 years), Telangana 1997–2014 minus 2012 (17 years), Tamil Nadu 2019 and 2024 only (2 years). **Zero years are shared by all three regions.** AP and Telangana share their full range; Tamil Nadu shares no year with either.
9. **Geographic-level consistency**: `"district"` in all 868 rows — no state or national aggregate mislabeled as district-level.
10. **Unit consistency**: `"t/ha"` in all 868 rows. Already normalized at collection time (AP/Telangana via corroborated hectares/tonnes; Tamil Nadu via the source's own explicit units).
11. **Yield conversion consistency**: recomputing `production_tonnes / area_ha` and comparing to the stored `final_yield_t_ha` gives a mismatch of **0%** for every AP and Telangana row (yield was derived by the source using the same formula) and a mean mismatch of 1.4% (max 0.27 percentage points on any single Tamil Nadu row) for Tamil Nadu, where the source publishes yield as an independently-measured productivity rate rather than a pure quotient — expected and explained in that collection's validation report, not an error. 0 records exceed a 1% mismatch threshold.
12. **Impossible or suspicious yields**: 0 records outside 0.1–15 t/ha; 0 records outside a tighter 0.5–8 t/ha rice-plausible band. Observed range across all 868 rows: 0.81–5.27 t/ha.
13. **Administrative-boundary discontinuities**: two distinct, real ones, both already documented in the individual collections and repeated here because they matter for any combined use:
    - **Telangana**: the source retroactively labels district records "Telangana" back to 1997, before the state existed (June 2014). Geographically consistent (correct district set), but not a contemporaneous historical designation for most of the series.
    - **Tamil Nadu**: Mayiladuthurai was carved out of Nagapattinam district between the 2019 and 2024 snapshots. Nagapattinam's reported area drops from 169,222 ha (2019) to 67,999 ha (2024) for exactly this reason — not a real production collapse. The 2019 and 2024 district lists are not the same set (36 vs 38 districts) and must not be treated as a stable panel.

**No problem found above was silently fixed.** Every one is carried forward into this report and into the two collections' own validation reports.

## 3. Environmental coverage feasibility (Task 3 — analysis only, nothing fetched)

### Weather

- **Source in use**: two separate mechanisms exist in this codebase, not one.
  - `ingestion/weather_fetch.py` — ERA5 (Copernicus CDS), per the 7 hand-defined `FIELDS` in `ingestion/config.py`, over `START_DATE`–`END_DATE` = **2019-01-01 to 2025-12-31**. Confirmed actually fetched: `data/raw/weather/F001_weather_daily.csv` exists, spanning that range.
  - `ingestion/district_weather_pull.py` — ERA5-Land (`ECMWF/ERA5_LAND/DAILY_AGGR`), via Earth Engine, per real district polygons from a 417-district registry (`data/raw/external/datagovin/district_registry.json`). Confirmed actually fetched: **417 of 417 registry districts have a weather CSV on disk**, every one spanning exactly **2000-01-01 to 2012-12-30** (verified directly by reading file contents, not assumed from a config default).
- **Years available, as actually fetched today**: field-level = 2019–2025; district-level = 2000–2012. Neither mechanism has ever been run for 1997–1999 or 2013–2018.
- **Geographic resolution**: field-level = a hand-drawn ~1 km box per field; district-level = the real administrative district polygon (`FAO/GAUL_SIMPLIFIED_500m/2015/level2`).
- **Can historical weather be collected for 1997–2014?** **Yes, feasible, not yet done for the full window.** ERA5 (CDS) extends back to 1940; ERA5-Land (the district mechanism, via Earth Engine) extends back to 1950. Both comfortably predate 1997. The district mechanism has already proven this in practice for 2000–2012 (all 417 districts pulled successfully); extending it to 1997–1999 and 2013–2014 is a parameter change (`--year-min 1997 --year-max 2014`) and more Earth Engine compute time, not a new capability. This analysis does not fetch it, per the task's explicit instruction.

### Satellite

- **Source in use**: again two mechanisms.
  - `ingestion/satellite_fetch.py` — Sentinel-2 (Earth Engine), per the 7 `FIELDS`, over the same 2019–2025 window. Confirmed fetched: `data/raw/satellite/F001_ndvi.csv` exists, spanning 2019-01-04 to 2025-12-28.
  - `ingestion/district_landsat_pull.py` — Landsat, via Earth Engine, per the same 417-district registry, over the same 2000–2012 window as the district weather. Confirmed fetched: **201 of 417 registry districts have a satellite CSV on disk today** (in progress, not complete), each spanning 2000–2012 where present.
- **Can it cover 1997–2014?** **Yes, feasible.** Landsat 5 (1984–2013), Landsat 7 (1999–present) and Landsat 8 (2013–present) jointly cover the full 1997–2014 window — this was already the basis for capping the district registry at 2000–2012 as "the clean Landsat 5 era" (per `ingestion/district_fields.py`'s own `--year-max` default and comment), meaning 1997–1999 is reachable but was deliberately excluded from the first pass for data-quality reasons (early Landsat 5 scenes have different noise characteristics), not because it's unreachable. Extending to 1997–1999 would need that quality question re-examined, not just a parameter change.
- **Can it cover Tamil Nadu 2019 and 2024?** **Yes — and partially already does.** Sentinel-2 (the field-level mechanism, 2019–2025) directly covers both years. F001/F002/F003 (Sulur, Kinathukadavu, Annur — all real localities inside **Coimbatore district**, Tamil Nadu) already have real Sentinel-2 and ERA5 data spanning 2019–2025. Coimbatore also appears in the new Tamil Nadu yield collection for both 2019 and 2024. **This is not, however, a clean field-to-yield match** — see §5's caution below.

## 4. Matching feasibility (Task 4 — POTENTIALLY MATCHABLE vs ACTUALLY MATCHED, computed directly, not estimated)

**No join has ever been executed between the three new yield collections and any weather or satellite file. ACTUALLY MATCHED = 0 for all three regions, for both weather and satellite, without exception.** The counts below are what *could* be joined using data that already exists on disk today, computed by:
1. normalizing district names and matching each yield record's district against the 417-district registry's district list for the same state,
2. checking whether that matched district has a weather file and/or a satellite file on disk,
3. checking whether the yield record's year falls inside the weather/satellite files' actual fetched range (2000–2012, verified directly from file contents — **not** the registry's own `"years"` field, which reflects an older Kharif-only yield-label year list and is not the same as the weather/satellite pull's date range).

| Region | Total yield records | District name matches registry | Year inside 2000–2012 | **Potentially weather-matchable** | **Potentially satellite-matchable** | **Actually matched** |
|---|---|---|---|---|---|---|
| Andhra Pradesh | 481 | 10 of 13 districts (KADAPA, SPSR NELLORE, VISAKHAPATANAM have no registry match) | 338 records | **260** | **260** (AP satellite pull is complete: 10/10 registry districts) | **0** |
| Telangana | 313 | 10 of 10 districts | 217 records | **217** | **0** (Telangana satellite pull has not reached these districts: 0/10 on disk) | **0** |
| Tamil Nadu | 74 | 22 of 39 distinct district values (17 unmatched, mostly post-2016 district splits: Chengalpattu, Kallakurichi, Ranipet, Tirupathur, Mayiladuthurai, Tenkasi, etc., which the registry — built from an older district set — never had) | **0 records** (Tamil Nadu's years are 2019/2024; the district-scale weather/satellite pull only covers 2000–2012 — **zero year overlap, regardless of district-name matching**) | **0** | **0** | **0** |
| **Total** | **868** | — | — | **477** | **260** | **0** |

**Why AP's weather and satellite potential are identical (260 = 260)**: AP is the only region where the satellite pull happens to be 100% complete for its own registry districts, so the satellite ceiling equals the weather ceiling there. This is a coincidence of pull order, not a structural fact — Telangana's 0 satellite-matchable makes that clear.

**Why Tamil Nadu's potential is 0 for both, from existing files**: not a data-quality problem with the Tamil Nadu collection — it is a pure consequence of the district-scale weather/satellite pull having only ever been run for 2000–2012, a window that shares no year with Tamil Nadu's 2019/2024 collection. Extending the pull to cover 2019 and 2024 is feasible (§3) but has not been done.

**The field-level Coimbatore exception, stated precisely**: F001/F002/F003 have real 2019–2025 Sentinel-2 and ERA5 data, and Coimbatore has real 2019 and 2024 district-level yield. Joining them is *technically* possible today without fetching anything new. It is **not counted in the table above** as "potentially matchable," because doing so would attach a **district-wide yield aggregate** to a **specific ~1 km field's imagery** — exactly the field-vs-region label mismatch this project's own `RESULTS.md` (§5) already identifies as the root cause of several of its earlier reported model failures. Three such rows would not meaningfully increase the usable dataset size and would reintroduce a known problem; they are named here so the option is visible, not silently used.

## 5. Geographic design check (Task 5)

Reading `ingestion/config.py` and `training/dataset.py` directly:

- **Field-level observations**: **supported natively**, and is the pipeline's only fully-wired path today. `FIELDS` in `ingestion/config.py` is a hardcoded list of 7 entries (`F001`–`F007`), each a hand-drawn ~1 km polygon with a fixed `field_id`. `training/dataset.py`'s `build_dataset_from_processed()` iterates over exactly this list and looks for `data/processed/{field_id}_aligned.csv` — confirmed only 7 such files exist.
- **District-level observations**: **partially supported, and not the way the new collections need.** The existing "district" label-granularity tier (`data/raw/yield_labels/district/`) swaps in district-sourced yield *values* for the same 7 physical field polygons — it does not add new spatial units. Separately, the 417-district registry + `district_weather_pull.py`/`district_landsat_pull.py` fetch real per-district weather/satellite data — but this has **never been run through an alignment step** to produce `{district_id}_aligned.csv` files; only F001–F007 have ever been aligned. `build_dataset_from_processed()` has no code path that reads a district registry or a `*_apy_clean.csv` file directly.
- **Multiple districts as first-class training units**: **not supported today.** Nothing in `training/dataset.py` loops over more than the fixed 7-entry `FIELDS` list.
- **Multiple states**: partially — the 7 fields already span 4 states (Tamil Nadu, Punjab, West Bengal, Andhra Pradesh) and the "state" label-granularity tier already demonstrates cross-state label-swapping works structurally at the field level. True multi-state district-level integration is not supported (same gap as above).
- **Changing administrative boundaries**: **no code handles this at all.** Every boundary issue found in this analysis and in the individual collections (Telangana's retroactive pre-2014 labeling, Tamil Nadu's Mayiladuthurai/Nagapattinam split, AP's 3 districts absent from the registry's older district set) was caught by manual documentation during collection, not by any validation code in the pipeline itself.

### Minimum architectural changes required to integrate this data

1. A **district-scale field registry loader** that generalizes `FIELDS` — either extending the existing `district_registry.json` mechanism or building a new one — that covers the *actual* district sets these three new `*_apy_clean.csv` files use (13 AP / 10 Telangana / 36–38 Tamil Nadu districts), not the older, differently-filtered 417-district registry, which only overlaps partially (§4).
2. An **alignment step** (an `align_pipeline.py`-equivalent) that turns each matched district's raw weather + satellite CSVs into a `{district_id}_aligned.csv` in the same shape `training/dataset.py` already expects — currently 0 districts have this; only the 7 hand-drawn fields do.
3. A **yield-label loader for the new schema** — the new files are one CSV per state (`state,district,crop,season,year,...`), not one CSV per `field_id` as `data/raw/yield_labels/{tier}/{field_id}_yield_labels.csv` currently requires. `build_dataset_from_processed()` would need a new code path, not a parameter tweak.
4. **Explicit boundary-aware record handling** — at minimum, a documented exclusion list or a boundary-change flag column, so a naive `(district, year)` join cannot silently pair a post-split Nagapattinam figure with a pre-split one, or treat a retroactively-labeled 1998 "Telangana" district as evidence the state existed then.
5. A **season-vocabulary reconciliation policy** — a decision (not yet made) on whether Tamil Nadu's `Whole Year` rows are compared against AP/Telangana's `Kharif`+`Rabi` combined, treated as a structurally different label type, or excluded from any single unified model — the current files do not resolve this, they only document that it exists.

**Per the task's explicit instruction, no district-level record has been converted into a fake field-level observation anywhere in this analysis or in the underlying collections.**

## 6. Data leakage analysis (Task 6)

- **Static soil features acting as location identifiers**: **already confirmed as a real, active risk in this project**, not hypothetical — `experiments/EXPERIMENT_1_REPORT.md` documents that a soil-only control (Experiment E) matched the full multimodal model's accuracy (MAE 0.093±0.046 vs 0.085±0.041), because `soil_x` is one fixed vector per field, constant across every season, so it functions as a field-identity fingerprint rather than a genuine environmental signal. This risk would be **structurally worse**, not better, if district-level SoilGrids data were added at AP/Telangana/Tamil Nadu scale: a district's derived soil properties change even more slowly than a single field's, so soil would even more strongly predict district identity, and thus indirectly predict that district's typical yield level, without the model learning any real weather-or-vision-to-yield relationship.
- **District identity leakage**: with only 10–13 districts repeated across 17–18 years each (AP, Telangana), a naive random split over all rows would place the *same* district in both train and test at different years far more often than not. A model can then learn "this is Guntur, Guntur usually yields ~X" rather than a genuine environment→yield mapping — statistically similar in effect to the soil-identity risk above, but present even without soil as an input, from the district label itself if it or any strong proxy of it reaches the model.
- **State identity leakage**: pooling all three regions naively is riskier than it looks, because state is trivially inferable from *structural* cues that have nothing to do with agronomy — Tamil Nadu's year values (2019/2024) fall completely outside AP/Telangana's range (1997–2014), and Tamil Nadu's season value is always `"Whole Year"` while AP/Telangana mix `Kharif`/`Rabi`. A model could learn "post-2015 or season=Whole Year → Tamil Nadu's yield distribution" as a shortcut, not a weather/vision relationship.
- **Duplicate districts across train/test**: mechanically the same failure mode as "district identity leakage" above — confirmed to be unavoidable under a plain random split at this district count (10–38 per region), not merely possible.
- **Repeated annual labels**: `experiments/EXPERIMENT_1_REPORT.md` §8 already found two of the original 5 test targets were exact repeats of values seen multiple times in training for the same field, from a coarse, slow-changing regional series. Not separately re-checked against the new 868-row collection in this pass (that would mean loading and joining data, outside this analysis's read-only scope), but flagged as the same category of risk to check for explicitly before reporting any result on these new districts, especially Telangana's slowly-varying pre-2014 series.
- **Temporal leakage**: mitigated by this project's existing convention of a **chronological** split (train = earliest examples, test = latest), already used in Experiment 1. Any new district-scale dataset should use the same discipline — sort by `season_start_date`/year before splitting, never shuffle first.
- **Normalization leakage**: `training/dataset.py` currently normalizes with **fixed constants** (`VISION_NORM`/`WEATHER_NORM`/`SOIL_NORM`), not a scaler fit on the pooled data — this specific leakage vector is already closed for the existing 7-field pipeline (verified in Experiment 1's leakage check). It would need re-verification, not re-fixing, if new districts with different soil/climate ranges are added, since fixed constants calibrated for 7 specific fields may not be the right normalization range for AP/Telangana/Tamil Nadu's much wider climatic spread — a distribution-shift concern, not strictly a leakage one, but adjacent enough to flag here.
- **Imputation leakage**: already found and fixed once in this project (`impute_missing_soil()`, now takes an explicit `fit_examples` parameter so a fill-in mean can never be computed from validation/test data — see `training/dataset.py`). Any new soil-imputation logic added for district-scale data must carry the same discipline from the start, not have it retrofitted after the fact as happened here.

### Recommended evaluation splits, in order of scientific strength

1. **Unseen-district split (strongest)** — hold out entire districts, never seen in training at any year, and test on them. This is the only split design that directly tests whether the model has learned a genuine weather/vision→yield relationship rather than a per-district identity shortcut, which is this project's own already-demonstrated primary failure mode (§ soil-as-identity above). With only 10–38 districts per region, expect **high variance** and report it honestly (as Experiment 1 already does with n=5, explicit no-p-value caveat) rather than a single confident number.
2. **Unseen-state split** — train on some states, test on a genuinely held-out one (e.g. train AP+Telangana, test Tamil Nadu). The strongest test of cross-region generalization, but **currently confounded** for this specific data: Tamil Nadu differs from AP/Telangana not just in geography but in era (2019/2024 vs 1997–2014) and season structure (Whole Year only vs Kharif/Rabi), so a poor or good unseen-state result today cannot be cleanly attributed to geography alone. This confound must be stated alongside any unseen-state result, not left implicit.
3. **Chronological split** — this project's existing convention (Experiment 1). Prevents future-information leakage, but does **not** prevent district-identity leakage, since the same districts recur across years on both sides of the cut. Necessary, not sufficient, and should not be reported as the sole evidence of generalization.
4. **Random split (weakest)** — should not be used as a headline result for this data. At 10–38 districts, a random split over-places the same districts on both sides far more than a chronological or unseen-district split would, making it the split most vulnerable to the district/soil-identity shortcut already confirmed active in this project.

**Recommendation for the paper**: report chronological as a baseline (for continuity with Experiment 1's existing methodology) but treat **unseen-district** as the headline generalization claim, with variance stated explicitly. Do not report a random split as evidence of anything beyond in-sample fit.

## 7. Recommended architecture

Given §5's findings, the minimum viable path is:

1. Build a district field registry scoped to *these three collections'* actual districts (13+10+36–38), reusing the existing `district_registry.json`/GAUL-matching approach but not its Kharif-only, 2000–2012-biased filter.
2. Run `district_weather_pull.py` and `district_landsat_pull.py` (already-proven mechanisms, just with different `--year-min`/`--year-max` arguments) to close the two real gaps identified in §3: 1997–1999 and 2013–2014 for AP/Telangana, and 2019/2024 for Tamil Nadu.
3. Write a district-scale alignment step alongside the existing field-scale `align_pipeline.py`, producing `{district_id}_aligned.csv` in the same shape.
4. Add a yield-label loader that reads the `*_apy_clean.csv` schema directly, with explicit, code-level exclusion of the two known boundary-discontinuity cases (pre-2014 Telangana rows if used as a pre-2014 signal at all; cross-year Nagapattinam/Mayiladuthurai comparisons) rather than relying on this document as the only safeguard.
5. Only after 1–4 exist does an unseen-district evaluation (§6) become possible to run honestly.

**None of this was implemented in this task, per its explicit "do not modify `training/dataset.py`" instruction.**

## 8. Recommended train/test strategy

Per §6: chronological split as a continuity baseline, unseen-district split as the primary reported generalization result, unseen-state result reported only with the era/season confound stated alongside it, random split not used as a headline number.

## 9. Maximum realistically usable dataset size

**Not 868.** Being precise about what "usable" means at each stage:

- **868** — real, validated yield records collected. This is a data-collection achievement, not a training-set size.
- **477** — potentially weather-matchable using files that already exist on disk (260 AP + 217 Telangana + 0 Tamil Nadu), pending §5's architectural work (registry scoping, alignment step, new label loader) actually being built.
- **260** — potentially satellite-matchable using files that already exist on disk (all from AP; Telangana and Tamil Nadu currently have 0 satellite coverage in their year ranges).
- **0** — actually matched into a training-ready example today. No join has been run.

If the §3 gaps are closed (1997–1999/2013–2014 weather+satellite for AP/Telangana, and 2019/2024 weather+satellite for Tamil Nadu — all confirmed technically feasible, none yet done), the realistic ceiling rises toward AP's 481 + Telangana's 313 = **794** (the two regions with a full potential year/district match once gaps are closed) plus Tamil Nadu's 74 if 2019/2024 environmental data is fetched — **up to 868** in the best case, still far short of if every record could be matched with zero further work. **As of today, the number of genuinely matched, training-ready observations is 0.**

## 10. GO / NO-GO recommendation

**GO — for further architectural work and targeted environmental data collection, in the order given in §7. NO-GO for training on this data today.**

The yield data itself is real, validated, and free of the errors Task 1 checked for (0 duplicates, 0 unit inconsistencies, 0 impossible values, both known boundary issues documented rather than hidden). The blocker is entirely on the environmental-matching and architecture side, not the yield data's quality: **zero of the 868 records have ever been joined to weather or satellite data**, and the pipeline has no code path to do so at district scale yet.

### Recommended next exact step

Do **not** train yet. The next step is §7 item 1–2: build a district registry scoped to these three collections' real districts, then run the already-proven `district_weather_pull.py`/`district_landsat_pull.py` mechanisms for the specific gaps identified in §3 (AP/Telangana: 1997–1999 and 2013–2014; Tamil Nadu: 2019 and 2024) — closing the gap that currently makes Tamil Nadu's potential match count 0 is the highest-value single action, since it is the newest, best-documented (explicit units), and most recent-era collection of the three, and is currently the one with zero environmental coverage of any kind. Only after that data exists on disk does an honest unseen-district evaluation (§6) become possible to run and report.
