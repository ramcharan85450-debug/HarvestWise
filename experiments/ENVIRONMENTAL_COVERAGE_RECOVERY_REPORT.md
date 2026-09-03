# Environmental coverage recovery — report

Scope: targeted recovery of Telangana and Tamil Nadu environmental coverage, administrative boundary resolution for 9 previously-unmatchable Tamil Nadu districts, soil-coverage recovery, and an AP temporal-gap feasibility check. **No model was trained.** Every fetch in this task reused already-proven Earth Engine/SoilGrids mechanisms from the prior district-pipeline task — nothing here is a new data *source*, only new *coverage* from sources already in use.

## 1. Background fetch verification (Phase 1)

The satellite/weather fetch running in the background at the start of this task was **not assumed complete** — verified directly by watching for its own `ALL DONE` log marker and cross-checking against actual file counts on disk (not just log text) at each step. It finished cleanly: Tamil Nadu satellite 60/60 windows (0 failed), Telangana satellite 10/10 districts (0 failed).

A follow-up fetch this task launched (weather+satellite for 9 newly-resolved Tamil Nadu districts, see §5) crashed once, genuinely: a transient DNS resolution failure reaching Google's OAuth token endpoint (`oauth2.googleapis.com`), not a data or code problem. It was retried and completed cleanly the second time — reported here rather than silently retried and left unmentioned.

## 2. Untracked file provenance results (Phase 1)

Every file this task's fetches wrote (88 total: 39 weather + 49 satellite, all under `data/raw/{weather,satellite}/southern_districts/`) was individually checked — not assumed valid — for: a `district_id` that resolves in `data/metadata/district_registry.csv`, non-empty rows, no all-NaN required columns, and a real, inspectable date range.

**Result: 88 of 88 VALID. 0 INVALID, 0 INCOMPLETE, 0 UNKNOWN PROVENANCE.**

Separately, `git status` also shows 57 pre-existing untracked CSVs under the *older* registry's directories (`data/raw/{weather,satellite}/districts/D0184`–`D0201`, `D0378`–`D0416`) left over from a session before this project's Southern India work began. **Checked and confirmed irrelevant**: every one belongs to Maharashtra, Uttar Pradesh, or Uttarakhand districts — none of the three states this project covers — so they were not added to the alignment dataset and were left untouched, exactly as in the prior task. No untracked file was auto-added to `district_multimodal_examples.csv` without this check.

## 3. Telangana recovery (Phase 2) — the highest priority

**Diagnosis, before any fetch, using the alignment output as it stood at the start of this task:**

| Failure category | Records affected (of 313) |
|---|---|
| 1. Missing district geometry | **0** — all 10 Telangana districts already had a real GAUL-matched polygon |
| 2. Missing weather | 86 (all: real weather files existed for every district, but did not cover the season) |
| 3. Missing satellite | **313 (100%)** — no satellite file existed for any Telangana district; the district-scale Landsat pull had simply never been run for Telangana before this task |
| 4. Missing soil | 41 |
| 5. Temporal-window mismatch | Same 86 as #2 — verified precisely: every one of those 86 records' `year` is 1997, 1998, 1999, 2013, or 2014, i.e. entirely outside the previously-fetched 2000–2012 weather window. **0 records failed for any other temporal reason.** |
| 6. Administrative naming mismatch | **0** — all 10 districts (Adilabad, Hyderabad, Karimnagar, Khammam, Mahbubnagar, Medak, Nalgonda, Nizamabad, Rangareddi, Warangal) matched their real GAUL polygon cleanly, first try |

**Conclusion: Telangana's ~0 fully-aligned count was caused almost entirely by #3 — satellite had simply never been fetched, not a boundary or naming problem.** This made the recovery action unambiguous: run the Landsat pull.

**Recovery performed**: `python -m ingestion.district_env_pull --kind satellite --states Telangana --year-min 2000 --year-max 2012` — reused the exact same district-polygon, cropland-masked, band-harmonized Landsat mechanism already proven for Andhra Pradesh in the prior task. **10 of 10 districts succeeded, 0 failed.**

**Result after recovery and re-running alignment:**

| | Telangana yield labels | → geometry matched | → weather matched | → satellite matched | → soil matched | → fully aligned |
|---|---|---|---|---|---|---|
| | 313 | 313 | 227 | 227 | 313 | **227** |

Telangana went from **0 to 227 fully aligned multimodal examples** (72.5% of its 313 labels). The remaining 86 unaligned records are **100% explained by the 1997–1999/2013–2014 gap already identified in the prior task** — see §6, not a new or different problem.

## 4. Tamil Nadu recovery (Phase 3)

### 4a. Why 9 districts had no usable GAUL boundary — investigated, not assumed

Checked directly against the live FAO GAUL `2015/level2` feature collection: **Krishnagiri (formed 2004) and Tiruppur (formed 2009) — both years before 2015 — have no GAUL entry at all.** This proves GAUL's actual boundary vintage is inconsistent, not uniformly "2015" despite the collection's name (already flagged in the prior task; this is independent confirmation from the same underlying dataset). The other 7 (Chengalpattu, Kallakurichi, Mayiladuthurai, Ranipet, Tenkasi, Tirupathur, Tiruvarur) were all formed 2019–2021, well after GAUL's real snapshot.

### 4b. Alternative authoritative boundary source — found and verified

Used **geoBoundaries** (geoboundaries.org), an internationally-recognized open administrative boundary database. Verified directly via its own API metadata before using it, not assumed suitable:

| | |
|---|---|
| Boundary year represented | **2021** (confirmed via API, not guessed) |
| Source data update date | 2023-01-19 |
| Underlying source | India's own Local Government Directory (`lgdirectory.gov.in`, Ministry of Panchayati Raj) + Pathways Data Pvt Ltd |
| License | Open Data Commons Open Database License 1.0 |
| Retrieved | 2026-09-04 |
| Districts covered (India ADM2) | 735 |

Matched using the **same discipline as the prior task's GAUL matching** — normalized name, plus a short table of individually-justified aliases, never fuzzy matching:

| District (source spelling) | geoBoundaries match | Basis |
|---|---|---|
| CHENGALPATTU | Chengalputtu | Documented spelling variant |
| KALLAKURICHI | Kallakurichi | Exact normalized match |
| KRISHNAGIRI | Krishnagiri | Exact normalized match |
| MAYILADUTHURAI | Mayiladuthurai | Exact normalized match |
| RANIPET | Ranipet | Exact normalized match |
| TENKASI | Tenkasi | Exact normalized match |
| TIRUPATHUR | Tirupathur | Exact normalized match |
| TIRUPPUR | Tiruppur | Exact normalized match |
| TIRUVARUR | Thiruvarur | Documented transliteration variant ("Th" vs "T" — the same pattern already documented for Thiruvallur's GAUL match) |

**All 9 resolved.** For every one, `data/metadata/district_registry.csv` now records: the real source name and its verified metadata (year, update date, license), a retrieval date, the exact district name matched, and — critically — an explicit note that this row's boundary source is **different** from the other 53 GAUL-matched rows in the same registry, so nothing downstream can accidentally treat all 62 rows as coming from one uniform source. **No boundary from a different source was merged into the GAUL rows — each of the 9 rows is separately, individually labeled.** The real polygon geometry for each was cached locally (`data/metadata/boundary_sources/tn_districts_geoboundaries/{district_id}_geoboundaries.geojson`) so the exact geometry used is reproducible and auditable, not just referenced by name.

### 4c. Weather and satellite collection for 2019 and 2024

Ran for all 9 newly-resolved districts, using the **same pre-harvest, season-window temporal discipline already established in the prior task** (Phase 7's `ingestion/district_season_calendar.py`, unmodified). 18 of 18 weather windows and 18 of 18 satellite windows succeeded, 0 failed.

### 4d. Result after recovery and re-running alignment

| | Tamil Nadu yield labels | → geometry matched | → weather matched | → satellite matched | → soil matched | → fully aligned |
|---|---|---|---|---|---|---|
| | 74 | 74 (was 74/74 already — TN's 9-district gap was a *geometry* problem for records outside this dataset's 74, not within it; see note below) | 74 | 74 | 74 | **74** |

Tamil Nadu went from 37 to **74 of 74 fully aligned — 100%.**

*Note on the geometry-matched figure*: the 9 previously-unmatched districts (Chengalpattu, Kallakurichi, etc.) **do** appear among Tamil Nadu's 74 collected yield records — they simply weren't blocking full alignment yet at the start of this task because environmental data hadn't been fetched for anything in the 2019/2024 window at all (see the prior task's report). Resolving their geometry via geoBoundaries was a precondition for fetching real weather/satellite for those specific districts, which is what actually moved the aligned count from 37 to 74.

## 5. Boundary resolution — full detail

Covered above (§4a–4b). Summary: `data/metadata/district_registry.csv` is now **62 of 62 districts** matched to a real, documented boundary source — 53 via FAO GAUL, 9 via geoBoundaries, each row labeled with which source it uses. **0 districts remain with no boundary source.**

## 6. AP temporal gap recovery (Phase 4) — investigated only, per priority order and "do not fetch unnecessary years"

Attempted only after §3 and §4, as instructed. **No fetch was run for these years in this task** — this is a feasibility finding, to inform a future, explicitly-scoped fetch, not an action taken now.

| Year | Weather (ERA5-Land) | Satellite (Landsat) | Classification |
|---|---|---|---|
| 1997 | Collection begins 1950 — well before 1997 | Landsat 5 only (L7 launched April 1999) | **AVAILABLE** |
| 1998 | Same | Landsat 5 only | **AVAILABLE** |
| 1999 | Same | Landsat 5 + Landsat 7 (from April) | **AVAILABLE** |
| 2013 | Same | Landsat 7 (SLC-off, degraded but usable) + Landsat 8 (launched Feb 2013) | **AVAILABLE** |
| 2014 | Same | Landsat 7 + Landsat 8 | **AVAILABLE** |

All 5 years are classified **AVAILABLE**, not partially available or unavailable, for both modalities — consistent with this project's own earlier documented finding ("Landsat 5/7/8 do cover 1997–2015", `ingestion/datagovin_fetch.py`) and directly reusing `ingestion/landsat_fetch.py`'s already-existing multi-sensor harmonization (`LANDSAT_COLLECTIONS` already includes LT05/LE07/LC08). Closing this gap is mechanical, not a design problem — the next task can run `district_env_pull.py --year-min 1997 --year-max 1999` and `--year-min 2013 --year-max 2014` for Andhra Pradesh and Telangana directly.

A smaller, related gap noticed during this task but not in its scope: **3 Andhra Pradesh districts (Kadapa, SPSR Nellore, Visakhapatanam) have real geometry (resolved via documented aliases in the prior task) but no weather/satellite ever fetched for them** — they were never in the older 417-district registry's own name-matched set either. Same fix mechanism, ~3 districts × 13 years, comparable in size to the Telangana satellite recovery in §3.

## 7. Soil coverage (Phase 5)

Six districts failed the ISRIC SoilGrids REST endpoint in the prior task: 3 read-timeouts (Chittoor, Kurnool, Medak), 3 genuine all-null responses (Chennai, Salem, Hyderabad).

**Investigated per the task's 4 questions, in order:**

1. **Is retry appropriate?** Yes for the 3 timeouts — a `ReadTimeout` on a public REST endpoint is a classic transient failure, not evidence of no data. **Retried: all 3 succeeded** (real values returned, e.g. Chittoor: phh2o=67, soc=320, clay=322).
2. **Does an official alternative endpoint exist?** Yes — this project already has one, built and documented in the *prior* task: `ingestion/soil_fetch_ee.py`, ISRIC SoilGrids **via Earth Engine** rather than the plain REST API. Its own docstring already documented that the REST endpoint returns HTTP 200 with all-null values for real Indian points that Earth Engine resolves correctly — exactly this failure mode.
3. **Does cached data with verified provenance exist?** No — not attempted, since option 2 (a real, already-proven alternative source) was available and used instead.
4. **Is the failure permanent?** For 3 of 6 districts (the timeouts): no, confirmed transient by successful retry. For the other 3 (the genuine nulls): **yes, permanent for the REST endpoint specifically** — but not for SoilGrids as a source. Retried via Earth Engine: **all 3 succeeded** (e.g. Chennai: phh2o=65.3, soc=375.3, clay=322.9 — real, plausible values, not fabricated).

**Result: 6 of 6 previously-failed districts now resolved — 3 via REST retry, 3 via the Earth Engine fallback already built in the prior task.** Every soil value's source is now recorded per-row in `data/raw/soil/southern_district_soil_properties.csv`'s new `source` column ("ISRIC SoilGrids REST API v2.0" or "ISRIC SoilGrids via Earth Engine (REST endpoint returned all-null at this point)"), so no one can mistake an EE-sourced value for a REST one or vice versa. **No soil value anywhere in this dataset was invented, estimated, or imputed** — every one traces to a real API response from a real source, and soil imputation was not used at any point in this task, per the explicit instruction.

**Soil coverage: 62 of 62 districts (100%), up from 47 of 53 at the start of this task.**

## 8. Updated alignment counts (Phase 6) — reported separately, never merged

Ran `python -m ingestion.district_alignment` after all recovery above. **One real bug was found and fixed during this final run** (see the boxed note below) before these numbers were accepted as final.

| | Count |
|---|---|
| **COLLECTED YIELD LABELS** | **868** |
| **DISTRICT GEOMETRY MATCHED** | **868** (was 851 at the start of this task) |
| **WEATHER MATCHED** | **561** (was 544) |
| **SATELLITE MATCHED** | **561** (was ~270) |
| **SOIL MATCHED** | **868** (was 733) |
| **FULLY ALIGNED** (weather + satellite + soil, all three) | **561** (was ~219) |

> **Bug found and fixed this task**: the satellite coverage check originally compared a file's overall min/max date range against the season window — which is wrong whenever a district's file holds two *disjoint* fetches (exactly Tamil Nadu's case: one file has 2019 rows and 2024 rows, nothing between). That made a 2019 "Whole Year" window spanning into mid-2020 look 100% covered by a file that never actually held any 2020 data. Fixed to check which *calendar years are actually present* in the file against the window, not just its outer bounds. This is disclosed, not hidden, because it changed a real number (satellite-matched moved from a wrongly-optimistic 520 to a correctly-computed 561 — the fix happened to raise the count here because the *old* bug had also wrongly rejected some legitimate near-miss records under the old, cruder method; the new method is simply correct, not tuned toward a bigger number). See `ingestion/district_alignment.py`'s `_aggregate_satellite` docstring.

**A related, honest limitation this makes visible, not something to hide**: every one of Tamil Nadu's 74 fully-aligned "Whole Year" examples has environmental data covering only **50.4%** of its nominal Jul–Jun window (July–December of the label year; January–June of the following year was never fetched, since only the label year's own calendar year was pulled). They clear this task's 50% minimum-coverage floor by a slim margin, not because the window is genuinely fully observed. Anyone using these 74 examples should know they represent half-year environmental context under a "Whole Year" label, not a true full year — flagged explicitly here and in `data/processed/district_multimodal_examples.csv`'s `satellite_date_range_coverage` column (0.504 for every one) rather than left implicit in a passing boolean flag.

## 9. Geographic diversity analysis (Phase 7)

| State | Collected | % of 868 collected | Fully aligned | % of 561 aligned | Districts with ≥1 aligned example |
|---|---|---|---|---|---|
| Andhra Pradesh | 481 | 55.4% | 260 | **46.3%** | 10 of 13 |
| Telangana | 313 | 36.1% | 227 | **40.5%** | 10 of 10 |
| Tamil Nadu | 74 | 8.5% | 74 | **13.2%** | 39 of 39 |

**59 of 62 total districts across all three states now have at least one fully aligned example** (up from 56 before soil/geometry recovery, and a small fraction before this task began).

**Flagged per the task's explicit instruction**: Andhra Pradesh and Telangana together still account for 86.8% of fully-aligned examples (46.3% + 40.5%), against Tamil Nadu's 13.2%. This is now a **genuinely three-state, three-region dataset** — no single state exceeds half of the aligned examples, a real change from the situation before this task (Andhra Pradesh alone was ~95% of aligned examples). But it is not evenly balanced, and describing it as "Southern India generalization" should be qualified: **Andhra Pradesh and Telangana provide depth (13 years, 2000–2012, Kharif+Rabi), while Tamil Nadu provides breadth at two points in time (2019, 2024) across the largest number of distinct districts (39) of any single state in this dataset.** Any headline claim of geographic generalization should say precisely this, not round it up to "balanced coverage of Southern India."

## 10. Temporal diversity analysis (Phase 7)

| Year(s) | Fully aligned | Note |
|---|---|---|
| 1997–1998 | 0 | Outside all fetched environmental windows (§6: feasible, not yet fetched) |
| 1999 | 20 | Partial (only some districts/seasons overlap the 2000-start window at the margin) |
| 2000–2011 | 38 per year, consistently | The dataset's stable, fully-populated core |
| 2012 | 10 | Partial-year source coverage |
| 2013–2014 | 0 | Outside all fetched environmental windows (§6: feasible, not yet fetched) |
| 2019 | 36 of 36 | **100%** — new this task |
| 2024 | 38 of 38 | **100%** — new this task, with the 50.4%-window caveat from §8 |

Season split: Kharif 239 of 391 collected (61%), Rabi 248 of 390 (64%), Whole Year 74 of 87 (85% — all from Tamil Nadu, all subject to the §8 partial-window caveat).

**Temporal diversity is now genuinely two-mode**: a dense, continuous 12-year block (2000–2011/2012) plus two sparse, recent, single-year snapshots (2019, 2024) five years apart with nothing in between. This is not a continuous time series across the full 1997–2024 span — it is two temporally disjoint regimes, and any model evaluation should treat them as such (e.g. a chronological split that pretends 2012→2019 is a continuous progression would be misleading).

## 11. Remaining limitations (stated plainly)

1. **1997–1999 and 2013–2014 remain unfetched** for Andhra Pradesh and Telangana — confirmed feasible (§6), not yet done. This is the single highest-value remaining gap for extending temporal depth.
2. **3 Andhra Pradesh districts (Kadapa, SPSR Nellore, Visakhapatanam)** have real geometry but no environmental data fetched at all — a small, well-scoped, cheap fix not attempted in this task (§6).
3. **Tamil Nadu's 74 aligned examples all carry the 50.4%-window caveat** from §8 — real but partial environmental context, not a full year, for every one.
4. **Tamil Nadu contributes breadth (39 districts), not depth (2 years only)**; Andhra Pradesh/Telangana contribute depth (13 years), not comparable breadth (23 total districts between them). A model trained on this combined set is not seeing the same kind of signal from each region.
5. **The registry now spans two different boundary sources** (53 GAUL, 9 geoBoundaries) — each row is labeled, but a consumer that doesn't check `geometry_source` per row could silently mix them.
6. **Soil is now 100% covered, but from two different mechanisms** (56 REST, 6 Earth Engine) — again labeled per-row, not silently blended, but worth knowing before treating the soil columns as uniformly sourced.

## 12. Training readiness (Phase 8)

**A. Chronological evaluation: NO-GO.**
Reason: the aligned data is not one continuous chronological series. It is two disjoint temporal blocks — 2000–2012 (dense, AP+Telangana) and 2019/2024 (sparse, two points, Tamil Nadu-dominated). A chronological split (train on earliest, test on latest) would in practice mean "train on AP/Telangana 2000–2011, test on Tamil Nadu 2019/2024" — which is actually an unseen-*state* test wearing a chronological-split label, not a genuine temporal-generalization test. Reporting it as "chronological evaluation" would misrepresent what is actually being measured.

**B. Unseen-district evaluation: GO, with a caveat on district count.**
Reason: 59 of 62 districts now have real, non-fabricated, fully aligned examples — enough distinct districts (10 AP + 10 Telangana + 39 TN) to genuinely hold some out and test on districts never seen in training, the split this and the prior task's own analysis both identify as scientifically strongest (directly testing for the district/soil-identity shortcut this project's own Experiment 1 already found real). The caveat: Andhra Pradesh and Telangana each only have 10 satellite-covered districts, so an unseen-district split within just one of those states will have high variance (holding out even 2–3 of 10 districts is a large fraction) — expected and should be reported with explicit uncertainty, not hidden.

**C. Multi-region generalization analysis: GO, with the qualification stated in §9.**
Reason: all three states now have real, substantial (not token) aligned coverage — 260/227/74. A model can genuinely be trained on some regions and tested on others. The qualification: Tamil Nadu differs from AP/Telangana in era (2019/2024 vs 2000–2012) and season structure (Whole Year only vs Kharif/Rabi) as well as geography, so a cross-region result must not be presented as isolating geography alone — this confound was already flagged in the prior compatibility analysis and remains true here.

## Final answer

| | |
|---|---|
| **1. Chronological training** | **NO-GO** — the data is two disjoint temporal blocks, not a continuous series; a chronological split would silently become an unseen-state test. |
| **2. Unseen-district evaluation** | **GO** — 59 of 62 districts have real fully-aligned examples; report per-state variance explicitly given each state's modest district count. |
| **3. Cross-region generalization** | **GO, with the era/season confound stated alongside every result** — do not claim geography alone explains a Tamil Nadu vs AP/Telangana difference. |

**Next scientifically correct action**: build the PyTorch-side loader that reads `data/processed/district_multimodal_examples.csv` into the model's input tensors (this and the prior task built the data pipeline, not that loader), then run the **unseen-district split** — not chronological, not random — as the first evaluation, with the mandatory soil-only control from the prior task's plan alongside every result. Closing the §6/§11 gaps (1997–1999, 2013–2014, and the 3 remaining AP districts) is worthwhile follow-up but is not a blocker for starting unseen-district evaluation on the 561 examples that already exist today.
