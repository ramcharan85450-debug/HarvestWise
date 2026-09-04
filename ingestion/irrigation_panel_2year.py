"""
Experiment 6, Checkpoint 4 — two-year district irrigation panel.

Builds ONLY the panel file. No merging into the modelling dataset, no feature
engineering beyond the approved primary variable, no interpolation, no
estimation, no state averages, no redistribution, no modelling.

APPROVED SCOPE
    28 districts x 2 years (2004-05 Fasli 1414, 2011-12 Fasli 1421) = 56 rows.

SOURCES (all previously retrieved and hashed; see EXPERIMENT_5_IRRIGATION_PROVENANCE.md)
    AP 2004-05  DES Andhra Pradesh, Season and Crop Report 2004-05/1414 Fasli,
                DETAILED TABLE III-B (Concld.), p.170. Unit: hectares (stated).
                Publishes net, % net to net area sown, more-than-once, gross.
    AP 2011-12  DES Andhra Pradesh, Districts at a Glance 2012.
                p.22 net area irrigated components (Canals/Tanks/Wells),
                p.23 area irrigated more than once, gross, intensity,
                p.17 net area sown. Unit: '000 Hect. (stated).
                NET IS NOT PUBLISHED and is recovered ONLY as
                    net = gross - area_irrigated_more_than_once
                which is validated against the separately published intensity.
    TN 2004-05  DES Tamil Nadu, Season and Crop Report 2004-05, TABLE III-B,
                block "AREA IRRIGATED BY ALL SOURCES". Unit: hectares (stated).
    TN 2011-12  DES Tamil Nadu, Season and Crop Report 2011-12 (Fasli 1421),
                TABLE III-B "TOTAL AREA IRRIGATED", p.104. Unit: hectares.
                OCR'd scan -> every row must pass identity validation.

ACCEPTANCE RULE (applied to every district-year, no exceptions)
    A row is accepted only if the source's own published quantities are
    internally consistent:
        (i)  gross - more_than_once == net      (exact, tolerance 1 unit)
        (ii) gross / net == published intensity (where intensity is published)
    A row failing either check is REJECTED and reported, never repaired.

NET-AREA DEFINITION (verified at Checkpoint 3, not assumed)
    Both Tamil Nadu years use: net = sum(all sources) - supplementary wells,
    with OTHER SOURCES INCLUDED. Verified arithmetically on the sources' own
    component tables: 2004-05 29/29 districts, 2011-12 16/16 fully-parsed
    districts (5 discriminating cases each way). The differing header wording
    does not reflect a differing definition.

UNIT CONVERSION (the only conversion performed anywhere)
    AP 2011-12 is published in '000 Hect. Converted to hectares by x1000.
    Recorded per row in `unit_conversion_applied`. No other source is
    converted; TN and AP 2004-05 are already in hectares as printed.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOCS = ROOT / "data" / "raw" / "external" / "district_irrigation" / "source_documents"
OUT = ROOT / "data" / "raw" / "external" / "district_irrigation" / "irrigation_panel_2year.csv"
REPORT = ROOT / "data" / "raw" / "external" / "district_irrigation" / "irrigation_panel_2year_validation.json"

AP_2004 = DOCS / "AP_Season_crop_2004-05_fasli1414.pdf"
AP_2011 = DOCS / "AP_Districts_at_a_Glance_2012.pdf"
TN_2004 = DOCS / "TN_2004-05_TableIIIB_AreaIrrigatedBySource_hectares.htm"
TN_2011 = DOCS / "TN_Season_crop_2011-12.pdf"

# ---------------------------------------------------------------- panel scope
# 20 AP/Telangana study districts, canonical -> (2004-05 name, 2011-12 name)
AP_TG = {
    "SRIKAKULAM": ("SRIKAKULAM", "Srikakulam"),
    "VIZIANAGARAM": ("VIZIANAGARAM", "Vizianagaram"),
    "EAST GODAVARI": ("EAST GODAVARI", "East Godavari"),
    "WEST GODAVARI": ("WEST GODAVARI", "West Godavari"),
    "KRISHNA": ("KRISHNA", "Krishna"),
    "GUNTUR": ("GUNTUR", "Guntur"),
    "PRAKASAM": ("PRAKASHAM", "Prakasam"),
    "CHITTOOR": ("CHITTOOR", "Chittoor"),
    "ANANTAPUR": ("ANANTHAPUR", "Anantapur"),
    "KURNOOL": ("KURNOOL", "Kurnool"),
    "MAHBUBNAGAR": ("MAHABOOBNAGAR", "Mahbubnagar"),
    "RANGAREDDI": ("RANGAREDDY", "Ranga Reddy"),
    "HYDERABAD": ("HYDERABAD", "Hyderabad"),
    "MEDAK": ("MEDAK", "Medak"),
    "NIZAMABAD": ("NIZAMABAD", "Nizamabad"),
    "ADILABAD": ("ADILABAD", "Adilabad"),
    "KARIMNAGAR": ("KARIMNAGAR", "Karimnagar"),
    "WARANGAL": ("WARANGAL", "Warangal"),
    "KHAMMAM": ("KHAMMAM", "Khammam"),
    "NALGONDA": ("NALGONDA", "Nalgonda"),
}
AP_REGION = {d: ("Telangana" if d in {
    "MAHBUBNAGAR", "RANGAREDDI", "HYDERABAD", "MEDAK", "NIZAMABAD",
    "ADILABAD", "KARIMNAGAR", "WARANGAL", "KHAMMAM", "NALGONDA"} else "Andhra Pradesh")
    for d in AP_TG}

# 8 Tamil Nadu study districts with clean two-year comparability
TN = {
    "KANCHEEPURAM": ("Kancheepuram", "Kancheepuram"),
    "CUDDALORE": ("Cuddalore", "Cuddalore"),
    "DHARMAPURI": ("Dharmapuri", "Dharmapuri"),
    "KRISHNAGIRI": ("Krishnagiri", "Krishnagiri"),
    "KARUR": ("Karur", "Karur"),
    "NAGAPATTINAM": ("Nagapattinam", "Nagapattinam"),
    "MADURAI": ("Madurai", "Madurai"),
    "DINDIGUL": ("Dindigul", "Dindigul"),
}

EXCLUSIONS = {
    "KANNIYAKUMARI": "DATA_NOT_AVAILABLE - absent from every block of TN 2011-12 Table III-B "
                     "(all seven blocks terminate at '30. The Nilgiris'); present elsewhere in "
                     "the report, so not an OCR failure. No value assigned.",
    "ARIYALUR": "SINGLE_YEAR_ONLY - district constituted 2007 from Perambalur; absent from the "
                "2004-05 source. Perambalur values not redistributed.",
    "COIMBATORE": "BOUNDARY_NOT_COMPARABLE - Thiruppur district formed 2009 from parts of "
                  "Coimbatore and Erode; the 2004-05 and 2011-12 extents are different "
                  "territory. Thiruppur values NOT redistributed back.",
    "ERODE": "BOUNDARY_NOT_COMPARABLE - see Coimbatore. Thiruppur values NOT redistributed back.",
}

FIELDS = [
    "canonical_district", "region", "year", "fasli",
    "net_irrigated_area_ha", "gross_irrigated_area_ha", "area_irrigated_more_than_once_ha",
    "net_area_sown_ha", "pct_net_irrigated_to_net_area_sown",
    "irrigation_intensity_reported",
    "net_source", "pct_source", "unit_as_published", "unit_conversion_applied",
    "identity_gross_minus_more_equals_net", "identity_intensity_check",
    "source_district_name", "source_publication", "row_status",
]


def _i(x):
    x = (x or "").replace(",", "").replace("'", "").strip()
    return int(x) if re.fullmatch(r"\d+", x) else None


# ---------------------------------------------------------------- extractors
def ap_2004():
    with pdfplumber.open(AP_2004) as pdf:
        t = pdf.pages[169].extract_text() or ""
    out = {}
    for m in re.finditer(r"^\s*(\d{1,2})\.\s+([A-Z][A-Z .]+?)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s*$",
                         t, re.M):
        _, name, net, pct_net, more, gross, _pg = m.groups()
        out[" ".join(name.split())] = {
            "net": int(net), "gross": int(gross), "more": int(more),
            "pct": float(pct_net), "intensity": None, "sown": None,
        }
    return out


def ap_2011():
    with pdfplumber.open(AP_2011) as pdf:
        p17 = pdf.pages[16].extract_text() or ""
        p23 = pdf.pages[22].extract_text() or ""
    irr = {}
    for m in re.finditer(r"(\d{1,2})\.\s+([A-Za-z][A-Za-z .]+?)\s+(\d+)\s+(\d+)\s+(\d+\.\d{2})", p23):
        _, name, more, gross, inten = m.groups()
        irr[" ".join(name.split())] = {"more": int(more), "gross": int(gross),
                                       "intensity": float(inten)}
    # p17 carries two interleaved tables; the 3-number series is
    # (current fallows, NET AREA SOWN, fishponds); the 2-number series is
    # (gross area sown, cropping intensity).
    sown, gross_sown = {}, {}
    for m in re.finditer(r"(\d{1,2})\.\s+([A-Za-z][A-Za-z .]+?)\s+(\d+)\s+(\d+)\s+(-|\d+)\s*$", p17, re.M):
        _, name, _fallow, ns, _fp = m.groups()
        sown[" ".join(name.split())] = int(ns)
    for m in re.finditer(r"(\d{1,2})\.\s+([A-Za-z][A-Za-z .]+?)\s+(\d+)\s+(\d+\.\d{2})\s*$", p17, re.M):
        _, name, gs, _ci = m.groups()
        gross_sown[" ".join(name.split())] = int(gs)
    for k, v in irr.items():
        v["sown"] = sown.get(k)
        v["gross_sown"] = gross_sown.get(k)
    return irr


def tn_2004():
    html = TN_2004.read_text(encoding="utf-8", errors="replace")
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    start = next(i for i, tr in enumerate(trs) if "AREA IRRIGATED BY ALL SOURCES" in tr.upper())
    out = {}
    for tr in trs[start:]:
        cs = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("&nbsp;", "").strip()
              for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if len(cs) < 8 or not re.match(r"^\d{1,2}\.$", cs[0]):
            continue
        # net, %net-to-net-sown, more-than-once, gross, %gross, intensity
        out[cs[1].strip()] = {"net": _i(cs[2]), "pct": float(cs[3]), "more": _i(cs[4]),
                              "gross": _i(cs[5]), "intensity": float(cs[7]), "sown": None}
    return out


def tn_2011():
    with pdfplumber.open(TN_2011) as pdf:
        t = pdf.pages[103].extract_text() or ""
    out = {}
    # gross, %gross, net, %net-to-net-sown, more-than-once, intensity
    for m in re.finditer(r"(\d{1,2})\.\s*([A-Za-z][A-Za-z .]+?)\s+(\d[\d,]*)'?\s+(\d+\.\d+)\s+"
                         r"(\d[\d,]*)\s+(\d+\.\d+)\s+(\d[\d,]*)\s+(\d+\.\d+)", t):
        _, name, gross, _pg, net, pct, more, inten = m.groups()
        out[" ".join(name.split())] = {"net": _i(net), "gross": _i(gross), "more": _i(more),
                                       "pct": float(pct), "intensity": float(inten), "sown": None}
    return out


# ---------------------------------------------------------------- panel build
def build():
    src = {"AP2004": ap_2004(), "AP2011": ap_2011(),
           "TN2004": tn_2004(), "TN2011": tn_2011()}
    rows, rejects = [], []

    def add(canon, region, year, fasli, rec, name, pub, scale, net_src, pct_src, sown_scaled):
        if rec is None:
            rejects.append({"district": canon, "year": year, "reason": "district not found in source"})
            return
        gross, more = rec.get("gross"), rec.get("more")
        net = rec.get("net")
        derived = False
        if net is None and gross is not None and more is not None:
            net = gross - more
            derived = True
        if net is None or gross is None or more is None:
            rejects.append({"district": canon, "year": year, "reason": "missing published quantity"})
            return

        id1 = (gross - more) == net
        inten = rec.get("intensity")
        if inten is not None and net > 0:
            id2 = abs(gross / net - inten) <= 0.015
        elif inten is not None and net == 0:
            id2 = inten == 0
        else:
            id2 = None

        if not id1 or id2 is False:
            rejects.append({"district": canon, "year": year,
                            "reason": f"identity failed (gross-more==net: {id1}, intensity: {id2})"})
            return

        pct = rec.get("pct")
        sown = rec.get("sown")
        if pct is None and sown not in (None, 0):
            pct = round(net / sown * 100, 2)
        rows.append({
            "canonical_district": canon, "region": region, "year": year, "fasli": fasli,
            "net_irrigated_area_ha": net * scale,
            "gross_irrigated_area_ha": gross * scale,
            "area_irrigated_more_than_once_ha": more * scale,
            "net_area_sown_ha": (sown * sown_scaled) if sown is not None else None,
            "pct_net_irrigated_to_net_area_sown": pct,
            "irrigation_intensity_reported": inten,
            "net_source": net_src, "pct_source": pct_src,
            "unit_as_published": "'000 Hect." if scale != 1 else "hectares",
            "unit_conversion_applied": f"x{scale} ('000 Hect. -> hectares)" if scale != 1 else "none",
            "identity_gross_minus_more_equals_net": id1,
            "identity_intensity_check": id2,
            "source_district_name": name, "source_publication": pub, "row_status": "ACCEPTED",
        })

    for canon, (n04, n11) in AP_TG.items():
        reg = AP_REGION[canon]
        add(canon, reg, "2004-05", "1414", src["AP2004"].get(n04), n04,
            "DES AP, Season and Crop Report 2004-05, Table III-B (Concld.), p.170",
            1, "published", "published", 1)
        add(canon, reg, "2011-12", "1421", src["AP2011"].get(n11), n11,
            "DES AP, Districts at a Glance 2012, pp.17/22/23",
            1000, "derived: gross - area_irrigated_more_than_once", "computed: net/net_area_sown", 1000)

    for canon, (n04, n11) in TN.items():
        add(canon, "Tamil Nadu", "2004-05", "1414", src["TN2004"].get(n04), n04,
            "DES TN, Season and Crop Report 2004-05, Table III-B, All Sources",
            1, "published", "published", 1)
        add(canon, "Tamil Nadu", "2011-12", "1421", src["TN2011"].get(n11), n11,
            "DES TN, Season and Crop Report 2011-12 (Fasli 1421), Table III-B, p.104",
            1, "published", "published", 1)

    return rows, rejects


def main():
    rows, rejects = build()
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    by = {}
    for r in rows:
        by.setdefault((r["region"], r["year"]), 0)
        by[(r["region"], r["year"])] += 1
    report = {
        "expected_rows": 56, "accepted_rows": len(rows), "rejected_rows": len(rejects),
        "rejects": rejects,
        "coverage": {f"{k[0]} | {k[1]}": v for k, v in sorted(by.items())},
        "identity_gross_minus_more_equals_net_pass": sum(
            1 for r in rows if r["identity_gross_minus_more_equals_net"]),
        "identity_intensity_pass": sum(1 for r in rows if r["identity_intensity_check"] is True),
        "identity_intensity_not_applicable": sum(
            1 for r in rows if r["identity_intensity_check"] is None),
        "excluded_districts": EXCLUSIONS,
        "missing_pct_variable": sum(
            1 for r in rows if r["pct_net_irrigated_to_net_area_sown"] is None),
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"accepted {len(rows)}/56  rejected {len(rejects)}")
    for k, v in sorted(by.items()):
        print(f"  {k[0]:16s} {k[1]}  n={v}")
    if rejects:
        print("REJECTS:")
        for r in rejects:
            print("  ", r)
    print(f"\nidentity gross-more==net : {report['identity_gross_minus_more_equals_net_pass']}/{len(rows)}")
    print(f"identity intensity       : {report['identity_intensity_pass']} pass, "
          f"{report['identity_intensity_not_applicable']} n/a")
    print(f"missing primary variable : {report['missing_pct_variable']}")
    print(f"\nwrote -> {OUT}")
    return rows


if __name__ == "__main__":
    main()
