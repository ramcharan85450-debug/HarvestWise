"""
Experiment 5, Checkpoint 5 — extraction of the 2004-05 district irrigation
values from the two retrieved DES publications, for data-quality auditing.

This module EXTRACTS AND AUDITS ONLY. It does not merge anything into the
modelling dataset, does not create modelling features, does not align
irrigation years to Kharif years, and does not run any model. Its output is a
raw, provenance-carrying table plus the audit numbers Checkpoint 5 requires.

WHAT IS EXTRACTED, AND FROM WHICH TABLE

  Andhra Pradesh (undivided; supplies both the AP and Telangana study
  districts):
      DES Andhra Pradesh, Season and Crop Report 2004-05 / 1414 Fasli,
      "DETAILED TABLE III-B (Concld.) - AREA IRRIGATED BY DIFFERENT SOURCES
      IN ANDHRA PRADESH BY DISTRICTS 2004-2005 (Area in Hectares)", p.170.
      Columns: Net area irrigated | % of net area irrigated to net area sown |
      Area irrigated more than once | Gross area irrigated | % of gross
      irrigated to total cropped area.

  Tamil Nadu:
      DES Tamil Nadu, Season and Crop Report 2004-05, "TABLE III-B - AREA
      IRRIGATED BY DIFFERENT SOURCES OF IRRIGATION 04-05 (in ha.)", final
      block "AREA IRRIGATED BY ALL SOURCES".
      Columns: Net area irrigated (excl. wells suppl. other sources) | % of
      net area irrigated to net area sown | Area irrigated more than once |
      Gross area of crops irrigated | % of gross area irrigated to gross area
      sown | Irrigation Intensity.

A DEFINITIONAL DIFFERENCE THAT MUST NOT BE GLOSSED
--------------------------------------------------
Tamil Nadu's net-area column is explicitly labelled "(excl. wells suppl.
other sources)". Andhra Pradesh's is not so qualified. The two "net area
irrigated" figures are therefore closely comparable but NOT proven identical
in definition. This is recorded on every row via `net_area_definition` and is
reported in the audit rather than silently treated as equivalent.

Values are read exactly as printed. Nothing is imputed, interpolated,
rescaled, redistributed or unit-converted.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "data" / "raw" / "external" / "district_irrigation" / "source_documents"
MAP_PATH = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_mapping_table.csv"
OUT = ROOT / "data" / "raw" / "external" / "district_irrigation" / "district_irrigation_2004_05_raw.csv"

AP_PDF = DOCS / "AP_Season_crop_2004-05_fasli1414.pdf"
TN_HTM = DOCS / "TN_2004-05_TableIIIB_AreaIrrigatedBySource_hectares.htm"

AP_TABLE = ("DES Andhra Pradesh, Season and Crop Report 2004-05/1414 Fasli, "
            "DETAILED TABLE III-B (Concld.), p.170")
TN_TABLE = ("DES Tamil Nadu, Season and Crop Report 2004-05, TABLE III-B, "
            "block 'AREA IRRIGATED BY ALL SOURCES'")

FIELDS = [
    "source_district_name", "source_state_as_printed", "reporting_year", "fasli",
    "net_irrigated_area_ha", "pct_net_irrigated_to_net_area_sown",
    "area_irrigated_more_than_once_ha", "gross_irrigated_area_ha",
    "pct_gross_irrigated", "irrigation_intensity_reported",
    "unit", "net_area_definition", "source_table", "source_file", "status",
]


def _num(s):
    """Parse a printed number. Returns None rather than guessing on anything
    that is not a clean number - a blank or a stray mark must not become 0."""
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s in ("", "-", "--", "N.A.", "NA"):
        return None
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def extract_ap() -> list[dict]:
    with pdfplumber.open(AP_PDF) as pdf:
        text = pdf.pages[169].extract_text() or ""
    rows = []
    for line in text.split("\n"):
        m = re.match(r"^\s*(\d{1,2})\.\s+([A-Z][A-Z .]+?)\s+(\d[\d.]*)\s+(\d[\d.]*)\s+(\d[\d.]*)\s+(\d[\d.]*)\s+(\d[\d.]*)\s*$", line)
        if not m:
            continue
        _, name, net, pct_net, more_once, gross, pct_gross = m.groups()
        rows.append({
            "source_district_name": " ".join(name.split()),
            "source_state_as_printed": "Andhra Pradesh (undivided)",
            "reporting_year": "2004-05", "fasli": "1414",
            "net_irrigated_area_ha": _num(net),
            "pct_net_irrigated_to_net_area_sown": _num(pct_net),
            "area_irrigated_more_than_once_ha": _num(more_once),
            "gross_irrigated_area_ha": _num(gross),
            "pct_gross_irrigated": _num(pct_gross),
            "irrigation_intensity_reported": None,  # not published in this table
            "unit": "hectares (stated: 'Area in Hectares')",
            "net_area_definition": "Net area irrigated (no exclusion stated in the source)",
            "source_table": AP_TABLE, "source_file": AP_PDF.name, "status": "OBSERVED",
        })
    return rows


def extract_tn() -> list[dict]:
    html = TN_HTM.read_text(encoding="utf-8", errors="replace")
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    start = None
    for i, tr in enumerate(trs):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("\xa0", "").strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if any("AREA IRRIGATED BY ALL SOURCES" in c.upper() for c in cells):
            start = i
            break
    if start is None:
        raise ValueError("Could not locate the 'AREA IRRIGATED BY ALL SOURCES' block.")

    rows = []
    for tr in trs[start:]:
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("&nbsp;", "").replace("\xa0", "").strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if len(cells) < 8 or not re.match(r"^\d{1,2}\.$", cells[0]):
            continue
        name = cells[1]
        vals = cells[2:8]
        rows.append({
            "source_district_name": " ".join(name.split()),
            "source_state_as_printed": "Tamil Nadu",
            "reporting_year": "2004-05", "fasli": "1414",
            "net_irrigated_area_ha": _num(vals[0]),
            "pct_net_irrigated_to_net_area_sown": _num(vals[1]),
            "area_irrigated_more_than_once_ha": _num(vals[2]),
            "gross_irrigated_area_ha": _num(vals[3]),
            "pct_gross_irrigated": _num(vals[4]),
            "irrigation_intensity_reported": _num(vals[5]),
            "unit": "hectares (stated: '(in ha.)')",
            "net_area_definition": "Net area irrigated (excl. wells suppl. other sources)",
            "source_table": TN_TABLE, "source_file": TN_HTM.name, "status": "OBSERVED",
        })
    return rows


def main():
    rows = extract_ap() + extract_tn()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    df = pd.DataFrame(rows)
    print(f"extracted rows: {len(df)} -> {OUT}")
    print(df.groupby("source_state_as_printed").size().to_dict())

    mapping = pd.read_csv(MAP_PATH)
    mapped = mapping[mapping.mapping_type != "UNMAPPABLE"]
    have = set(df["source_district_name"])
    missing = [r.source_district_name for r in mapped.itertuples()
               if r.source_district_name not in have]
    print(f"\nmapped study districts with an extracted value: "
          f"{len(mapped) - len(missing)}/{len(mapped)}")
    print(f"mapped but not extracted: {missing or 'none'}")
    return df


if __name__ == "__main__":
    main()
