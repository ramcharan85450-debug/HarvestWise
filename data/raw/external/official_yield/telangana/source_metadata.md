# Telangana official yield data — source metadata

## Primary source used (real, official, government)

| | |
|---|---|
| Publisher | Government of India, Ministry of Agriculture and Farmers Welfare, Department of Agriculture and Farmers Welfare |
| Dataset title | "District-wise, season-wise crop production statistics from 1997" |
| Platform | data.gov.in (Open Government Data Platform India) |
| Resource ID | `35be999b-0208-4354-b557-f6ca9a5355de` |
| API endpoint | `https://api.data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de` |
| Raw file in this folder | `raw_datagovin_35be999b_telangana_rice.csv` |
| Records | 313 (state field = "Telangana", crop = Rice, all seasons/years present in the source for that state value) |
| Districts | 10 |
| Years covered | 1997–2014, with **2012 missing** (no rows for that year under any season) |
| Seasons present | Kharif (157 rows), Rabi (156 rows) — no "Whole Year" rows for this state, unlike the Andhra Pradesh subset of the same resource |
| Retrieved | 2026-09-03, via `ingestion/datagovin_fetch.py` (this project's existing fetch script, already used earlier this session for the same resource; this task filters that already-committed, unmodified file to `state == "Telangana"` rather than re-fetching, for the same transcription-integrity reason documented in the Andhra Pradesh collection) |

This satisfies source priority #1 (Government of India DES / Ministry of Agriculture) and #2 (data.gov.in) simultaneously — the data.gov.in resource **is** the DES/Ministry of Agriculture dataset, republished on the open-data platform, not a third-party re-host.

## CRITICAL FINDING — Telangana state-label boundary issue (Step 4 of the task), documented rather than silently resolved

Telangana was carved out of Andhra Pradesh and formally came into existence on **2 June 2014**. This resource's own `state_name` field nonetheless reports **"Telangana" for rows dated 1997–2014** — i.e., for years almost entirely *before* the state existed.

This label was **not introduced by this project's ingestion code**. `ingestion/datagovin_fetch.py` (line 98) copies `state_name` directly from the source API's own JSON field with no name mapping, remapping, or inference logic applied. So this is the publisher's own retroactive labeling of these historical district records under Telangana's post-2014 identity — not an error introduced by this collection task, and not something this task invented.

What this means for use of the data:

- **The district set is internally consistent with the district structure Telangana held at its 2014 formation** (Adilabad, Hyderabad, Karimnagar, Khammam, Mahbubnagar, Medak, Nalgonda, Nizamabad, Rangareddy, Warangal — the 10 original Telangana districts, before the 2016 state-level reorganization into 33 districts). This is a real corroborating check: if the source had mixed in a district that never belonged to the Telangana region, that would indicate a labeling error; it did not.
- **What it does NOT mean**: it does not mean a Telangana state government, or Telangana-specific administrative statistics collection, existed for 1997–2013. During that period these same districts were part of undivided Andhra Pradesh, and any contemporaneous official publication from that era would have reported them as Andhra Pradesh, not Telangana. This dataset's "Telangana" label is a **retrospective relabeling by the current publisher for continuity of the statistical series**, common practice for GoI district-series maintenance after a state bifurcation, not a claim that Telangana issued these statistics at the time.
- **No records were reassigned, merged, or reconciled by this task.** The `state` field is passed through exactly as the source reports it, for every row, with this caveat documented here rather than either (a) silently accepting "Telangana" as if it were a contemporaneous historical fact, or (b) silently relabeling pre-2014 rows back to "Andhra Pradesh," which the source itself does not do and which this task was explicitly told not to do by guessing.
- Per the task's Step 4 instruction ("If boundary reconciliation is required, STOP and document the issue rather than guessing"): **this is exactly that situation.** The issue is documented here in full rather than resolved by a judgment call, so that anyone using this file for the paper knows the state label reflects the *publisher's current-boundary convention*, not a historically contemporaneous state identity.

## Coverage gap against the requested 2019–2024 window — stated plainly, not hidden

**This source's Telangana rice records stop at 2014** (with 2012 additionally missing inside that range). The requested 2019–2024 window is not covered by this dataset — the same limitation already found for Andhra Pradesh from the same underlying GoI series.

## Secondary sources identified but not downloaded (real, confirmed to exist, requires manual/browser access)

| | |
|---|---|
| Publisher | Directorate of Economics and Statistics (DES), Government of Telangana |
| Role | State Directorate of Economics and Statistics for Telangana (source priority #3) |
| URLs checked | `https://www.des.telangana.gov.in/` (reachable) and `https://ecostat.telangana.gov.in/functional_area_des.html` (DNS resolution failure — does not resolve from this environment) |
| Confirmed real content seen on the reachable site | A "Latest Publications" list (e.g. "SEEEPC Volumes I–IV," "Telangana State Indicator Framework (SIF) 3.0 — 2025") — general state economic-statistics publications, not a direct link to district/season/crop-wise APY tables in the fetched page content |
| Status | **Reachable but no downloadable district-wise rice/paddy file was located** by automated page-fetching. Not included in the clean CSV. |

| | |
|---|---|
| Publisher | Telangana Open Data Portal (`data.telangana.gov.in`), collection: agriculture |
| Role | Telangana government statistical publications (source priority #5) |
| URL | https://data.telangana.gov.in/collection/agriculture |
| Status | **Reachable, but the page is JavaScript-rendered** — the fetched page returned only the site title, no dataset listing, so no specific dataset or file could be identified or verified as usable. Not included. |

| | |
|---|---|
| Publisher | Telangana Department of Agriculture |
| Role | Telangana Agriculture Department (source priority #4) |
| URL | https://agri.telangana.gov.in/ |
| Status | **Reachable, but same JS-navigation limitation** — "Reports" section exists per the site's menu but its contents were not exposed to automated fetching. A specific report URL found via search (`open_record_view.php?ID=1255`, "season and crop coverage report yasangi-2023-24") returned HTTP 404 when fetched directly. Not included. |

## Sources checked and found unreachable

| Source | Result |
|---|---|
| `data.desagri.gov.in/website/crops-apy-report-web` (GoI DES's own APY report portal) | Unreachable via WebFetch (no response) — consistent with `desagri.gov.in`/`aps.dac.gov.in` being unreachable from this environment, already documented in the Andhra Pradesh collection. |
| `ecostat.telangana.gov.in` | DNS resolution failure (`getaddrinfo ENOTFOUND`). |

## Sources explicitly NOT used, per the task's restriction

Dataful.in and IndiaStatDistricts.com both surfaced in search results with what looks like the same underlying district-wise Telangana rice series. Both are **third-party commercial data aggregators, not primary government publishers**, so neither was used as a source or cited as corroboration — consistent with the task's restriction against "random datasets." No Kaggle datasets, Wikipedia figures, blog data, or manually-entered values were used.
