# Overlap-year collection — validation report (Experiment 3, Phase 4)

Validated file: `tamil_nadu_overlap/tamil_nadu_overlap_apy_clean.csv` (381 rows)
Produced by: `ingestion/tamil_nadu_overlap_extract.py`
Raw source on disk: `data/raw/external/datagovin/district_yield_rice.csv`

## 1. Publisher and official status

| Field | Value |
|---|---|
| Publisher | Government of India, Ministry of Agriculture and Farmers Welfare |
| Platform | data.gov.in (India's Open Government Data Platform) |
| Resource ID | `35be999b-0208-4354-b557-f6ca9a5355de` |
| Source URL | https://data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de |
| Fetch code | `ingestion/datagovin_fetch.py` (`filters[crop]=Rice`) |
| Retrieval | The national dump was already downloaded by earlier work in this project; Tamil Nadu rows were extracted from it here. |

**This is the same resource, fetched by the same code, that already supplied every Andhra Pradesh and Telangana row in this project.** That is the reason it was chosen over any new source: comparability with the rows these will be contrasted against is the entire scientific purpose, and a different publisher would have reintroduced a source confound while removing a temporal one.

Not used: Kaggle, Wikipedia, blogs, scraped datasets, or any synthetic generation.

## 2. Crop, geography, year, season identity

| Check | Result |
|---|---|
| Crop | `Rice` for all 381 rows, from the source's own `Crop` field (filtered at fetch time, not inferred). **PASS** |
| State | `Tamil Nadu` for all rows, from the source's own `State_Name`. **PASS** |
| Geographic level | District. 31 distinct districts. No state or national aggregate. **PASS** |
| Year | 2000–2012, from the source's own `Crop_Year`. **PASS** |
| Season | `Kharif` for all 381 rows, from the source's own `Season`. **PASS** |

## 3. Units — not guessed

The source states no unit in its API metadata (`Area` and `Production` are typed only as `numeric`). The unit was therefore **not** guessed here; it inherits the evidence already established for the identical fields of the identical resource in `andhra_pradesh/validation_report.md` §5: GoI DES methodology documentation for this dataset category specifies area in hectares and production in tonnes, and the alternative hypotheses fail a plausibility test (acres would imply ~2.47× higher yields; quintals ~10× lower).

Because these Tamil Nadu rows come from the same columns of the same resource, applying a *different* unit assumption to them than to the AP/Telangana rows would itself be an error. `yield_unit` is recorded as `t/ha`.

## 4. Yield derivation and cross-check

Yield is computed as `production_tonnes / area_ha`. It is **recomputed** in `tamil_nadu_overlap_extract.py` rather than copied, and then checked against the value the fetch code derived independently. The extractor raises and refuses to write if any row disagrees by more than 1e-3. **0 rows disagreed.**

## 5. Duplicate, missing and validity checks

| Check | Result |
|---|---|
| Duplicate `(state, district, crop, season, year)` | 0 |
| Missing values in any column | 0 |
| Non-positive area or production | 0 (excluded at fetch time by `to_yield_rows`) |
| Yield outside the project's 0.1–15.0 t/ha bound (`district_alignment.YIELD_MIN/MAX`) | 0 |
| Key collision with existing Tamil Nadu 2019/2024 rows | 0 — verified in `district_alignment_overlap.py`, which raises rather than let the aligner drop them silently |

## 6. Four extreme values — reported, not removed

Four rows are extreme but fall inside the project's existing validity bounds, so they were **kept**. Removing them would have meant applying a stricter rule to Tamil Nadu than was applied to Andhra Pradesh and Telangana, which would bias exactly the cross-region comparison this data exists to support.

| District | Year | Area (ha) | Production (t) | Yield (t/ha) |
|---|---|---|---|---|
| COIMBATORE | 2008 | 2,573 | 25,437 | **9.886** |
| PERAMBALUR | 2008 | 12,399 | 113,794 | **9.178** |
| RAMANATHAPURAM | 2003 | 121,031 | 20,771 | **0.172** |
| RAMANATHAPURAM | 2007 | 123,771 | 29,879 | **0.241** |

Honest assessment: 9.9 t/ha is at or beyond the realistic ceiling for district-average rice and may indicate a source error in either area or production. The two Ramanathapuram values are consistent with severe drought in a drought-prone district (2003 was a documented drought year in Tamil Nadu) but are extreme regardless. **These are flagged as suspect source values, not corrected, not imputed, and not silently dropped.** Anyone using this file should know they are present. They are 4 rows of 381 (1.05%).

## 7. District-name reconciliation

Five of 31 source district names differ in spelling from the project registry. Each mapping is declared explicitly in `DISTRICT_ALIASES` (no fuzzy matching, which would also "successfully" match genuinely different districts):

| Source name | Registry name | Basis |
|---|---|---|
| KANCHIPURAM | KANCHEEPURAM | Spelling variant |
| SIVAGANGA | SIVAGANGAI | Spelling variant |
| THIRUVARUR | TIRUVARUR | Transliteration variant |
| TIRUCHIRAPPALLI | TIRUCHIRAPALLI | Spelling variant |
| TUTICORIN | THOOTHUKUDI | Official renaming — same district |

After mapping, **0 of 31 districts fail to match the registry.**

## 8. Raw vs processed separation

Raw national dump (`data/raw/external/datagovin/district_yield_rice.csv`) is unmodified. The new clean file lives in its own directory (`official_yield/tamil_nadu_overlap/`), kept **separate** from `official_yield/tamil_nadu/` (the 2019/2024 TN DES records) so the two cohorts never lose their distinct provenance, retrieval dates or source documents.

## 9. Verdict

**PASS.** 381 real, official, district-level Tamil Nadu Kharif rice records for 2000–2012, from an already-validated government source, with units corroborated rather than assumed, 0 duplicates, 0 missing values, and 4 extreme values disclosed rather than removed.
