"""
Real-outcome validation service.

Reads data/raw/harvest_outcomes/{field_id}_outcomes.csv - real records of what
a grower actually harvested, versus what the system recommended, versus a
fixed-date baseline. This is the project's highest-priority outstanding
data-acquisition item and the directory is currently empty, so every field
returns an empty list.

That empty list is the correct answer, not a gap to paper over. This module
previously returned nine hand-written seasons ("Rabi 2023, +0.62 t/ha over the
fixed-date baseline", and so on) for three fields that no longer exist in the
project, and the dashboard rendered them under the heading "the evidence
behind the real-outcome-validation claim". Fabricated evidence for the single
claim a reviewer is most likely to probe is worse than no evidence: no
evidence is an honest limitation, invented evidence is misconduct.

Populate the CSVs (columns listed in
evaluation/outcome_validation/backtest_real_outcomes.py) from a grower,
cooperative or agri-board case study and this endpoint becomes real with no
code change.
"""

from app.config import HARVEST_OUTCOMES_DIR


def get_outcomes(field_id: str) -> list[dict]:
    path = HARVEST_OUTCOMES_DIR / f"{field_id}_outcomes.csv"
    if not path.exists():
        return []

    import pandas as pd

    df = pd.read_csv(path)
    return [
        {
            "season": str(row["season_start_date"]),
            "recommended_window": (
                f"{row['recommended_window_start']} to {row['recommended_window_end']}"
            ),
            "actual_harvest_date": str(row["actual_harvest_date"]),
            "actual_yield_t_ha": float(row["actual_yield_t_ha"]),
            "fixed_date_baseline_yield_t_ha": float(row["fixed_date_baseline_yield_t_ha"]),
        }
        for _, row in df.iterrows()
    ]
