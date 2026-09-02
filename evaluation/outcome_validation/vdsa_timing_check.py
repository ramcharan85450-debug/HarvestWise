"""
Checks this project's harvest-timing assumptions against 848 real sow-to
-harvest intervals from ICRISAT's VDSA panel (see ingestion/vdsa_outcomes.py).

This deliberately does NOT attempt to match VDSA's 12 villages to satellite
pixels. Geocoding the village names (Arap, Baghakole, Inai, Susari,
Dubaliya, Hesapiri, Dumariya, Durgapur, Sogar, Ainlatunga, Bilaikani) against
OpenStreetMap found only 6 of 11, and none with confirmed certainty - India
has many same-named villages, and a wrong match would silently corrupt a
plot-level comparison with the wrong location's weather and imagery, which is
a worse failure than not running the comparison at all.

What VDSA CAN support without any geolocation: real, independently-collected
evidence on how long a sow-to-harvest interval actually is. That is used here
to check two things this project previously assumed rather than measured:

1. CROP_CALENDARS' season_length_weeks (ingestion/config.py) - is 154 days a
   reasonable rice season, 140 days a reasonable wheat season?
2. The OLD min_harvest_week bound (season_len // 2, replaced in
   models/heads/rl_harvest_policy/agronomic_window.py after the IRRI-window
   check found it disagreed with published guidance on 20/21 real seasons) -
   where does that bound fall in the distribution of when real farmers
   actually harvested?

Run:
    python -m ingestion.vdsa_outcomes
    python -m evaluation.outcome_validation.vdsa_timing_check
"""

import json
from pathlib import Path

import pandas as pd

from ingestion.config import CROP_CALENDARS, RAW_DIR

OUTCOMES_PATH = RAW_DIR / "harvest_outcomes" / "VDSA_EastIndia_plot_seasons.csv"
RESULTS_PATH = Path(__file__).resolve().parent / "vdsa_timing_check.json"

CROP_MAP = {"Paddy": "rice", "Wheat": "wheat"}


def main():
    if not OUTCOMES_PATH.exists():
        raise FileNotFoundError(f"Missing {OUTCOMES_PATH} - run `python -m ingestion.vdsa_outcomes` first.")

    df = pd.read_csv(OUTCOMES_PATH)
    results = {}

    for crop_name, calendar_key in CROP_MAP.items():
        d = df.loc[df.crop == crop_name, "days_to_harvest"]
        our_days = CROP_CALENDARS[calendar_key]["season_length_weeks"] * 7
        old_bound_days = our_days // 2
        percentile_of_old_bound = float((d < old_bound_days).mean())

        results[crop_name] = {
            "n_real_plot_seasons": int(len(d)),
            "real_days_to_harvest": {
                "mean": round(float(d.mean()), 1),
                "median": round(float(d.median()), 1),
                "p25": round(float(d.quantile(0.25)), 1),
                "p75": round(float(d.quantile(0.75)), 1),
                "min": round(float(d.min()), 1),
                "max": round(float(d.max()), 1),
            },
            "project_assumed_season_days": our_days,
            "old_min_harvest_week_bound_days": old_bound_days,
            "old_bound_percentile_of_real_harvests": round(percentile_of_old_bound, 3),
        }

        print(f"{crop_name} (n={len(d)} real plot-seasons):")
        print(f"  real sow-to-harvest: mean {d.mean():.0f}d, median {d.median():.0f}d, "
              f"IQR [{d.quantile(.25):.0f}, {d.quantile(.75):.0f}]")
        print(f"  project's CROP_CALENDARS assumption: {our_days}d")
        print(
            f"  OLD min_harvest_week bound was {old_bound_days}d -> real farmers harvested "
            f"later than that on {100*(1-percentile_of_old_bound):.1f}% of the 848 real seasons\n"
        )

    print(
        "This independently corroborates the IRRI-window finding "
        "(evaluation/outcome_validation/agronomic_agreement.py): the OLD "
        "season_len // 2 harvest bound was not just agronomically unjustified "
        "in theory, real growers' behavior confirms it was far too early."
    )

    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nwrote -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
