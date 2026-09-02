# Yield labels — source and status

## Current source (real, official, citable, year-varying)
Government of India, **Economic Survey 2025-26, Statistical Appendix,
Table 1.17: "Yield Per Hectare of Major Crops"**, Economic, Statistics &
Evaluation Division, Department of Agriculture and Farmers Welfare:
https://www.indiabudget.gov.in/economicsurvey/doc/stat/tab1.17.pdf

This table reports **national Kharif rice yield by agricultural year**, with
genuine year-to-year variation:

| Agricultural year | Kharif rice yield |
|---|---|
| 2019-20 | 2,622 kg/ha = 2.622 t/ha |
| 2020-21 | 2,607 kg/ha = 2.607 t/ha |
| 2021-22 | 2,705 kg/ha = 2.705 t/ha |
| 2022-23 | 2,735 kg/ha = 2.735 t/ha |
| 2023-24 | 2,780 kg/ha = 2.780 t/ha |
| 2024-25 | 2,825 kg/ha = 2.825 t/ha |

(Extended back to 2019-20 when `ingestion/config.py`'s START_DATE was widened
from 2022 to 2019 to give the Climate-Shock Benchmark more seasons. Note
2020-21 is genuinely *lower* than 2019-20 - the series is not monotonic, which
is exactly the real variation the labels are meant to carry.)

Applied to all three fields' `*_yield_labels.csv` as
`season_start_date=YYYY-08-01, final_yield_t_ha=<value above>`, matching each
real satellite/weather season by year (see `training/dataset.py`'s
`_match_yield_label`, which prefers this year-aware match over the older
day-of-year fallback described below).

**Why this replaced the earlier single-value label:** the 3 real Coimbatore
fields previously shared one repeated 2019-20 district figure applied to
every season, giving the label zero real variance — any MAE/accuracy
comparison against it was a plausibility check at best, not a statistically
meaningful benchmark. This national, year-matched series gives real variation
that lines up with the actual 2022-2025 satellite/weather data, at the cost
of being a **national average rather than Coimbatore-specific** — a genuine
trade-off, not a fabrication. Document both properties (real variation, but
national not local granularity) wherever this dataset's results are reported.

There is currently no matched label for the 2025 season (the Economic Survey
2025-26 table's most recent *final* estimate is 2024-25; the 2025-26 Kharif
figure is not yet published) — that season is simply dropped by
`build_dataset_from_processed()` rather than guessed.

## Superseded: original Coimbatore district figure (kept for reference)
Tamil Nadu Department of Economics and Statistics, Season and Crop Report,
table "V.5: Area, Yield and Production of Rice - Season Wise, Districtwise
2019-20": https://www.tnagrisnet.tn.gov.in/dashboard/report/05_05.pdf

Coimbatore district, Samba/Thaladi/Pishanam season - Area: 733 Ha,
Production: 2,667 Tonnes, Productivity: **3,641 kg/ha = 3.641 t/ha**. Real,
but a single 2019-20 data point that doesn't overlap the project's
2022-2025 satellite/weather coverage (see `_match_yield_label`'s day-of-year
fallback, which still uses this kind of label if a field's CSV only has one
row).

## Next improvement, if pursued
A genuinely **Coimbatore-specific, multi-year** series (from
https://des.tn.gov.in/en/node/18 or https://data.desagri.gov.in) would be
strictly better than the current national-average stand-in - swap it in the
same way (one row per available year) if found.

## Multi-state expansion: F004 (Punjab), F005 (West Bengal), F006 (Andhra Pradesh)
Real, named rice-growing localities added alongside the 3 Coimbatore fields
(see `ingestion/config.py` FIELDS - Ajnala/Amritsar, Burdwan, Amalapuram/East
Godavari), each with its own real satellite/weather/soil pull and its own
**state-specific, genuinely year-varying** yield series:

| Field | State | Source | Values (t/ha) |
|---|---|---|---|
| F004 | Punjab | CEIC Data, citing Directorate of Economics and Statistics, Dept. of Agriculture & Farmers Welfare, Govt. of India | 2021: 4.366, 2022: 4.340, 2023: 4.193 |
| F005 | West Bengal | same primary source, via CEIC | 2022: 2.995, 2023: 3.057 |
| F006 | Andhra Pradesh | same primary source, via CEIC | 2023: 3.393 |

**Sourcing caveat:** these were retrieved via CEIC Data (a data aggregator),
not fetched directly from the primary government page
(https://desagri.gov.in/document-report/4-1-5-state-wise-yield-of-rice/ or
the RBI's "Handbook of Statistics on Indian States"), because both were
unreachable (connection refused/timeout) from this environment when
attempted. CEIC explicitly attributes these figures to the correct primary
source, so they're real, not fabricated - but re-verify against the primary
government page directly if you can reach it, before relying on these
numbers for a publication claim.

**KNOWN GAP - state-specific labels do not cover 2019-2021.** When the date
range was widened back to 2019, the national rice series above was extended
(it is published in the Economic Survey PDF, which is directly fetchable), but
the state-specific series could NOT be: the primary government portals
(data.desagri.gov.in, aps.dac.gov.in) are unreachable from this environment
(connection refused) and CEIC returns HTTP 403 to automated fetches. So
F004-F007's pre-2022 seasons fall back to their nearest available labelled
year via `training/dataset.py`'s `_match_yield_label`. Those seasons carry
real satellite/weather/soil inputs but a borrowed label, so they add input
diversity without adding independent label variance - do not count them as
independent observations when reporting sample size. Fixing this means
manually pulling the state-wise rice/wheat yield series for 2019-2021 from
one of those portals in a browser and adding the rows.

**Excluded, not used:** CEIC's search results also returned Andhra Pradesh
figures for 2024 (3.822 t/ha) and 2025 (3.928 t/ha) that jump implausibly
far above the 2023 figure (3.393) and the national trend - rather than
include numbers I couldn't cross-check, they were left out. Only the 2023 AP
figure is used; F006 seasons in other years fall back to it via
`training/dataset.py`'s nearest-available-year matching.

Real coverage is now: **3 states beyond Tamil Nadu, 6 real fields total,
9 distinct real yield values across states/years** (vs. the single repeated
number this project started with) - still a small sample for a
statistically powered claim, but genuinely multi-state, multi-year real
data, not fabricated or synthetic.

## Multi-crop expansion: F007 (Punjab wheat)
Punjab genuinely runs a rice (kharif) / wheat (rabi) rotation on the same
land, so F007 reuses **F004's exact geometry** (same real field) with
`crop=wheat_punjab` instead of a fabricated separate location - the
satellite/weather raw data was copied from F004 rather than re-queried,
since it's the same polygon and F004's pull already spans the full
2022-2025 date range (covering both the kharif and rabi seasons at that
location).

| Field | State/Crop | Source | Values (t/ha) |
|---|---|---|---|
| F007 | Punjab wheat | CEIC Data, citing Directorate of Economics and Statistics, Govt. of India | 2022: 4.216, 2023: 4.748 |

Same CEIC-aggregator sourcing caveat as the multi-state section above
applies here too.
