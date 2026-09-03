# Tamil Nadu official yield data — source metadata

## STEP 1 — Sources discovered and investigated

| Publisher | Dataset/report title | Official URL | Years covered | Geographic level | Crop coverage | Area? | Production? | Yield? | Units explicit? | Downloadable? |
|---|---|---|---|---|---|---|---|---|---|---|
| Tamil Nadu Agriculture Department (TNAGRISNET) | "V.5: Area, Yield and Production of Rice — Season wise, Districtwise 2019-20" | https://www.tnagrisnet.tn.gov.in/dashboard/report/05_05.pdf | 2019-20 only (single-edition dashboard publication) | District | Rice only | Yes | Yes | Yes | **Yes — explicit** (`AREA (in Ha.)`, `PRODUCTION (in Tonnes)`, `PRODUCTIVITY (Kg/ Ha)` printed as literal column headers) | **Yes — downloaded** |
| Tamil Nadu Directorate of Economics and Statistics | "Season and Crop Report 2024-25", Table IV-A "Area under Food Crops — 2024-25" | https://www.tn.gov.in/crop/areaunderfoodcrops.pdf | 2024-25 | District | All food crops, incl. Paddy | Yes | — | — | **Yes — explicit** (`( in ha.)` printed under the table title) | **Yes — downloaded** |
| Tamil Nadu Directorate of Economics and Statistics | "Season and Crop Report 2024-25", Table V-B "Production of Crops during 2024-25" | https://www.tn.gov.in/crop/productionofprincipalcrops.pdf | 2024-25 | District | All principal crops, incl. Rice | — | Yes | — | **Yes — explicit** (`( in Tonnes)`) | **Yes — downloaded** |
| Tamil Nadu Directorate of Economics and Statistics | "Season and Crop Report 2024-25", Table V-A "Districtwise Average Yield Rates of the Crops for the Year 2024-25" | https://www.tn.gov.in/crop/averageyieldrateofcrops.pdf | 2024-25 | District | All crops, incl. Rice | — | — | Yes | **Yes — explicit** (`(in kg / ha)`) | **Yes — downloaded** |
| Tamil Nadu DES | Table II "Area, Production and Yield rate of principal crops" (state-level summary) | https://www.tn.gov.in/crop/areaproductionandyield.pdf | 2024-25 | **State**, not district | Principal crops | Yes | Yes | Yes | Yes — explicit | Downloaded, but **not used** (wrong geographic level for this task) |
| Government of India, Ministry of Agriculture / DES (via data.gov.in) | "District-wise, season-wise crop production statistics from 1997" | https://api.data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de | 1997–2013 for Tamil Nadu specifically | District | Rice (filtered) | Yes | Yes | Derived | Not stated by source; corroborated in the AP/Telangana collections from this project | Yes (already fetched earlier this project) — **not used for this task**, see rationale below |
| Telangana/AP state DES pattern check: Tamil Nadu Agriculture Dept main site | https://agri.telangana.gov.in equivalents were not applicable; TN's own https://www.tnagriculture.in/dashboard/book | Index of ~485 reports | 1934–2021 (dashboard snapshot) | District (varies) | All crops | — | — | — | — | Index page only — see below |

## Why priority 1/2 sources were used instead of the GoI DES fallback (priority 3/4)

Unlike Andhra Pradesh and Telangana — where no state-level source could be located with a working download link, forcing reliance on the GoI DES data.gov.in resource — **Tamil Nadu's own Department of Economics and Statistics and Agriculture Department publish exactly the requested tables with working, directly downloadable PDF links and explicit unit labels.** Per the task's source priority (TN DES first, TN Agriculture Dept/AGRISNET second, GoI DES third, data.gov.in fourth), these were used as the primary and only sources. The GoI DES/data.gov.in resource (already used for Andhra Pradesh and Telangana) was checked for Tamil Nadu coverage and found to run 1997–2013 only — older, and with non-explicit units, than what the priority-1/2 sources provide — so it was **not used** for the clean CSV, consistent with the task's explicit priority ordering (a higher-priority, better-documented source should not be superseded by a lower-priority one).

## Sources found but not usable

| Source | Status |
|---|---|
| Tamil Nadu Open Data / TNAGRISNET dashboard index (`https://www.tnagrisnet.tn.gov.in/dashboard/book`) | Reachable; confirmed the 2019-20 rice report (05_05.pdf) is the **only** district-wise rice Area/Production/Yield table in that dashboard edition — no equivalent report for 2020-21, 2021-22, 2022-23, or 2023-24 was found in the same index. |
| `https://www.tnagrisnet.tn.gov.in/dashboard/report/` (directory listing) | HTTP 403 Forbidden — directory browsing is blocked; individual report files must be reached via known filenames. |
| TN state DES Season and Crop Report — earlier editions (2019-20 through 2023-24, i.e. the DES's own equivalent of the district APY tables for years between the two datasets used here) | The DES's `tn.gov.in/crop/` URL pattern serves the **current** edition only (currently 2024-25); no archive of prior editions' equivalent PDFs at stable URLs was located by this session's tooling. Not fabricated or estimated — simply not found. |

## STEP 2/3 — Raw files preserved

All stored unmodified in `raw/`:

| File | Content |
|---|---|
| `tnagrisnet_05_05_rice_2019-20.pdf` | Original TNAGRISNET district-wise rice APY table, 2019-20 |
| `tn_crop_stat_areaunderfoodcrops.pdf` | TN DES Table IV-A, area under food crops incl. Paddy, 2024-25 (61 pages, all food crops — Paddy is on pages 1–2) |
| `tn_crop_stat_productionofprincipalcrops.pdf` | TN DES Table V-B, production of principal crops incl. Rice, 2024-25 (14 pages — Rice is on page 1) |
| `tn_crop_stat_averageyieldrateofcrops.pdf` | TN DES Table V-A, districtwise average yield rates incl. Rice, 2024-25 (13 pages — Rice is on page 1) |
| `tn_crop_stat_areaproductionandyield.pdf` | TN DES Table II, state-level (not district) APY summary — downloaded for completeness, not used in the clean CSV |
| `tnagrisnet_2019_20.txt`, `productionofprincipalcrops.txt` | Plain-text extractions (`pdftotext -layout`) kept alongside the PDFs for auditability |
| `parsed_extraction_log.csv` | Full season-wise (Kar/Kuruvai/Sornavari, Samba/Thaladi/Pishanam, Navarai/Kodai) breakdown for every 2019-20 district, exactly as parsed and validated — kept for anyone who wants sub-annual detail beyond the annual totals in the clean CSV |
| `parsed_extraction_log_2024.csv` | Per-district area/production/yield for 2024-25 plus the cross-check column described in `validation_report.md` §5 |

## Extraction method and why it required care

The 2024-25 DES tables are ruled, multi-page PDF tables where two districts' rows are sometimes packed into a single visually-merged table row (a rendering artifact of the source PDF, not of this task). A naive text extraction risks silently misattributing one district's numbers to another. This was handled with `pdfplumber`'s structured table extraction, splitting merged cells on their internal line breaks and re-pairing them index-for-index with the corresponding district-name cell — then **every single resulting row was cross-checked** two ways before being trusted (see `validation_report.md` §4–5): (a) do the three season components (Kar/Kuruvai, Samba/Thaladi, Navarai/Kodai) sum to the source's own printed Total, and (b) does `area × yield-rate` reproduce the source's own printed production figure. Both checks passed for every district in both years, which is the basis for treating this extraction as reliable rather than a guess.

## Retrieved

2026-09-03, via direct HTTPS download (`curl`) of each PDF from its official government URL, followed by text/table extraction as described above. No page content was summarized through an intermediate AI tool for the numeric values used in the clean CSV — every number in `tamil_nadu_apy_clean.csv` traces to a specific cell in a specific downloaded PDF, verifiable by re-opening the file in `raw/`.
