"""
Experiment 5, Checkpoint 5 — data quality audit of the extracted 2004-05
district irrigation values.

Audit only. Nothing is merged into the modelling dataset, no modelling feature
is created, no year alignment is performed, no model is run.

Writes experiments/EXPERIMENT_5_IRRIGATION_DATA_AUDIT.md and returns PASS/FAIL.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RAW = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_irrigation_2004_05_raw.csv"
MAP = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_mapping_table.csv"
OUT = ROOT / "experiments" / "EXPERIMENT_5_IRRIGATION_DATA_AUDIT.md"

# State totals published by the SOURCES THEMSELVES, used as independent
# internal cross-checks of the district tables. Not used as data.
AP_STATE_NET_2004_05 = 3_880_590   # AP Summary Table B1, "TOTAL NET AREA IRRIGATED", 2004-05
TN_STATE_NET_2004_05 = 2_637_198   # TN Season & Crop Report 2004-05, section 3.2 narrative


def main():
    df = pd.read_csv(RAW)
    mapping = pd.read_csv(MAP)
    mapped = mapping[mapping.mapping_type != "UNMAPPABLE"]
    checks = []

    # ---- 1. duplicates ----
    dup = df.duplicated(["source_district_name", "source_state_as_printed", "reporting_year"]).sum()
    checks.append(("Duplicate district-year records", dup == 0,
                   f"{int(dup)} duplicate (district, state, year) keys across {len(df)} extracted rows."))

    # ---- 2. units ----
    units = sorted(df["unit"].unique())
    unit_ok = all("hectare" in u.lower() or "ha." in u.lower() for u in units)
    checks.append(("Units stated explicitly by each source and mutually compatible", unit_ok,
                   "Units are printed in the table headers, not inferred: " + " | ".join(units)))

    # ---- 3. impossible values ----
    bad = []
    for r in df.itertuples():
        if r.net_irrigated_area_ha is not None and r.net_irrigated_area_ha < 0:
            bad.append((r.source_district_name, "negative net area"))
        if r.gross_irrigated_area_ha is not None and r.gross_irrigated_area_ha < 0:
            bad.append((r.source_district_name, "negative gross area"))
        p = r.pct_net_irrigated_to_net_area_sown
        if p is not None and not (0 <= p <= 100):
            bad.append((r.source_district_name, f"pct out of range: {p}"))
    checks.append(("No impossible values (negative areas, percentages outside 0-100)", not bad,
                   f"{len(bad)} impossible value(s) found. {bad[:5] if bad else ''}"))

    # ---- 4. net/gross consistency ----
    sub = df.dropna(subset=["net_irrigated_area_ha", "gross_irrigated_area_ha"])
    viol_ge = sub[sub.gross_irrigated_area_ha < sub.net_irrigated_area_ha]
    ident = sub.dropna(subset=["area_irrigated_more_than_once_ha"]).copy()
    ident["expected_gross"] = ident.net_irrigated_area_ha + ident.area_irrigated_more_than_once_ha
    ident["abs_err"] = (ident.expected_gross - ident.gross_irrigated_area_ha).abs()
    ident["rel_err"] = ident.abs_err / ident.gross_irrigated_area_ha.replace(0, pd.NA)
    exact = int((ident.abs_err <= 1).sum())
    within_1pct = int((ident.rel_err.fillna(1) <= 0.01).sum())
    checks.append(("Gross area >= net area for every district", len(viol_ge) == 0,
                   f"{len(viol_ge)} violation(s) of gross >= net across {len(sub)} rows."))
    checks.append((
        "Accounting identity gross = net + area irrigated more than once",
        exact >= int(0.95 * len(ident)),
        f"Holds exactly (|error| <= 1 ha) for {exact}/{len(ident)} rows; within 1% for "
        f"{within_1pct}/{len(ident)}. This identity is a property the sources should satisfy "
        "internally, so it is a real test of extraction fidelity as well as of the data.",
    ))

    # ---- 5. year alignment ----
    yrs = sorted(df["reporting_year"].unique())
    fas = sorted(df["fasli"].astype(str).unique())
    checks.append(("All records share one reporting year and fasli", len(yrs) == 1 and len(fas) == 1,
                   f"reporting_year={yrs}, fasli={fas}. Both sources are Fasli 1414 = 2004-05. "
                   "NOTE: no mapping of this fasli year onto the HarvestWise Kharif window has "
                   "been performed - that remains an open Checkpoint 7 decision."))

    # ---- 6. district alignment ----
    have = set(df["source_district_name"])
    miss = [r.source_district_name for r in mapped.itertuples() if r.source_district_name not in have]
    checks.append(("Every mapped study district has an extracted value", not miss,
                   f"{len(mapped) - len(miss)}/{len(mapped)} mapped study districts have a value. "
                   f"Missing: {miss or 'none'}. Ariyalur remains UNMAPPABLE_YEAR_NOT_COVERED by "
                   "approved ruling and is excluded rather than filled."))

    # ---- 7. missingness ----
    study_src = set(mapped["source_district_name"])
    study = df[df.source_district_name.isin(study_src)]
    miss_tbl = {c: int(study[c].isna().sum()) for c in
                ["net_irrigated_area_ha", "gross_irrigated_area_ha",
                 "pct_net_irrigated_to_net_area_sown", "area_irrigated_more_than_once_ha"]}
    checks.append(("No missing values in the primary irrigation variables for study districts",
                   all(v == 0 for k, v in miss_tbl.items()
                       if k in ("net_irrigated_area_ha", "gross_irrigated_area_ha")),
                   f"Missing counts across the {len(study)} study-district rows: {miss_tbl}"))

    # ---- 8. source agreement: district sums vs each source's own state total ----
    ap = df[df.source_state_as_printed.str.startswith("Andhra")]
    tn = df[df.source_state_as_printed == "Tamil Nadu"]
    ap_sum, tn_sum = ap.net_irrigated_area_ha.sum(), tn.net_irrigated_area_ha.sum()
    ap_dev = abs(ap_sum - AP_STATE_NET_2004_05) / AP_STATE_NET_2004_05
    tn_dev = abs(tn_sum - TN_STATE_NET_2004_05) / TN_STATE_NET_2004_05
    checks.append((
        "District sums reconcile with each source's own published state total",
        ap_dev < 0.02 and tn_dev < 0.05,
        f"Andhra Pradesh: district sum {ap_sum:,.0f} ha vs published state total "
        f"{AP_STATE_NET_2004_05:,} ha ({ap_dev:.2%} deviation). "
        f"Tamil Nadu: district sum {tn_sum:,.0f} ha vs published state total "
        f"{TN_STATE_NET_2004_05:,} ha ({tn_dev:.2%} deviation). "
        "These totals come from the SAME publications (AP Summary Table B1; TN section 3.2) "
        "and are used only as internal consistency checks, never as data.",
    ))

    # ---- 9. definitional comparability ----
    defs = sorted(df["net_area_definition"].unique())
    checks.append((
        "Net-area definitions recorded and compared across sources",
        False,  # deliberately reported as a WARNING, not a pass
        "The two sources do NOT use provably identical net-area definitions. Tamil Nadu's column "
        "is labelled 'Net area irrigated (excl. wells suppl. other sources)'; Andhra Pradesh's "
        "carries no stated exclusion. Definitions found: " + " | ".join(defs) +
        ". This is recorded on every row and is a genuine comparability limitation, not an "
        "extraction error. It is raised here rather than resolved silently.",
    ))

    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_crit = len(checks) - 1  # check 9 is a recorded warning, not a gate
    crit_pass = sum(1 for (t, ok, _) in checks if ok and not t.startswith("Net-area definitions"))
    verdict = "PASS" if crit_pass == n_crit else "FAIL"

    lines = [
        "# Experiment 5 — irrigation data quality audit (Checkpoint 5)", "",
        f"Generated by `experiments/run_experiment5_audit.py` on "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.", "",
        "Audit only. Nothing was merged into the modelling dataset, no modelling feature was "
        "created, no year alignment was performed, no model was run.", "",
        f"**Overall: {verdict} — {crit_pass} of {n_crit} gating checks passed, "
        "plus 1 recorded comparability warning (check 9).**", "",
        "## Checks", "",
    ]
    for i, (t, ok, ev) in enumerate(checks, 1):
        mark = "PASS" if ok else ("WARNING" if t.startswith("Net-area definitions") else "FAIL")
        lines += [f"### {i}. {t} — {mark}", "", ev, ""]

    lines += [
        "## Usable sample", "",
        f"- Districts extracted: **{len(df)}** ({len(ap)} undivided Andhra Pradesh, {len(tn)} Tamil Nadu)",
        f"- Study districts with an observed 2004-05 value: **{len(mapped) - len(miss)} of 32**",
        "- Excluded: **Ariyalur** (`UNMAPPABLE_YEAR_NOT_COVERED`; district created 2007)",
        "- Reporting year: **2004-05, Fasli 1414**, identical in both sources",
        "- Unit: **hectares**, stated explicitly in both table headers", "",
        "## Exclusions", "",
        "| District | Reason | Rows affected in the Experiment 4 matched subset |",
        "|---|---|---|",
        "| Ariyalur (Tamil Nadu) | Constituted 2007 from Perambalur; absent from the 2004-05 "
        "source. No value assigned, split, estimated or copied. | 4 of 382 |", "",
        "## Limitations carried forward", "",
        "1. **One observation year.** Irrigation is available for 2004-05 only, so it is static "
        "per district across the 2000-2012 panel — the location-fingerprint hazard already "
        "flagged in the implementation plan.",
        "2. **Net-area definitions are not provably identical** (check 9).",
        "3. **Source-composition categories are not comparable** between the two DES taxonomies; "
        "only the net/gross totals are.",
        "4. **Fasli month span still unverified**, and no Kharif alignment has been performed.",
        "5. **Tiruppur boundary change (2009)** affects Coimbatore and Erode extents relative to "
        "the 2004-05 figures.", "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"AUDIT: {verdict} ({crit_pass}/{n_crit} gating checks)")
    for i, (t, ok, _) in enumerate(checks, 1):
        mark = "PASS" if ok else ("WARN" if t.startswith("Net-area definitions") else "FAIL")
        print(f"  {i}. [{mark}] {t}")
    print(f"\nAP district sum {ap_sum:,.0f} vs state {AP_STATE_NET_2004_05:,} ({ap_dev:.2%})")
    print(f"TN district sum {tn_sum:,.0f} vs state {TN_STATE_NET_2004_05:,} ({tn_dev:.2%})")
    print(f"identity gross=net+more_once exact: {exact}/{len(ident)}")
    print(f"wrote -> {OUT}")
    return verdict


if __name__ == "__main__":
    main()
