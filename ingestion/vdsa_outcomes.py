"""
Builds real harvest-outcome records from ICRISAT's Village Dynamics in South
Asia (VDSA) micro-data - Cult_ip (cultivation operations, with real dates per
operation) joined to Crop_info_op (harvested output per plot), for the
EastIndia region, 2010-2013.

This is the project's real-outcome validation data. It was the one thing the
project could not derive, download, or model from anything else - see
data/raw/harvest_outcomes/README.md, which explains why an invented record was
worse than none. VDSA is a genuine, decades-running ICRISAT/NCAP/IRRI panel
survey (village-level field investigators recording each cultivation
operation as it happens, not farmer recall at season's end), obtained via free
registration at vdsa.icrisat.org.

What this is NOT: a record of "recommended harvest window vs actual harvest
date vs a fixed-date baseline" - VDSA has no notion of a system recommendation,
because no such system existed when this was collected. What it IS: real
sowing date, real harvest date, and real measured yield, for 848 plot-seasons
(712 paddy, 136 wheat) across Bihar, Jharkhand and Odisha, 2010-2013.

Two honest limitations to carry into any reporting of this data:

1. Region mismatch. VDSA's EastIndia round covers Bihar (IBH), Jharkhand
   (IJH) and Odisha (IOR) - none of this project's 7 named fields are in
   those states. This validates the METHOD (does a harvest-timing policy's
   recommendation align with what real growers who timed their harvest well
   actually did) on a different population than the yield-forecast model was
   evaluated on, not the same fields end to end.
2. Field-recorded, not farmer-recalled. Values come from VDSA's monthly
   field-investigator visits (per the questionnaire in
   Include/Questionaire/YII.pdf), which is a real strength over survey recall,
   but yield here is measured production divided by the surveyed plot area in
   acres, not verified against a separate area survey - stated as VDSA's own
   documented methodology, not an assumption made here.

Run:
    python -m ingestion.vdsa_outcomes
"""

from pathlib import Path

import pandas as pd

from ingestion.config import RAW_DIR

VDSA_DIR = RAW_DIR / "external" / "vdsa" / "by_year"
OUT_DIR = RAW_DIR / "harvest_outcomes"

KEY = ["Sur_yr", "Cult_id/Hhid/Vdsid", "Plot_code"]

SOWING_OPS = ["Sowing", "Transplantation"]
HARVEST_OPS = ["Harvesting", "Harvesting And Threshing"]
CROPS = ["Paddy", "Wheat"]

MIN_DAYS, MAX_DAYS = 30, 250  # plausibility bounds on sow-to-harvest duration
MIN_YIELD, MAX_YIELD = 0.2, 12.0  # t/ha, same bounds used for the district data

ACRE_TO_HA = 0.4047


def _load(base: str) -> pd.DataFrame:
    parts = sorted(VDSA_DIR.glob(f"{base}_*.xlsx"))
    if not parts:
        raise FileNotFoundError(f"No {base}_*.xlsx under {VDSA_DIR} - download via vdsa.icrisat.org first.")
    return pd.concat([pd.read_excel(p) for p in parts], ignore_index=True)


def build_plot_seasons() -> pd.DataFrame:
    cult = _load("Cult_ip")
    crop = _load("Crop_info_op")

    sow = cult[cult.Operation.isin(SOWING_OPS)].groupby(KEY)["Dt_oper"].min().rename("sow_date")
    harvest = cult[cult.Operation.isin(HARVEST_OPS)].groupby(KEY)["Dt_oper"].max().rename("harvest_date")

    yields = crop[crop.Crop_name.isin(CROPS) & crop.Op_main_prod_qty.notna()].copy()
    # Op_main_prod_unit is Kg or Qt (quintal = 100 kg) in this survey round.
    yields["yield_kg"] = yields.Op_main_prod_qty * yields.Op_main_prod_unit.map({"Kg": 1, "Qt": 100}).fillna(0)
    agg = (
        yields.groupby(KEY)
        .agg(crop=("Crop_name", "first"), area_acres=("Plot_area", "first"), yield_kg=("yield_kg", "sum"))
        .reset_index()
        .set_index(KEY)
    )

    df = agg.join(sow, how="inner").join(harvest, how="inner")
    df = df[df.area_acres > 0]
    df["yield_t_ha"] = (df.yield_kg / 1000) / (df.area_acres * ACRE_TO_HA)
    df["sow_date"] = pd.to_datetime(df.sow_date, dayfirst=True, errors="coerce")
    df["harvest_date"] = pd.to_datetime(df.harvest_date, dayfirst=True, errors="coerce")
    df = df.dropna(subset=["sow_date", "harvest_date"])
    df["days_to_harvest"] = (df.harvest_date - df.sow_date).dt.days

    df = df[(df.days_to_harvest > MIN_DAYS) & (df.days_to_harvest < MAX_DAYS)]
    df = df[(df.yield_t_ha > MIN_YIELD) & (df.yield_t_ha < MAX_YIELD)]
    return df.reset_index()


def main():
    df = build_plot_seasons()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "VDSA_EastIndia_plot_seasons.csv"
    df.to_csv(out_path, index=False)

    print(f"real plot-seasons with sow date + harvest date + plausible yield: {len(df)}")
    print(df.crop.value_counts().to_string())
    print(f"years: {sorted(df.Sur_yr.unique())}")
    print(f"wrote -> {out_path}")


if __name__ == "__main__":
    main()
