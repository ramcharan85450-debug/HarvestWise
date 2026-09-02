"""
Backtests a harvest-window recommendation against what actually happened -
the real-outcome-validation evidence, distinct from yield-forecast accuracy.

Reads data/raw/harvest_outcomes/{field_id}_outcomes.csv with columns:
    season_start_date, recommended_window_start, recommended_window_end,
    actual_harvest_date, actual_yield_t_ha, fixed_date_baseline_date,
    fixed_date_baseline_yield_t_ha
This is the highest-priority real-data item for the project (see novelty
scoring notes) - until it's populated, backend/app/services/outcome_service.py
serves clearly-labeled placeholder figures instead.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ingestion.config import RAW_DIR

OUTCOMES_DIR = RAW_DIR / "harvest_outcomes"


@dataclass
class BacktestSummary:
    field_id: str
    n_seasons: int
    mean_recommended_yield: float
    mean_fixed_date_yield: float
    mean_gain_t_ha: float
    win_rate: float  # fraction of seasons where the recommendation beat the fixed-date baseline


def backtest_field(field_id: str) -> BacktestSummary:
    path = OUTCOMES_DIR / f"{field_id}_outcomes.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"No real outcome records at {path} yet. This is the data-acquisition "
            "item to prioritize (farmer/cooperative/agri-board case study - see "
            "project data-acquisition notes)."
        )

    df = pd.read_csv(path)
    gains = df["actual_yield_t_ha"] - df["fixed_date_baseline_yield_t_ha"]

    return BacktestSummary(
        field_id=field_id,
        n_seasons=len(df),
        mean_recommended_yield=float(df["actual_yield_t_ha"].mean()),
        mean_fixed_date_yield=float(df["fixed_date_baseline_yield_t_ha"].mean()),
        mean_gain_t_ha=float(gains.mean()),
        win_rate=float((gains > 0).mean()),
    )


def backtest_all_fields(field_ids: list[str]) -> list[BacktestSummary]:
    summaries = []
    for field_id in field_ids:
        try:
            summaries.append(backtest_field(field_id))
        except FileNotFoundError as e:
            print(e)
    return summaries
