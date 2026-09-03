# Andhra Pradesh official yield data — source metadata

## Primary source used (real, official, government)

| | |
|---|---|
| Publisher | Government of India, Ministry of Agriculture and Farmers Welfare, Department of Agriculture and Farmers Welfare |
| Dataset title | "District-wise, season-wise crop production statistics from 1997" |
| Platform | data.gov.in (Open Government Data Platform India) |
| Resource ID | `35be999b-0208-4354-b557-f6ca9a5355de` |
| API endpoint | `https://api.data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de` |
| Dataset last updated (per source metadata) | 2021-07-13 |
| Raw file in this folder | `raw_datagovin_35be999b_andhra_pradesh_rice.csv` |
| Records | 481 (Andhra Pradesh, crop=Rice, all seasons, all years present) |
| Districts | 13 |
| Years covered | 1997–2014 |
| Seasons present | Kharif (234 rows), Rabi (234 rows), Whole Year (13 rows) |
| Retrieved | 2026-09-02, via `ingestion/datagovin_fetch.py` (already fetched earlier in this project; this task filters that same real, unmodified file to Andhra Pradesh rather than re-fetching, to avoid any risk of transcription error from re-summarizing 481 records through an intermediate tool) |

This satisfies source priority #1 (Government of India DES / Ministry of Agriculture) and #4 (data.gov.in) simultaneously — the data.gov.in resource **is** the DES/Ministry of Agriculture dataset, republished on the open-data platform, not a third-party re-host.

## Coverage gap against the requested 2019–2024 window — stated plainly, not hidden

**This source's Andhra Pradesh rice records stop at 2014.** The requested 2019–2024 window is not covered by this dataset. This is the same known limitation already documented elsewhere in this project (`data/raw/yield_labels/README.md`, `RESULTS.md` §5d) — the underlying government series itself does not appear to have been updated with district-level figures past the mid-2010s on data.gov.in.

## Secondary source identified but not downloaded (real, confirmed to exist, requires manual/browser access)

| | |
|---|---|
| Publisher | Directorate of Economics and Statistics (DES), Government of Andhra Pradesh |
| Role | Declared the State Agriculture Statistical Authority; state DES for Andhra Pradesh (source priority #3) |
| URL | https://des.ap.gov.in/MainPage.do?mode=menuBind&tabname=activities |
| Confirmed real categories seen on the site | "Crop wise 1st/2nd/3rd/4th Advance Estimates," "Final Estimates," under an Agriculture Statistics reports section |
| Status | **Reachable, confirmed to be a real official AP government statistics portal, but its actual downloadable report files were not located** — the site's navigation did not expose direct file links to this session's page-fetching tool (likely JS-driven navigation or PDF links not surfaced in the fetched page). Not included in the clean CSV. Would need direct browser navigation to retrieve. |

An independent web search additionally described (without a working direct download link found) a Government of India DES dataset spanning AP district-season-crop APY statistics "from 1997-98 to 2022-23" with "area in Hectares, production in Tonnes, yield in Tonnes per Hectare" — consistent with, and independent corroboration of, the unit assumption applied to the primary source above (see `validation_report.md` for exactly how units were verified). This more recent version of the series was not itself located at a fetchable URL in this session, so it is not the source of any row in `andhra_pradesh_apy_clean.csv` — noted here only as corroborating evidence for the unit determination.

## Sources checked and found unreachable or not usable

| Source | Result |
|---|---|
| `desagri.gov.in` / `data.desagri.gov.in` (GoI DES's own primary web portal, priority #1) | Unreachable from this environment — confirmed independently via two different fetch mechanisms in earlier work this session (local Python `requests`: connection refused/timeout; the WebFetch tool: no response). Not a guess; corroborated twice. |
| `aps.dac.gov.in` | Same — unreachable. |
| `eands.dacnet.nic.in` | DNS resolution failure (domain does not resolve from this environment). |
| Punjab-specific data.gov.in market-arrivals/procurement resources (checked in earlier, unrelated work this session) | Reachable, but not Andhra Pradesh data — not relevant to this task, noted only to distinguish "no unit stated" (which happened there) from this task's primary source, which does have corroborating unit evidence. |

No Kaggle datasets, scraped blog data, or manually-entered figures were used or considered, per the task's explicit restriction.
