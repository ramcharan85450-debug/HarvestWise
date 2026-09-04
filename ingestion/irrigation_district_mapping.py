"""
Experiment 5, Checkpoint 4 — district harmonization mapping table.

Produces ONLY a mapping table. It does not read irrigation values, does not
merge anything into the modelling dataset, does not create derived features,
does not align years, and does not compute statistics.

EVERY MAPPING IS DECLARED EXPLICITLY BELOW. No fuzzy matching is used
anywhere: a fuzzy matcher will happily "succeed" on two genuinely different
districts, and the whole point of this table is that a human can audit each
row. Permitted operations are exact spelling normalization, documented
historical-name-to-current-name normalization where identity is unambiguous
and no value is redistributed, and explicit UNMAPPABLE classifications.

SOURCES OF THE NAME LISTS (read from the retrieved documents, not assumed)

  AP / Telangana : "DETAILED TABLE III-B (Concld.) - AREA IRRIGATED BY
                    DIFFERENT SOURCES IN ANDHRA PRADESH BY DISTRICTS
                    2004-2005 (Area in Hectares)", p.170 of the DES Andhra
                    Pradesh Season and Crop Report 2004-05 / 1414 Fasli.
                    23 districts, undivided Andhra Pradesh.

  Tamil Nadu     : "TABLE III-B - AREA IRRIGATED BY DIFFERENT SOURCES OF
                    IRRIGATION 04-05 (in ha.)", DES Tamil Nadu Season and
                    Crop Report 2004-05. 30 districts.

  HarvestWise    : the 32 study districts of the Experiment 4 estimation
                    subset (Kharif 2000-2012).

MAPPING TYPES USED
  EXACT     source name equals the canonical name after case normalization
  RENAMED   documented spelling/transliteration variant of the SAME district;
            no boundary change, no value redistributed
  UNMAPPABLE the district cannot be matched without inventing a value

SPLIT and MERGED are deliberately NOT used to move any value. Where a split
makes a study district absent from the source year, the row is UNMAPPABLE.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_mapping_table.csv"

AP_SOURCE_TABLE = ("DES Andhra Pradesh, Season and Crop Report 2004-05/1414 Fasli, "
                   "DETAILED TABLE III-B (Concld.), p.170")
TN_SOURCE_TABLE = ("DES Tamil Nadu, Season and Crop Report 2004-05, "
                   "TABLE III-B, Area Irrigated by Different Sources of Irrigation 04-05")

# (canonical HarvestWise district, HarvestWise region, source name as printed,
#  source state as printed, source table, mapping type, justification, status)
MAPPINGS: list[tuple] = [
    # ---------------- Tamil Nadu ----------------
    ("COIMBATORE", "Tamil Nadu", "Coimbatore", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name.", "OBSERVED"),
    ("CUDDALORE", "Tamil Nadu", "Cuddalore", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name.", "OBSERVED"),
    ("DHARMAPURI", "Tamil Nadu", "Dharmapuri", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name. Krishnagiri was separated from Dharmapuri in 2004 and the source "
     "lists both districts separately, so the 2004-05 Dharmapuri figure already reflects "
     "the post-separation district.", "OBSERVED"),
    ("DINDIGUL", "Tamil Nadu", "Dindigul", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name.", "OBSERVED"),
    ("ERODE", "Tamil Nadu", "Erode", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name. See boundary caveat: Tiruppur district was formed in 2009 partly "
     "from Erode, so the 2004-05 Erode extent is larger than the post-2009 Erode.",
     "OBSERVED_WITH_BOUNDARY_CAVEAT"),
    ("KANCHEEPURAM", "Tamil Nadu", "Kancheepuram", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name.", "OBSERVED"),
    ("KANNIYAKUMARI", "Tamil Nadu", "Kanyakumari", "Tamil Nadu", TN_SOURCE_TABLE, "RENAMED",
     "Documented transliteration variant of the same district; no boundary change and no "
     "value redistributed.", "OBSERVED"),
    ("KARUR", "Tamil Nadu", "Karur", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name.", "OBSERVED"),
    ("KRISHNAGIRI", "Tamil Nadu", "Krishnagiri", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name. Krishnagiri was created from Dharmapuri in 2004 and appears as its "
     "own district in the 2004-05 source, so no reconstruction is required.", "OBSERVED"),
    ("MADURAI", "Tamil Nadu", "Madurai", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name.", "OBSERVED"),
    ("NAGAPATTINAM", "Tamil Nadu", "Nagapattinam", "Tamil Nadu", TN_SOURCE_TABLE, "EXACT",
     "Identical name.", "OBSERVED"),
    ("ARIYALUR", "Tamil Nadu", "", "Tamil Nadu", TN_SOURCE_TABLE, "UNMAPPABLE",
     "Ariyalur district was constituted in 2007 from Perambalur district and therefore does "
     "not exist in the 2004-05 source. Assigning Perambalur's values would redistribute a "
     "historical value across a boundary change, which is prohibited. No value is assigned, "
     "estimated, split or copied.", "UNMAPPABLE_YEAR_NOT_COVERED"),

    # ---------------- Andhra Pradesh ----------------
    ("ANANTAPUR", "Andhra Pradesh", "ANANTHAPUR", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "RENAMED", "Spelling variant of the same district.", "OBSERVED"),
    ("CHITTOOR", "Andhra Pradesh", "CHITTOOR", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name.", "OBSERVED"),
    ("EAST GODAVARI", "Andhra Pradesh", "EAST GODAVARI", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name.", "OBSERVED"),
    ("GUNTUR", "Andhra Pradesh", "GUNTUR", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name.", "OBSERVED"),
    ("KRISHNA", "Andhra Pradesh", "KRISHNA", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name.", "OBSERVED"),
    ("KURNOOL", "Andhra Pradesh", "KURNOOL", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name.", "OBSERVED"),
    ("PRAKASAM", "Andhra Pradesh", "PRAKASHAM", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "RENAMED", "Spelling variant of the same district.", "OBSERVED"),
    ("SRIKAKULAM", "Andhra Pradesh", "SRIKAKULAM", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name.", "OBSERVED"),
    ("VIZIANAGARAM", "Andhra Pradesh", "VIZIANAGARAM", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name.", "OBSERVED"),
    ("WEST GODAVARI", "Andhra Pradesh", "WEST GODAVARI", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name.", "OBSERVED"),

    # ---------------- Telangana (reported under undivided Andhra Pradesh) ----------------
    # State attribution differs from HarvestWise, district identity does not.
    # Telangana was formed in 2014; in 2004-05 these ten districts existed with
    # the same names and boundaries under Andhra Pradesh. This is a state
    # attribution difference, NOT a boundary change and NOT a redistribution.
    ("ADILABAD", "Telangana", "ADILABAD", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name; reported under undivided AP in 2004-05.", "OBSERVED"),
    ("HYDERABAD", "Telangana", "HYDERABAD", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name; reported under undivided AP in 2004-05.", "OBSERVED"),
    ("KARIMNAGAR", "Telangana", "KARIMNAGAR", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name; reported under undivided AP in 2004-05.", "OBSERVED"),
    ("KHAMMAM", "Telangana", "KHAMMAM", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name; reported under undivided AP in 2004-05.", "OBSERVED"),
    ("MAHBUBNAGAR", "Telangana", "MAHABOOBNAGAR", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "RENAMED", "Spelling variant of the same district; reported under "
     "undivided AP in 2004-05.", "OBSERVED"),
    ("MEDAK", "Telangana", "MEDAK", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name; reported under undivided AP in 2004-05.", "OBSERVED"),
    ("NALGONDA", "Telangana", "NALGONDA", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name; reported under undivided AP in 2004-05.", "OBSERVED"),
    ("NIZAMABAD", "Telangana", "NIZAMABAD", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name; reported under undivided AP in 2004-05.", "OBSERVED"),
    ("RANGAREDDI", "Telangana", "RANGAREDDY", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "RENAMED", "Spelling variant of the same district; reported under "
     "undivided AP in 2004-05.", "OBSERVED"),
    ("WARANGAL", "Telangana", "WARANGAL", "Andhra Pradesh (undivided)",
     AP_SOURCE_TABLE, "EXACT", "Identical name; reported under undivided AP in 2004-05.", "OBSERVED"),
]

FIELDS = ["canonical_district_harvestwise", "harvestwise_region", "source_district_name",
          "source_state_as_printed", "source_table", "mapping_type", "justification",
          "status", "reporting_year", "confidence"]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for (canon, region, src, src_state, table, mtype, why, status) in MAPPINGS:
        rows.append({
            "canonical_district_harvestwise": canon,
            "harvestwise_region": region,
            "source_district_name": src,
            "source_state_as_printed": src_state,
            "source_table": table,
            "mapping_type": mtype,
            "justification": why,
            "status": status,
            "reporting_year": "2004-05 (Fasli 1414)",
            # HIGH only where the identity is unambiguous and nothing is redistributed.
            "confidence": "HIGH" if mtype in ("EXACT", "RENAMED") else "N/A - UNMAPPABLE",
        })

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    counts = Counter(r["mapping_type"] for r in rows)
    print(f"mapping rows: {len(rows)} -> {OUT}")
    for k in ("EXACT", "RENAMED", "SPLIT", "MERGED", "AMBIGUOUS", "UNMAPPABLE"):
        print(f"  {k:11s} {counts.get(k, 0)}")
    by_region = Counter((r["harvestwise_region"], r["mapping_type"] != "UNMAPPABLE") for r in rows)
    print("\nmapped (non-UNMAPPABLE) by region:")
    for region in ("Andhra Pradesh", "Telangana", "Tamil Nadu"):
        ok = by_region.get((region, True), 0)
        bad = by_region.get((region, False), 0)
        print(f"  {region:16s} mapped {ok}  unmappable {bad}")
    print("\nUNMAPPABLE cases:")
    for r in rows:
        if r["mapping_type"] == "UNMAPPABLE":
            print(f"  {r['canonical_district_harvestwise']} ({r['harvestwise_region']}): {r['status']}")


if __name__ == "__main__":
    main()
