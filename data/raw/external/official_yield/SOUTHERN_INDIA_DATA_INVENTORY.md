# Southern India official yield data — inventory

Covers the three district-level Rice/Paddy collections completed so far: Andhra Pradesh, the Telangana region, and Tamil Nadu. This is an inventory of what exists on disk today — it does not imply any of it has been joined to weather, satellite, or soil data yet (see `experiments/SOUTHERN_INDIA_COMPATIBILITY_ANALYSIS.md` for that).

## Summary table

| | Andhra Pradesh | Telangana region | Tamil Nadu |
|---|---|---|---|
| Observations | 481 | 313 | 74 |
| Districts | 13 | 10 | 36 (2019) / 38 (2024) — not the same 36/38 |
| Years | 1997–2014 (18 distinct years) | 1997–2014, **2012 missing** (17 distinct years) | **2019 and 2024 only** (2 distinct years) |
| Seasons present | Kharif (234), Rabi (234), Whole Year (13) | Kharif (157), Rabi (156) | Whole Year (74) only |
| Geographic level | District | District | District |
| Unit confidence | **Corroborated** (methodology description + plausibility check + exact reproduction of source's own yield) — not printed explicitly by the source | **Corroborated**, same method as AP (same publisher, same resource) | **Explicit** — printed directly on the source tables (`in Ha.`, `in Tonnes`, `Kg/Ha`) |
| Source | Government of India, Ministry of Agriculture/DES, via data.gov.in (resource `35be999b`) | Same resource as AP, filtered to `state == "Telangana"` | TN Agriculture Dept (TNAGRISNET, 2019) + TN Directorate of Economics and Statistics (Season and Crop Report 2024-25) |
| Source priority tier (per this project's own collection tasks) | #1/#2 combined (data.gov.in **is** the GoI DES dataset) | Same as AP | #1 and #2 — genuinely higher-priority sources than AP/Telangana had available |
| Retrieved | 2026-09-02/03 | 2026-09-03 | 2026-09-03 |
| Rejected records | 0 | 0 | 1 (Chennai 2019-20, missing production/yield in source) |

## Known limitations, by region

**Andhra Pradesh**: stops at 2014, does not reach the project's preferred 2019–2024 window. 13 of AP's ~22 rice-growing districts are covered — a real subset, not fabricated to complete the set. Units are corroborated, not first-party-labeled.

**Telangana region**: the source's own `state_name` field retroactively labels every row "Telangana" back to 1997, thirteen years before the state existed (June 2014). Verified as the publisher's own convention (not introduced by this project's code), and as geographically consistent (all 10 districts are genuine Telangana-region districts, none borrowed from coastal Andhra/Rayalaseema) — but it is **not** a contemporaneous historical designation for the pre-2014 majority of the series. Year 2012 is entirely absent. Also stops at 2014.

**Tamil Nadu**: only two snapshot years exist, five years apart, with no continuous series in between — this is not a time series in the way AP/Telangana are. The district set changed between the two years: Mayiladuthurai was carved out of Nagapattinam between 2019 and 2024, so "Nagapattinam" does not mean the same administrative area in both years. Each row is an annual total; season-level (Kar/Kuruvai, Samba/Thaladi, Navarai/Kodai) figures exist in the raw source files but were not decomposed into the clean CSV.

## Cross-region compatibility, checked directly (not assumed)

- **Schema**: identical 13-column schema across all three files (`state,district,crop,season,year,area_ha,production_tonnes,final_yield_t_ha,yield_unit,geographic_level,source_name,source_url,retrieved_date`).
- **Crop**: `"Rice"` in all 868 rows, no variant spellings.
- **Geographic level**: `"district"` in all 868 rows.
- **Unit**: `"t/ha"` in all 868 rows — already normalized to a common unit at collection time, not left as a downstream problem.
- **Yield plausibility**: all 868 rows fall inside 0.81–5.27 t/ha, well within a plausible 0.1–15 t/ha band for Indian district-level rice.
- **Duplicates**: 0 duplicate `(state, district, crop, season, year)` combinations within any single file, and 0 across all three files combined (checked directly, not inferred).
- **Season vocabulary is NOT unified**: AP and Telangana use `Kharif`/`Rabi`/`Whole Year`; Tamil Nadu uses only `Whole Year`. A query that assumes every region reports the same seasons will silently return nothing for Tamil Nadu's Kharif/Rabi split, because that split was never included in the clean file (see limitation above).
- **Year ranges do not overlap between Tamil Nadu and the other two regions at all** — AP/Telangana cover 1997–2014, Tamil Nadu covers 2019 and 2024. There is no year in this combined inventory that all three regions share data for.

## Files

```
data/raw/external/official_yield/
├── andhra_pradesh/
│   ├── raw_datagovin_35be999b_andhra_pradesh_rice.csv
│   ├── andhra_pradesh_apy_clean.csv        (481 rows)
│   ├── source_metadata.md
│   └── validation_report.md
├── telangana/
│   ├── raw_datagovin_35be999b_telangana_rice.csv
│   ├── telangana_apy_clean.csv             (313 rows)
│   ├── source_metadata.md
│   └── validation_report.md
├── tamil_nadu/
│   ├── raw/  (5 official PDFs + 2 text extracts + 2 audit CSVs)
│   ├── tamil_nadu_apy_clean.csv            (74 rows)
│   ├── source_metadata.md
│   └── validation_report.md
└── SOUTHERN_INDIA_DATA_INVENTORY.md        (this file)
```

**Combined total: 868 real, validated district-level Rice/Paddy observations across 3 regions.** This number describes what has been *collected and validated*, not what is usable for model training — see the compatibility analysis for how many of these can actually be paired with environmental data today.
