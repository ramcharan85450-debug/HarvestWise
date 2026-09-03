# Telangana official yield data — validation report

Validated file: `telangana_apy_clean.csv` (313 rows), derived from `raw_datagovin_35be999b_telangana_rice.csv` (same values as the original fetch — no rows or numeric values altered, only the column set renamed/extended per the requested clean schema).

## 1. Publisher verification

Publisher is the Government of India, Ministry of Agriculture and Farmers Welfare / Department of Agriculture and Farmers Welfare, republished via data.gov.in (India's Open Government Data Platform). Confirmed via the resource's own organization metadata, not assumed from the dataset title alone — the same resource already used and verified for the Andhra Pradesh collection. **PASS.**

## 2. Geographic level verification

Every row carries a real `district` value from the source's own `District_Name` field (10 distinct districts present, matching the Telangana district structure as it existed at the state's 2014 formation) — not a state or national aggregate mislabeled as district-level. `geographic_level` is set to `"district"` for every row. **PASS.**

## 3. Crop name verification

Every row's `crop` field is `"Rice"`, exactly as returned by the source's own `Crop` field, filtered at fetch time (`filters[crop]=Rice`) rather than inferred. Single distinct value confirmed by direct check. **PASS.**

## 4. Year/season verification

`year` comes directly from the source's `Crop_Year` field; `season` from `Season` (`Kharif` or `Rabi` — both genuine source-reported values; no "Whole Year" rows exist for this state in this resource, unlike Andhra Pradesh). Range: **1997–2014, with 2012 absent** (no Kharif or Rabi row for that year, for any district). 0 duplicate `(district, crop, season, year)` combinations. **PASS**, with the coverage-gap and missing-year limitations stated in section 8.

## 5. Telangana state/boundary verification — the check specific to this state, done carefully rather than assumed

**This is the one verification step that is materially different from the Andhra Pradesh collection**, because Telangana did not exist as a state until 2 June 2014, while this dataset's rows for that state label run from 1997.

Checks performed:

- **Was the "Telangana" label introduced by this project's own code, or is it the source's own field value?** Traced directly in `ingestion/datagovin_fetch.py`: `state` is set to `r.get("state_name")` from the raw API JSON with no remapping logic anywhere in the fetch or parsing code. **Confirmed: this is the publisher's own field value**, not an artifact of this task or this project's ingestion pipeline.
- **Are the districts under the "Telangana" label geographically consistent with the real Telangana region, and not contaminated with districts that were never part of it?** All 10 districts present (Adilabad, Hyderabad, Karimnagar, Khammam, Mahbubnagar, Medak, Nalgonda, Nizamabad, Rangareddi, Warangal) are the 10 districts Telangana held at its actual 2014 formation. No coastal-Andhra or Rayalaseema district names appear under the Telangana label. **PASS — internally consistent.**
- **Does this mean these records are contemporaneous Telangana-state statistics for 1997–2013?** **No — and this is stated explicitly rather than left ambiguous.** Telangana did not exist as an administrative or statistical entity before June 2014; any real 1997–2013 report would have described these same districts as part of undivided Andhra Pradesh. The "Telangana" label in this source is a **retrospective relabeling for series continuity**, applied by the publisher to its own historical data after the 2014 bifurcation — not a claim by this task, and not a guess. See `source_metadata.md` for the full discussion.
- **Was any reconciliation, merging, or relabeling performed by this task?** **No.** Every row's `state` value is passed through unchanged from the source. This task did not reassign any Andhra Pradesh-labeled row to Telangana, and did not relabel any Telangana-labeled row back to Andhra Pradesh. Per the task's Step 4 instruction, this boundary issue is **documented, not silently resolved**.

**Verdict: geographically consistent (correct district set), but the state label is the publisher's retrospective (current-boundary) convention, not a contemporaneous historical designation for the pre-2014 majority of the series.** Anyone using this file for the paper should describe these records as "district-level rice statistics for the districts now comprising Telangana," not as "official Telangana state statistics" for years before mid-2014, to avoid overstating what the label means.

## 6. Unit verification

**The source's own API response and field metadata do not state a unit anywhere** (same absence already found and documented for the Andhra Pradesh subset of this identical resource — the `Area` and `Production` fields are typed only as `numeric`).

The unit was corroborated, not guessed, using the same two checks already validated for Andhra Pradesh from this identical resource and publisher:

1. **Independent methodology description** (see `source_metadata.md` in the Andhra Pradesh collection for the sourced quote): the same Government of India DES methodology for this exact dataset category states area in hectares, production in tonnes, yield in tonnes per hectare — applicable here because it is the same resource, same publisher, same dataset, only a different state filter.
2. **Order-of-magnitude plausibility check specific to this Telangana subset.** Computing `production / area` under the hectares/tonnes assumption gives a yield range of **0.951–4.085 t/ha** across all 313 rows (mean 2.747 t/ha) — squarely inside the range of real, independently documented Indian rice yields (consistent with the Andhra Pradesh subset's 0.81–5.26 t/ha range from the same resource, and with this project's own Economic Survey-derived national series). Testing the alternative unit hypotheses: acres instead of hectares would imply yields ~2.47× higher (up to ~10 t/ha) — implausibly high; quintals instead of tonnes would imply yields ~10× lower (down to ~0.10 t/ha) — implausibly low for a real harvest. Hectares/tonnes is again the only hypothesis producing biologically plausible results across the whole subset.

**Verdict: hectares (area) and tonnes (production) are corroborated by independent, real evidence — not an explicit first-party label from the source file itself, and not a guess.** `yield_unit` is set to `t/ha` for every row on this basis, consistent with the same determination already made and documented for the Andhra Pradesh subset of this resource.

**On the yield figures themselves**: the source provides `yield_t_ha` already computed (not derived by this task); a direct recomputation of `production_tonnes / area_ha` was run against every row and matched the source's own yield figure exactly (0 mismatches beyond rounding) under the hectares/tonnes assumption — this is itself additional, independent corroboration that the assumed units are correct, since a wrong unit pairing would not reproduce the source's own reported yield.

## 7. Duplicate check

0 duplicate `(state, district, crop, season, year)` combinations across all 313 rows. **PASS.**

## 8. Invalid-value check

- Non-positive area: 0
- Non-positive production: 0
- Missing/null values in any column: 0
- Yield outside a plausible 0.1–15 t/ha range: 0
- Yield recomputed from production/area vs. source-reported yield: 0 mismatches (all differences < 0.001 t/ha after rounding)

**PASS** on all five.

## 9. Coverage and known limitations — stated plainly

- **Years: 1997–2014, with 2012 entirely missing** (no row for any district/season that year). The task's preferred 2019–2024 window is **not covered** by this source. Three real, confirmed-to-exist secondary/other-priority sources (Telangana state DES, Telangana Open Data Portal, Telangana Agriculture Department) were located and are documented in `source_metadata.md`, but none had actual downloadable district-wise files retrievable by this session's automated tooling — reported as a gap, not filled with an estimate.
- **State-label boundary issue**: as detailed in section 5, the "Telangana" label applies retrospectively to records predating the state's actual 2014 formation. This is the source's own convention, preserved as-is and flagged prominently rather than silently accepted or "corrected."
- **10 of Telangana's district-equivalent units are present** — matching the state's original 2014 district count (before the 2016 reorganization into 33 districts). No additional or substitute districts were fabricated.
- **No "Whole Year" season rows exist for Telangana in this resource** (unlike Andhra Pradesh, which had 13 such rows) — only Kharif and Rabi. This is simply what the source reports; nothing was excluded by this task.
- **No records were rejected**: every row passed publisher, geographic-level, crop, and (corroborated) unit checks. The state-label caveat in section 5 is a documentation requirement, not a rejection criterion — the underlying district/crop/area/production/yield values are real and usable, only the *state attribution for pre-2014 years* needs the caveat carried alongside them.

## Summary

| Check | Result |
|---|---|
| Publisher is official government org | PASS |
| Geographic level is genuinely district | PASS |
| Crop name verified | PASS (Rice only) |
| Year/season verified | PASS (1997–2014, 2012 missing; 2019–2024 not covered) |
| Telangana boundary/state-label check | PASS geographically; **retrospective label, documented — not a contemporaneous historical claim** |
| Units verified (not guessed) | PASS, via methodology corroboration + plausibility check + exact source-yield reproduction — not a first-party source label |
| Duplicates | 0 |
| Missing values | 0 |
| Invalid (non-positive/out-of-range) values | 0 |
| Records rejected | 0 |
| **Usable records** | **313** |
