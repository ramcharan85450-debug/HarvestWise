# Real yield-label collection plan — Punjab (Amritsar), rice + wheat

Scope: F004 (Ajnala, Amritsar, rice_punjab) and F007 (same field, rice-wheat
rotation, wheat_punjab) — the location recommended in this project's scope
analysis, because it already has real satellite/weather/soil pulled and
already has labels at all three tiers (national, state, district), making it
the lowest-risk place to add depth rather than start a new location from
zero.

## 1. Required schema (confirmed by reading the code, not assumed)

`training/dataset.py`'s `build_dataset_from_processed()` reads
`data/raw/yield_labels/{field_id}_yield_labels.csv` (default tier) or
`data/raw/yield_labels/{tier}/{field_id}_yield_labels.csv` for
`tier in {"national", "state", "district"}`, via:

```python
labels = pd.read_csv(labels_path, parse_dates=["season_start_date"])
...
final_yield = float(match.iloc[0]["final_yield_t_ha"])
```

**Only two columns are actually required:**

| Column | Type | Notes |
|---|---|---|
| `season_start_date` | date, any pandas-parseable format (ISO `YYYY-MM-DD` used throughout this project) | Matched against each real season's start date - see matching rule below |
| `final_yield_t_ha` | float | Tonnes per hectare - **must already be converted to this unit before being written**, `_match_yield_label` does no unit conversion |

Matching rule (`_match_yield_label`, `training/dataset.py:63-87`): prefers a
row within 45 days of the season's real start date (exact year-aware match);
if none exists, falls back to day-of-year matching (ignoring calendar year)
within 30 days, preferring the chronologically nearest year among those. A
file with only one row is silently reused for every season via this
fallback — which is exactly why label years and satellite years must
actually overlap to count as independent observations (see README.md's
"KNOWN GAP" section for where this already happened).

**Six recommended (not required) metadata columns**, added in this session
to every existing file and validated by `ingestion/validate_yield_labels.py`:
`geographic_level`, `source_name`, `source_url_or_id`, `original_unit`,
`retrieved_date`, `crop`. These are inert to `training/dataset.py` (confirmed:
grep shows no other script reads or rewrites these files, so extra columns
are carried harmlessly) and exist purely so a reader of the CSV itself —
not just the README prose — can see what a number is and where it came from.

## 2. Rules this plan follows

1. **No field-level yield is invented.** If no real field-level (F004/F007
   -specific) measurement can be found, none is added — the existing
   national/state/district tiers stay as they are, honestly labelled at
   their real resolution, rather than being relabelled or duplicated as
   field-level.
2. **District or state averages are never written with
   `geographic_level=field`.** The validator (`validate_yield_labels.py`)
   explicitly flags any row claiming `field`-level so that claim gets a
   second look before being trusted.
3. **Every dataset states its geographic level explicitly** in the
   `geographic_level` column, not only in prose.
4. **Units are normalized to t/ha in `final_yield_t_ha`**, with the
   as-reported unit preserved in `original_unit` for audit (e.g. a
   government table reporting kg/ha or quintal/ha keeps that original label
   even after the conversion is applied to the column the model reads).
5. **Dates are standardized** to `season_start_date` in ISO `YYYY-MM-DD`,
   consistent with every other file in this project.
6. **Source is preserved per row**, not only in a README — `source_name`
   and `source_url_or_id` (a URL, or a data.gov.in resource ID where that is
   the more stable identifier) travel with the data itself.

## 3. Sources, in priority order

### District-level (Amritsar) — highest priority, see reasoning below

| Priority | Source | What it offers | Status |
|---|---|---|---|
| 1 | data.gov.in resource `1ec5d89e-6cff-4358-958c-67432e7a73f9` — "District-wise market arrivals of Paddy crop from 1978 to 2021" (Punjab Dept. of Economic and Statistical Organization) | District-level paddy arrivals to **2021** — 7 years fresher than the district source currently in use (which stops 2014) | Already discovered in `district_yield_candidates.json`, not yet fetched |
| 2 | data.gov.in resource `93fc715e-22cc-4db9-ba35-6aaaea3e6246` — "District-wise procurement of Paddy crop by different PSWC from 1994 to 2021" | District procurement volumes to 2021 - a real proxy for harvest timing and volume, not yield directly | Already discovered, not yet fetched |
| 3 | Punjab State Agricultural Marketing Board (Mandi Board) | Mandi-level arrivals/prices, potentially more recent than either data.gov.in resource | Not yet checked - requires locating the correct public dataset/portal |
| 4 | Directorate of Agriculture, Punjab / *Statistical Abstract of Punjab* (annual) | District area/production/yield tables | Not yet checked |
| 5 | Food Corporation of India (FCI) district wheat procurement (MSP) | District-level wheat procurement by year — real, official, wheat-specific (the current district source is rice-only, so F007/wheat has no district tier at all yet) | Not yet checked |

**Why district-level is the priority**, not state or field: this project's
own controlled granularity sweep (`RESULTS.md` §5d) already measured that
district-resolution labels are where the deep model's disadvantage against
tree ensembles nearly disappears (+0.009 t/ha vs. +0.045 national /
+0.081 state). Extending the district tier with fresher (to-2021), real
Punjab-specific sources is the single highest-value, lowest-risk addition:
it directly attacks the one confound the sweep already identified (stale
labels with no overlap to the real 2019-2025 satellite window), using
sources that have already been found to exist, not sources that still need
to be located.

### State-level

| Priority | Source | Status |
|---|---|---|
| 1 | Directorate of Economics & Statistics (DES), Ministry of Agriculture, Govt. of India — the primary source CEIC (currently used) itself cites | Not yet accessed directly; DES's own portal (`desagri.gov.in`) returned connection-refused from this environment when previously tried (see `README.md`) — would need to be attempted from a different network, or via a browser |
| 2 | *Agricultural Statistics at a Glance*, Ministry of Agriculture & Farmers Welfare (annual) | Not yet checked |
| 3 | *Economic Survey of Punjab* (Government of Punjab, annual) | Not yet checked |

Going directly to DES rather than continuing to rely on CEIC (an aggregator)
would remove a data-provenance layer and let 2019-2021 state-level rows be
added, closing the README's already-documented "KNOWN GAP."

### Field-level

| Priority | Source | Status |
|---|---|---|
| 1 | Cost of Cultivation Scheme (CCS) microdata, Directorate of Economics & Statistics, Govt. of India | Real plot-level cost/area/yield for sampled farmers including Punjab rice/wheat — would need a formal data request; not yet attempted |
| 2 | Punjab Agricultural University (PAU), Ludhiana — Krishi Vigyan Kendra, Amritsar | Local farm-level trial/extension records; not yet contacted |
| 3 | Punjab Remote Sensing Centre (PRSC), Ludhiana | Occasional plot/village-level crop-health bulletins; not yet checked |
| 4 | Direct farmer survey, Ajnala tehsil | Genuine primary data; requires fieldwork, not a desk-research source |

**Honest current status: no field-level source is secured for F004/F007.**
Unlike the 3 VDSA villages (which have real plot-level outcomes but are a
different location entirely), Punjab has no existing panel survey covering
it. This tier requires new outreach (CCS request, or a KVK/PAU contact), not
another API pull — it should not be assumed solvable on the same timeline as
the district-tier improvement above.

## 4. If only regional (district/state/national) data is obtained

This has already been this project's situation for all 7 fields since the
start, and the existing handling is the honest template to keep following:

- **Never rename a regional figure as field-level.** `geographic_level`
  states the true resolution; nothing downstream is allowed to imply
  otherwise (`validate_yield_labels.py` flags any `geographic_level=field`
  row for manual confirmation specifically to catch this mistake before it
  happens).
- **State plainly, wherever the result is reported, that the label is
  regional and the input is field-specific.** `RESULTS.md` §1 and the
  README have done this from the start ("Label granularity is the project's
  central limitation") — continue that same sentence for any new field.
- **Treat seasons that fall back to a repeated or nearest-year label as
  non-independent observations for sample-size purposes**, exactly as the
  README already does for F004-F007's pre-2022 seasons. A season with a
  borrowed label adds input diversity, not label variance — do not count it
  toward statistical power.
- **Use the granularity sweep itself as the honest framing**, rather than
  treating a regional label as a stand-in for field-level truth: this
  project's contribution (`RESULTS.md` §5d) is precisely that the *gap*
  between label resolutions is measurable and reportable, which only works
  if every tier's real resolution stays clearly labelled rather than
  blurred.

## 5. Validation

Run before and after adding any new file or row:

```
python -m ingestion.validate_yield_labels
```

Checks: missing values, duplicate `season_start_date` rows, invalid yields
(non-positive or outside a plausible 0.1-15 t/ha range), unit inconsistencies
(a value above 50 t/ha is flagged as an almost-certainly-unconverted
kg/ha or quintal/ha figure), date problems (unparseable, pre-1990, or
future-dated), and crop mismatches (the file's field_id must exist in
`ingestion.config.FIELDS`, and a `crop` column value must match that field's
configured crop). It never modifies a file — it only reports.

Current status of all 24 existing files: 0 schema errors, 0 missing
required values, 0 duplicates, 0 invalid yields, 0 unit inconsistencies, 0
date problems, 0 crop mismatches. The only flagged gap is `retrieved_date`
being blank on the pre-existing (default/national/state tier) files, left
blank deliberately (`ingestion/add_yield_label_provenance.py`'s docstring)
because their real fetch dates were never logged at the time and should not
be backfilled with a guess.
