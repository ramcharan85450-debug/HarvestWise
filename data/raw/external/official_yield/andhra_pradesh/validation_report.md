# Andhra Pradesh official yield data — validation report

Validated file: `andhra_pradesh_apy_clean.csv` (481 rows), derived from `raw_datagovin_35be999b_andhra_pradesh_rice.csv` (byte-identical to the original fetch — no rows or values altered, only the column set renamed/extended per the requested clean schema).

## 1. Publisher verification

Publisher is the Government of India, Ministry of Agriculture and Farmers Welfare / Department of Agriculture and Farmers Welfare, republished via data.gov.in (India's Open Government Data Platform). Confirmed via the resource's own API metadata (organization field), not assumed from the dataset title alone. **PASS.**

## 2. Geographic level verification

Every row carries a real `district` value from data.gov.in's own `District_Name` field (13 distinct Andhra Pradesh districts present) — not a state or national aggregate mislabeled as district-level. `geographic_level` is set to `"district"` for every row. **PASS.**

## 3. Crop name verification

Every row's `crop` field is `"Rice"`, exactly as returned by the source's own `Crop` field, filtered at fetch time (`filters[crop]=Rice`) rather than inferred. Single distinct value confirmed by direct check. **PASS.**

## 4. Year/season verification

`year` comes directly from the source's `Crop_Year` field; `season` from `Season` (`Kharif`, `Rabi`, or `Whole Year` — all three are genuine values the source itself reports, not invented categories). Range: **1997–2014**. No row's year/season combination is duplicated (checked directly: 0 duplicate `(district, crop, season, year)` combinations). **PASS**, with the coverage-gap limitation stated in section 8 below.

## 5. Unit verification — the one check that needs a precise, honest answer, not a blanket "verified"

**The source's own API response and field metadata do not state a unit anywhere** (confirmed by inspecting the raw API metadata directly — the `Area` and `Production` fields are typed only as `numeric`, with no unit label). This is the same absence of unit metadata found in earlier, unrelated work this session on a different data.gov.in resource (Punjab market arrivals), so it is treated with the same seriousness here rather than assumed away.

Given that, the unit was NOT guessed. It was corroborated by two independent, real checks, both documented precisely so the strength of the evidence is clear rather than overstated:

1. **Independent methodology description.** A web search (not this specific data.gov.in resource, but describing the Government of India DES's published methodology for the same category of dataset — district/season/crop-wise APY statistics for Andhra Pradesh) states explicitly: *"area measured in Hectares, production in Tonnes, and yield in Tonnes per Hectare."* This is independent, real, and specific to this exact data type and state, from the same publishing authority (GoI DES / Ministry of Agriculture).
2. **Order-of-magnitude plausibility check against a real, independently-sourced yield series.** Computing `production / area` on the raw values under the hectares/tonnes assumption gives a yield range of **0.81–5.26 t/ha** across all 481 rows — squarely inside the range of real, independently-documented Indian rice yields (this project's own Economic Survey-derived national series runs 2.3–2.8 t/ha for the same crop in later years; see `data/raw/yield_labels/README.md`). Testing the alternative unit hypotheses this dataset could plausibly use: if `Area` were in acres rather than hectares, the implied yield would be ~2.47× higher (5.2–13 t/ha in places) — implausibly high for rainfed-heavy AP districts in 1997–2014; if `Production` were in quintals rather than tonnes, implied yield would be ~10× lower (0.08–0.53 t/ha) — implausibly low for any real rice harvest. Hectares/tonnes is the only hypothesis of the three that produces a biologically plausible result across the whole dataset.

**Verdict: hectares (area) and tonnes (production) are corroborated by independent, real evidence — not an explicit first-party label from the source file itself, and not a guess.** `yield_unit` is set to `t/ha` for every row on this basis. Anyone building on this file should know the precise nature of this verification (methodology-description + plausibility corroboration) rather than assume it is a label the source stated outright, which it did not.

## 6. Duplicate check

0 duplicate `(state, district, crop, season, year)` combinations across all 481 rows. **PASS.**

## 7. Invalid-value check

- Non-positive area: 0
- Non-positive production: 0
- Missing/null values in any column: 0
- Yield outside a plausible 0.1–15 t/ha range: 0

**PASS** on all four.

## 8. Coverage and known limitations — stated plainly

- **Years: 1997–2014 only.** The task's preferred 2019–2024 window is **not covered** by this source. A real, confirmed-to-exist secondary source (AP's own state DES, `des.ap.gov.in`) was located and is documented in `source_metadata.md`, but its actual downloadable files could not be retrieved by this session's tooling — this is reported as a gap, not filled with an estimate.
- **District name spelling**: the source itself spells one district `VISAKHAPATANAM` (a genuine typo for Visakhapatnam) — preserved exactly as the source reports it, in both the raw and clean files, rather than silently "corrected," so the file matches its real source exactly. Noted here so it isn't mistaken for a different place or a transcription error introduced in this task.
- **13 of Andhra Pradesh's rice-growing districts are present**; independent sourcing (see `source_metadata.md`) describes rice as grown in 22 AP districts state-wide, so this source's district coverage, while real, is a subset — additional districts were not fabricated to complete the set.
- **No records were rejected** under rule 10 (reject unverifiable source/unit info) — every row passed publisher, geographic-level, crop, and (corroborated, not first-party-labeled) unit checks as documented above.

## Summary

| Check | Result |
|---|---|
| Publisher is official government org | PASS |
| Geographic level is genuinely district | PASS |
| Crop name verified | PASS (Rice only) |
| Year/season verified | PASS (1997–2014; 2019–2024 not covered) |
| Units verified (not guessed) | PASS, via methodology corroboration + plausibility check — not a first-party source label |
| Duplicates | 0 |
| Missing values | 0 |
| Invalid (non-positive/out-of-range) values | 0 |
| Records rejected | 0 |
| **Usable records** | **481** |
