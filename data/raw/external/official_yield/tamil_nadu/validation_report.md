# Tamil Nadu official yield data — validation report

Validated file: `tamil_nadu_apy_clean.csv` (74 rows: 36 districts for 2019-20 + 38 districts for 2024-25), derived from four official PDFs in `raw/` as documented in `source_metadata.md`.

## 1. Publisher verification

- 2019-20 rows: Tamil Nadu Agriculture Department, via its official TNAGRISNET portal (`tnagrisnet.tn.gov.in`), source priority #2. **PASS.**
- 2024-25 rows: Tamil Nadu Directorate of Economics and Statistics, via the state government's own domain (`tn.gov.in/crop/`), source priority #1 — the single highest-priority source specified by the task. **PASS.**

Both are genuine `.gov.in` state-government domains, not aggregators or third parties.

## 2. Geographic level verification

Every row carries a real district value taken directly from the source's own `District` column (36 districts for 2019-20, 38 for 2024-25 — see §7 for why the counts differ). `geographic_level` is `"district"` for every row, never a state or national figure mislabeled. **PASS.**

## 3. Crop name verification

Every row's `crop` is `"Rice"`. The 2019-20 source's own table title says "RICE"; the 2024-25 source's own tables say "RICE" (production, yield-rate) and "PADDY" (area — the source's own terminology for the same crop, consistent within Table IV-A). Not inferred — read directly from each table's own header. **PASS.**

## 4. Row-level internal consistency check (season components sum to the source's own Total) — 2019-20

For every one of the 37 districts (+ the STATE row) in the 2019-20 table, the three season area values (Kar/Kuruvai/Sornavari, Samba/Thaladi/Pishanam, Navarai/Kodai) were summed and compared against the source's own printed "Total" column — same for Production. **All 37 districts + the STATE row passed with an exact match (0 discrepancy)**, both for Area and for Production. This is strong evidence the transcription is correct district-by-district, not just plausible in aggregate — a transposition error (e.g., swapping two districts' rows) would have been extremely unlikely to still pass 37 independent exact-sum checks. Full detail in `raw/parsed_extraction_log.csv`.

One row (Chennai) has area but the source itself prints "-" (dash) for all three production and all four productivity cells — read as **genuinely missing**, not zero, and excluded from the clean CSV (see §8).

## 5. Row-level internal consistency check (area × yield-rate reproduces production) — 2024-25

The 2024-25 figures come from **three separate PDF tables** (area, production, yield-rate) that had to be joined by district name. As an independent check that the join was performed correctly and no district's row was misaligned, `area_ha × yield_kg_per_ha / 1000` was computed for every district and compared against that same district's independently-extracted production figure from the production table.

**Result: all 38 districts matched within rounding** (the largest deviation was 77 tonnes on a district reporting ~690,000 tonnes — 0.01% — fully explained by the yield-rate table itself being pre-rounded to the nearest whole kg/ha before publication). See `raw/parsed_extraction_log_2024.csv` for the full per-district comparison. Additionally, the sum of the 38 district production totals (7,093,820 t) matches the source's own STATE row (7,093,817 t) to within 3 tonnes out of 7.09 million — 0.00004%, i.e. effectively exact and consistent with minor independent rounding in the source's own three tables rather than a parsing defect.

**PASS** on both consistency checks.

## 6. Unit verification

**All three units are EXPLICIT, printed directly on the source tables themselves — not corroborated or inferred**, unlike the Andhra Pradesh and Telangana collections (data.gov.in did not print units there):

| Unit | Where explicitly stated |
|---|---|
| Area | `AREA (in Ha.)` — 2019-20 table header; `( in ha.)` — 2024-25 Table IV-A subtitle |
| Production | `PRODUCTION (in Tonnes)` — 2019-20 table header; `( in Tonnes)` — 2024-25 Table V-B subtitle |
| Yield/Productivity | `PRODUCTIVITY (Kg/ Ha)` — 2019-20 table header; `(in kg / ha)` — 2024-25 Table V-A subtitle |

`final_yield_t_ha` is computed from the source's own explicit `kg/ha` figure via `÷ 1000` (a unit conversion, not a re-derivation — the source already provides the official yield rate; this task did not compute yield from area/production, it converted the source's own yield figure to the requested `t/ha` unit). Every conversion is identical and mechanical: `t/ha = (kg/ha reported by source) / 1000`.

**Marked: EXPLICIT.** **PASS.**

## 7. STEP 8 — District boundary check (Tamil Nadu-specific, done carefully)

Tamil Nadu created several new districts by splitting existing ones in recent years, including in the exact window between this dataset's two years:

- **Mayiladuthurai** district was carved out of **Nagapattinam** district in late 2019/2020. This is directly visible in the data: Nagapattinam's total rice area falls from **169,222 ha (2019-20)** to **67,999 ha (2024-25)**, while a new district, **Mayiladuthurai**, appears in the 2024-25 table with **108,130 ha** — a combined 2024-25 figure (176,129 ha) in the same range as the pre-split 2019-20 Nagapattinam figure, which is exactly the signature of a district split, not a genuine agricultural decline. **The 2019-20 "Nagapattinam" row and the 2024-25 "Nagapattinam" row do NOT represent the same administrative geography and must not be compared as a time series without accounting for this.**
- The 2019-20 table already reflects three other splits that happened earlier in 2019 (Kallakurichi from Villupuram/Salem, Ranipet and Tirupathur from Vellore) — both years' district lists include these three, so they do not create a boundary mismatch **between these two specific years**, only relative to any pre-2019 data (such as the 1997–2013 GoI DES series used for Andhra Pradesh/Telangana, which is explicitly not used here).
- **No district was merged, renamed, or reconciled by this task.** Both years' district names are preserved exactly as each source reports them (`THIRUVALLUR`/`TIRUCHIRAPALLI` spelling variants between the two sources are preserved as-is per district per year, not silently normalized to one canonical spelling — see §9).
- Per the task's Step 8 instruction, this is flagged, not silently resolved: **any use of this file that compares Nagapattinam or Mayiladuthurai across 2019 and 2024 must account for the 2019/2020 boundary change, and any use that treats "38 districts" as a stable panel across both years is incorrect — the district set genuinely differs by one district between the two years.**

## 8. Missing-value / invalid-value check

- **Chennai, 2019-20: excluded.** Source shows real area (119 ha) but dashes (no data) for all production and productivity cells. Rather than treat "-" as 0 (which would fabricate a false zero-production record) or guess a plausible value, this row was **rejected** and is not in the clean CSV. This is the only rejected record.
- Duplicate `(district, crop, season, year)` combinations: **0**.
- Missing state/district/crop/year values: **0** (checked directly on the 74-row clean file).
- Negative area, negative production, negative yield: **0** of each.
- Zero-area records with nonzero production: **0**.
- Yield outside a plausible 0.1–15 t/ha range: **0** (observed range: 1.966–5.271 t/ha, fully plausible for Indian district-level rice).
- District naming inconsistencies: `district` is stored as reported by each source, upper-cased for consistency with the Andhra Pradesh/Telangana files in this project; the two sources spell a few districts slightly differently across years (e.g. "Tiruchirapalli" vs "Tiruchirappalli", "Kanniyakumari" vs "Kanyakumari") — preserved per-source rather than force-normalized, since silently merging spelling variants risks conflating two different sources' conventions. Anyone joining across years by district name should account for these variants.

**PASS** on all numeric integrity checks; 1 record correctly rejected for missing data rather than fabricated.

## 9. Summary

| Check | Result |
|---|---|
| Publisher is official TN state government | PASS (priority #1 and #2 sources both used) |
| Geographic level is genuinely district | PASS |
| Crop verified | PASS (Rice/Paddy only) |
| Row-level internal consistency (season sums = source Total) | PASS — 37/37 districts, 2019-20 |
| Row-level internal consistency (area × yield ≈ production) | PASS — 38/38 districts, 2024-25, within 0.01% |
| Units | **EXPLICIT** for all three (area, production, yield) — a stronger evidentiary basis than the corroborated units used for Andhra Pradesh/Telangana |
| District boundary check | Mayiladuthurai/Nagapattinam split documented — **flagged, not silently reconciled** |
| Duplicates | 0 |
| Missing values | 0 in the clean file (1 record rejected before inclusion, see §8) |
| Invalid (non-positive/out-of-range) values | 0 |
| **Total records considered** | 75 (37 districts × 2019-20, minus nothing yet, + 38 districts × 2024-25) |
| **Records rejected** | 1 (Chennai 2019-20, missing production/yield) |
| **Usable records** | **74** |
