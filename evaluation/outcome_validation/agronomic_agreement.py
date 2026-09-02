"""
Agronomic-agreement validation: does the learned harvest policy agree with the
published agronomic optimum?

This is a SUBSTITUTE for real-outcome validation, not an equivalent of it, and
the distinction must survive into the write-up. Real-outcome validation asks
"did acting on the recommendation produce a better harvest than the grower's
customary date" - that needs records from an actual grower, and
data/raw/harvest_outcomes/ is still empty. This asks the weaker but genuinely
answerable question: "does the policy's recommended week fall inside the
harvest window agronomists independently publish for this crop?"

Ground truth comes from IRRI's Rice Knowledge Bank, which gives an optimum of
28-35 days after heading for a dry-season harvest and 32-38 days after heading
for a wet-season one. Earlier harvesting leaves unfilled, immature grain and
raises milling breakage; later harvesting loses grain to shattering.
    http://www.knowledgebank.irri.org/training/fact-sheets/item/when-to-harvest-fact-sheet

Heading date is not recorded anywhere in this project's data, so it is
estimated from the real satellite series as the week of PEAK NDVI. That is a
standard remote-sensing proxy - canopy greenness peaks around heading/anthesis
and declines through grain fill and senescence - but it is a proxy, and its
error (roughly +/- one 7-day observation step here) is comparable to the width
of the IRRI window itself. Report the agreement rate with that caveat attached;
it is the main reason this cannot replace real outcome records.

All 7 fields are kharif/monsoon-season rice or rabi wheat, so the wet-season
window (32-38 DAH) is used for kharif rice and the dry-season window (28-35
DAH) for the rabi wheat field.

Run:
    python -m evaluation.outcome_validation.agronomic_agreement
"""

import json
from datetime import date
from pathlib import Path

import numpy as np

from ingestion.config import FIELDS
from training.dataset import build_dataset_from_processed

RESULTS_PATH = Path(__file__).resolve().parent / "agronomic_agreement.json"

# Days after heading, from the IRRI fact sheet cited above.
WET_SEASON_DAH = (32, 38)
DRY_SEASON_DAH = (28, 35)

DAYS_PER_STEP = 7  # the aligned series is weekly

CROP_BY_FIELD = {f["field_id"]: f["crop"] for f in FIELDS}


def _window_for(crop: str) -> tuple[int, int]:
    """Kharif rice is harvested out of the monsoon (wet-season window); Punjab
    rabi wheat matures into the dry season."""
    return DRY_SEASON_DAH if crop.startswith("wheat") else WET_SEASON_DAH


def heading_week(vision_x: np.ndarray) -> int:
    """Index of peak NDVI (column 0 of vision_x) = heading proxy."""
    return int(np.argmax(vision_x[:, 0]))


def agronomic_window_weeks(vision_x: np.ndarray, crop: str) -> tuple[int, int]:
    lo_days, hi_days = _window_for(crop)
    head = heading_week(vision_x)
    return head + lo_days // DAYS_PER_STEP, head + int(np.ceil(hi_days / DAYS_PER_STEP))


def _load_forecast_model():
    import torch

    from training.train_forecast_model import CHECKPOINT_DIR, ForecastModel

    model = ForecastModel()
    ckpt = torch.load(CHECKPOINT_DIR / "fusion_backbone.pt", map_location="cpu")
    for part in ("vision_enc", "weather_enc", "soil_enc", "fusion", "backbone"):
        getattr(model, part).load_state_dict(ckpt[part])
    model.head.load_state_dict(torch.load(CHECKPOINT_DIR / "yield_head.pt", map_location="cpu"))
    model.eval()
    return model


def _recommended_week(quantiles, rainfall, min_week: int) -> tuple[int, str]:
    """The policy's chosen harvest week: trained PPO where available, else the
    static optimizer. Same fallback the serving layer uses, so this validates
    the recommendation users actually get."""
    median = quantiles[:, 1].tolist()
    low, high = quantiles[:, 0].tolist(), quantiles[:, 2].tolist()
    n = len(median)

    try:
        from stable_baselines3 import PPO

        from models.heads.rl_harvest_policy.env import HarvestTimingEnv
        from training.train_forecast_model import CHECKPOINT_DIR

        policy = PPO.load(str(CHECKPOINT_DIR / "rl_harvest_policy.zip"), device="cpu")
        k = HarvestTimingEnv.LOOKAHEAD_WEEKS

        def ahead(series, w):
            return [series[min(w + j, n - 1)] for j in range(1, k + 1)]

        week = min_week
        while week < n - 1:
            obs = np.array(
                [median[week], low[week], high[week], rainfall[week], week / max(1, n - 1),
                 *ahead(median, week), *ahead(rainfall, week)],
                dtype=np.float32,
            )
            action, _ = policy.predict(obs, deterministic=True)
            if int(action) == 1:
                return week, "RL adaptive policy"
            week += 1
        return n - 1, "RL adaptive policy"
    except Exception:
        from models.heads.static_harvest_optimizer import optimize_window

        return (
            optimize_window(median, rainfall, window_len_weeks=1, search_start_idx=min_week).start_week_idx,
            "Static multi-objective optimizer",
        )


def main():
    import torch

    from training.dataset import normalize_model_inputs

    examples = build_dataset_from_processed()
    if not examples:
        print("No real season examples - run ingestion/align_pipeline.py first.")
        return

    model = _load_forecast_model()
    rows, agree = [], 0

    for ex in examples:
        crop = CROP_BY_FIELD.get(ex.field_id, "rice")
        v, w, s = normalize_model_inputs(ex.vision_x, ex.weather_x, ex.soil_x)
        batch = {
            "vision_x": torch.from_numpy(v).unsqueeze(0),
            "weather_x": torch.from_numpy(w).unsqueeze(0),
            "soil_x": torch.from_numpy(s).unsqueeze(0),
            "growth_stage": torch.from_numpy(ex.growth_stage).unsqueeze(0),
        }
        with torch.no_grad():
            quantiles, _ = model(batch)
        q = quantiles[0].numpy()

        rainfall = ex.weather_x[:, 1].tolist()
        min_week = len(q) // 2
        rec_week, source = _recommended_week(q, rainfall, min_week)
        lo, hi = agronomic_window_weeks(ex.vision_x, crop)

        inside = lo <= rec_week <= hi
        agree += int(inside)
        rows.append(
            {
                "field_id": ex.field_id,
                "season_start": ex.season_start_date,
                "crop": crop,
                "heading_week": heading_week(ex.vision_x),
                "agronomic_window_weeks": [int(lo), int(hi)],
                "recommended_week": int(rec_week),
                "weeks_outside": 0 if inside else int(min(abs(rec_week - lo), abs(rec_week - hi))),
                "agrees": bool(inside),
                "recommended_by": source,
            }
        )

    rate = agree / len(rows)
    print(f"=== Agronomic agreement (IRRI harvest window) ===")
    print(f"real season examples : {len(rows)}")
    print(f"policy inside window : {agree}  ({rate:.1%})")
    offs = [r["weeks_outside"] for r in rows if not r["agrees"]]
    if offs:
        print(f"when outside, median miss: {int(np.median(offs))} week(s), max {max(offs)}")
    print()
    for r in rows[:12]:
        mark = "OK " if r["agrees"] else "off"
        print(
            f"  {mark} {r['field_id']} {r['season_start']}  heading wk {r['heading_week']:>2}  "
            f"IRRI wk {r['agronomic_window_weeks'][0]}-{r['agronomic_window_weeks'][1]}  "
            f"policy wk {r['recommended_week']}"
        )

    print(
        "\nCAVEAT to report with this number: heading date is a PEAK-NDVI proxy at\n"
        "7-day resolution, and its error is comparable to the width of the IRRI\n"
        "window itself. This measures agreement with published agronomic guidance,\n"
        "NOT that acting on the recommendation improved a real harvest - that still\n"
        "requires the grower records described in data/raw/harvest_outcomes/README.md."
    )

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "source": "IRRI Rice Knowledge Bank - When to harvest",
                "wet_season_days_after_heading": WET_SEASON_DAH,
                "dry_season_days_after_heading": DRY_SEASON_DAH,
                "heading_proxy": "week of peak NDVI",
                "n_seasons": len(rows),
                "n_agree": agree,
                "agreement_rate": round(rate, 4),
                "seasons": rows,
            },
            indent=2,
        )
    )
    print(f"\nwrote -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
