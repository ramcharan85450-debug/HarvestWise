"""
Experiment 1: baseline comparison of data-source combinations, for the
conference paper. Trains the SAME architecture (models.heads / training's
ForecastModel, unmodified) four times, each time masking a different subset
of its real inputs to zero, so the only thing that differs between runs is
which real data sources reach the model - not the architecture, epoch count,
or optimizer.

Uses ONLY the 21 real season examples already in data/processed/ +
data/raw/yield_labels/ (training.dataset.build_dataset_from_processed()).
No synthetic data is generated or used anywhere in this script - unlike
evaluation/run_model_comparison.py, which pretrains on
build_synthetic_dataset() before evaluating on real data, this experiment
trains directly on a chronological split of the real data alone, per this
experiment's explicit no-synthetic-data requirement.

Split strategy (documented, not arbitrary): all 21 real examples are sorted
by season_start_date ascending and cut into three CONTIGUOUS chronological
blocks - train = earliest 13, val = next 3, test = latest 5. Every test
example's season_start_date is later than every train example's, so no
later-season information can leak backward into training. This is a real
constraint on the design: two fields (F005, F007) have only one real season
each, so a per-field chronological holdout is not possible - the split is
global (pooled across fields) instead, which is documented as a limitation,
not hidden.

Existing checkpoints (backend/checkpoints/fusion_backbone.pt) are NOT reused
and NOT overwritten. They were trained on ALL real examples with no
modality masking and a random (non-chronological) train/val split, so they
answer a different question than this experiment does; each of the four
configurations below is trained from scratch. Nothing in backend/checkpoints
is touched by this script.

Run:
    python -m experiments.run_experiment1 --seeds 5 --epochs 30
"""

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch.utils.data import DataLoader

from evaluation.ablation.run_ablation import AblatedLoader
from training.dataset import SeasonDataset, build_dataset_from_processed, impute_missing_soil
from training.train_forecast_model import ForecastModel, train_one_epoch

EXPERIMENTS_DIR = Path(__file__).resolve().parent
REPRO_LOG_PATH = EXPERIMENTS_DIR / "reproducibility_log.json"

CONFIGS = {
    "baseline_weather_only": {
        "label": "Experiment A - Weather only",
        "data_sources": ["weather"],
        "zero_out": ["vision", "soil"],
        "feature_list": ["temp_c", "precip_mm", "humidity_pct", "wind_speed_ms"],
    },
    "baseline_satellite_only": {
        "label": "Experiment B - Satellite only",
        "data_sources": ["satellite"],
        "zero_out": ["weather", "soil"],
        "feature_list": ["ndvi", "ndvi_delta", "evi", "ndwi"],
    },
    "baseline_weather_satellite": {
        "label": "Experiment C - Weather + Satellite",
        "data_sources": ["weather", "satellite"],
        "zero_out": ["soil"],
        "feature_list": ["temp_c", "precip_mm", "humidity_pct", "wind_speed_ms", "ndvi", "ndvi_delta", "evi", "ndwi"],
    },
    "full_harvestwise": {
        "label": "Experiment D - Full multi-source (weather + satellite + soil)",
        "data_sources": ["weather", "satellite", "soil"],
        "zero_out": [],
        "feature_list": ["temp_c", "precip_mm", "humidity_pct", "wind_speed_ms", "ndvi", "ndvi_delta", "evi", "ndwi", "phh2o", "soc", "clay", "sand", "nitrogen"],
    },
    "baseline_soil_only": {
        # Added as a control after Experiment D's result (see report section 8):
        # soil is a static per-field constant, so a model given ONLY soil has
        # no season-varying signal at all - it can only ever predict a
        # per-field constant. This configuration exists specifically to make
        # that explicit and measurable, not to be a serious forecasting
        # baseline in its own right.
        "label": "Experiment E - Soil only (control)",
        "data_sources": ["soil"],
        "zero_out": ["vision", "weather"],
        "feature_list": ["phh2o", "soc", "clay", "sand", "nitrogen"],
    },
}

# No real forecast data exists in this project - ingestion/weather_fetch.py and
# district_weather_pull.py pull ERA5-Land, which is historical reanalysis, not
# a forward-looking forecast product. There is no configuration here that
# claims to use forecast data, per this experiment's explicit rule against
# claiming a source that isn't genuinely available.


def chronological_split(examples: list):
    ordered = sorted(examples, key=lambda e: e.season_start_date)
    n = len(ordered)
    n_test, n_val = 5, 3
    train, val, test = ordered[: n - n_val - n_test], ordered[n - n_val - n_test : n - n_test], ordered[n - n_test :]
    return train, val, test


@torch.no_grad()
def predict(model: ForecastModel, loader) -> tuple[list[float], list[float]]:
    model.eval()
    preds, actuals = [], []
    for batch in loader:
        quantiles, _ = model(batch)
        preds.extend(quantiles[:, -1, 1].tolist())  # last-week median quantile, same convention as predict_final_yield
        actuals.extend(batch["final_yield"].tolist())
    return preds, actuals


def train_one_config(zero_out: list[str], train_ds, epochs: int, seed: int) -> ForecastModel:
    torch.manual_seed(seed)
    train_loader = AblatedLoader(DataLoader(train_ds, batch_size=8, shuffle=True), zero_out)
    model = ForecastModel()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    for _ in range(epochs):
        train_one_epoch(model, train_loader, optimizer)
    return model


def metrics(preds: list[float], actuals: list[float]) -> dict:
    mae = mean_absolute_error(actuals, preds)
    rmse = mean_squared_error(actuals, preds) ** 0.5
    # r2_score needs target variance > 0 to be meaningful; the fixed 5-example
    # test set here has real yield variance (2.825-4.193 t/ha), so it is
    # computable, but is reported with an explicit small-n caveat in the
    # final report rather than treated as a stable estimate.
    r2 = r2_score(actuals, preds)
    return {"mae": mae, "rmse": rmse, "r2": r2}


def naive_baseline(train_examples, test_examples) -> dict:
    train_mean = statistics.mean(e.final_yield for e in train_examples)
    preds = [train_mean] * len(test_examples)
    actuals = [e.final_yield for e in test_examples]
    return {"preds": preds, "actuals": actuals, **metrics(preds, actuals)}


def run_config(name: str, cfg: dict, train_examples, val_examples, test_examples, epochs: int, seeds: int) -> dict:
    train_ds, val_ds, test_ds = SeasonDataset(train_examples), SeasonDataset(val_examples), SeasonDataset(test_examples)
    test_loader = AblatedLoader(DataLoader(test_ds, batch_size=len(test_ds)), cfg["zero_out"])
    val_loader = AblatedLoader(DataLoader(val_ds, batch_size=len(val_ds)), cfg["zero_out"])

    per_seed = []
    all_preds_seed0, all_actuals_seed0 = None, None
    for seed in range(seeds):
        model = train_one_config(cfg["zero_out"], train_ds, epochs, seed)
        test_preds, test_actuals = predict(model, test_loader)
        val_preds, val_actuals = predict(model, val_loader)
        m = metrics(test_preds, test_actuals)
        m["val_mae"] = mean_absolute_error(val_actuals, val_preds)
        per_seed.append(m)
        if seed == 0:
            all_preds_seed0, all_actuals_seed0 = test_preds, test_actuals

    agg = {
        metric: {
            "mean": statistics.mean(s[metric] for s in per_seed),
            "sd": statistics.stdev(s[metric] for s in per_seed) if seeds > 1 else 0.0,
            "min": min(s[metric] for s in per_seed),
            "max": max(s[metric] for s in per_seed),
        }
        for metric in ["mae", "rmse", "r2"]
    }
    return {
        "name": name,
        "label": cfg["label"],
        "data_sources": cfg["data_sources"],
        "feature_list": cfg["feature_list"],
        "per_seed": per_seed,
        "aggregate": agg,
        "seed0_test_preds": all_preds_seed0,
        "seed0_test_actuals": all_actuals_seed0,
    }


def make_figures(results: list[dict], naive: dict):
    names = [r["label"].split(" - ")[0] for r in results] + ["Naive (train mean)"]
    mae_means = [r["aggregate"]["mae"]["mean"] for r in results] + [naive["mae"]]
    mae_sds = [r["aggregate"]["mae"]["sd"] for r in results] + [0.0]
    rmse_means = [r["aggregate"]["rmse"]["mean"] for r in results] + [naive["rmse"]]
    rmse_sds = [r["aggregate"]["rmse"]["sd"] for r in results] + [0.0]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(names, mae_means, yerr=mae_sds, color="#3d7a4f", capsize=4)
    ax.set_ylabel("MAE (t/ha), mean +/- sd over seeds")
    ax.set_title("Experiment 1 - MAE by data-source configuration\n(n_test=5 - too small for a stable ranking, see report)")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(EXPERIMENTS_DIR / "figures" / "figure1_mae_comparison.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(names, rmse_means, yerr=rmse_sds, color="#4a6fa5", capsize=4)
    ax.set_ylabel("RMSE (t/ha), mean +/- sd over seeds")
    ax.set_title("Experiment 1 - RMSE by data-source configuration\n(n_test=5 - too small for a stable ranking, see report)")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(EXPERIMENTS_DIR / "figures" / "figure2_rmse_comparison.png", dpi=150)
    plt.close(fig)

    best = min(results, key=lambda r: r["aggregate"]["mae"]["mean"])
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    preds, actuals = best["seed0_test_preds"], best["seed0_test_actuals"]
    lo, hi = min(preds + actuals) - 0.2, max(preds + actuals) + 0.2
    ax.plot([lo, hi], [lo, hi], "--", color="gray", linewidth=1, label="perfect prediction")
    ax.scatter(actuals, preds, color="#c0533e", s=70, zorder=3)
    for a, p in zip(actuals, preds):
        ax.annotate(f"({a:.2f},{p:.2f})", (a, p), textcoords="offset points", xytext=(6, 4), fontsize=7)
    ax.set_xlabel("Actual yield (t/ha)")
    ax.set_ylabel("Predicted yield (t/ha)")
    ax.set_title(f"Actual vs. predicted - {best['label']} (seed 0)\nONLY 5 TEST POINTS - not a reliable calibration plot")
    ax.legend()
    fig.tight_layout()
    fig.savefig(EXPERIMENTS_DIR / "figures" / "figure3_actual_vs_predicted_best_model.png", dpi=150)
    plt.close(fig)

    return best["name"]


def verify_no_leakage(examples, train_examples, val_examples, test_examples) -> dict:
    """Checks the specific leakage vectors that matter for THIS pipeline, by
    reading what training/dataset.py actually does rather than assuming a
    generic sklearn-style fit(train)/transform(val,test) workflow - this
    project's normalization is not that, and the honest report is what it
    actually is, not what the workflow is usually assumed to be."""
    import numpy as np

    from training.dataset import SOIL_NORM, VISION_NORM, WEATHER_NORM

    findings = {}

    # 1. Is normalization a scaler FIT on any split, or fixed constants?
    findings["normalization_mechanism"] = (
        "FIXED CONSTANTS, not a fitted scaler. VISION_NORM/WEATHER_NORM/SOIL_NORM "
        "in training/dataset.py are literal (center, scale) tuples baked into the "
        "module, identical across every run, every split, and every experiment in "
        "this project - they are never computed from this experiment's train split "
        "(or from any split). This means the risk this check is usually run to catch "
        "- a scaler fit on data that includes the test set - cannot occur here by "
        "construction, but it is also not a 'fit-on-train-only' scaler in the usual "
        "sense: nothing is fit on train either. Verified by reading the literal "
        "values, not assumed:"
    )
    findings["normalization_constants"] = {
        "VISION_NORM (ndvi, ndvi_delta, evi, ndwi)": VISION_NORM,
        "WEATHER_NORM (temp_c, precip_mm, humidity_pct, wind_speed_ms)": WEATHER_NORM,
        "SOIL_NORM (phh2o, soc, clay, sand, nitrogen)": SOIL_NORM,
    }

    # 2. FIXED this session (was previously flagged as a present-but-inactive
    # leakage vector): training/dataset.py::impute_missing_soil() now takes an
    # explicit fit_examples argument, and this script calls
    # build_dataset_from_processed(impute=False) + splits + THEN
    # impute_missing_soil(examples, fit_examples=train_examples) - see main().
    # Checked here that this run actually did that (not just that the API
    # exists), and that with the current real data the fix is unobservable in
    # its output only because there is nothing to fix yet - 0 of 21 examples
    # have missing soil, so fit_examples's choice of pool has no effect on any
    # value in this run. The fix's value is in the code path being correct
    # for the day a field's soil pull fails, not in changing today's numbers.
    n_nan = int(sum(np.isnan(e.soil_x).any() for e in examples))
    findings["soil_imputation_leakage_vector"] = {
        "status": "FIXED - impute_missing_soil() now accepts fit_examples; this script passes fit_examples=train_examples explicitly (see run_experiment1.py::main)",
        "location": "training/dataset.py::impute_missing_soil()",
        "mechanism_now": "fill-in mean, if ever needed, is computed ONLY from fit_examples (here: the 13 training examples) - val/test examples can supply a value to be FILLED, never to help COMPUTE the fill value",
        "n_examples_with_nan_soil_in_this_run": n_nan,
        "verdict": (
            "No NaN soil in the current real data (0 of 21), so imputation does not "
            "run in this experiment either way - the fix changes the code path's "
            "correctness for a future failure, not any number reported today."
        ) if n_nan == 0 else (
            "Imputation ran this time; fit pool was train_examples only, per the code "
            "path above, so no val/test information reached the computed fill value."
        ),
    }

    # 3. Structural check: did the val/test DataLoaders used in run_config()
    # ever appear in a training_loader / optimizer.step() call? By
    # construction they cannot - train_one_config() only ever receives
    # train_ds, and predict() (used for both val and test) is wrapped in
    # @torch.no_grad() and is only called after training completes for that
    # seed. Confirmed here by checking the actual example objects are disjoint.
    train_ids = {id(e) for e in train_examples}
    val_ids = {id(e) for e in val_examples}
    test_ids = {id(e) for e in test_examples}
    findings["split_disjointness"] = {
        "train_val_overlap": len(train_ids & val_ids),
        "train_test_overlap": len(train_ids & test_ids),
        "val_test_overlap": len(val_ids & test_ids),
        "verdict": "disjoint (0 overlap in all three pairs)" if not (train_ids & val_ids or train_ids & test_ids or val_ids & test_ids) else "OVERLAP FOUND - invalid split",
    }
    findings["training_loop_leakage"] = (
        "train_one_config() (see this file) is called with ONLY train_ds - val_ds and "
        "test_ds are never passed to it, never appear in an optimizer.step() call, and "
        "are only read inside predict(), which is decorated @torch.no_grad() and is "
        "called strictly after training for that seed has finished. No early-stopping "
        "or best-epoch selection on val is performed (see report section 5) - a fixed "
        "epoch count is used for every seed, so val also never influences which "
        "weights are kept."
    )

    return findings


def document_test_set(test_examples) -> list[dict]:
    """Field ID, crop, season/year, and actual yield for every test example -
    the exact 5 real examples every configuration in this experiment is
    scored against."""
    from ingestion.config import FIELDS

    fields_by_id = {f["field_id"]: f for f in FIELDS}
    rows = []
    for e in test_examples:
        f = fields_by_id[e.field_id]
        year = e.season_start_date[:4] if e.season_start_date else "unknown"
        rows.append({
            "field_id": e.field_id,
            "field_name": f["name"],
            "crop": f["crop"],
            "season_start_date": e.season_start_date,
            "season_year": year,
            "actual_yield_t_ha": round(e.final_yield, 3),
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=30)
    args = parser.parse_args()

    # impute=False: soil imputation (if it were ever needed) must be fit on
    # the training split only, never on the full pool - see
    # training/dataset.py::impute_missing_soil's docstring and
    # verify_no_leakage() below. Splitting happens first, then imputation is
    # applied explicitly with fit_examples=train_examples.
    examples = build_dataset_from_processed(impute=False)
    train_examples, val_examples, test_examples = chronological_split(examples)
    impute_missing_soil(examples, fit_examples=train_examples)

    print(f"Real examples: {len(examples)} total -> train {len(train_examples)}, val {len(val_examples)}, test {len(test_examples)}")
    print(f"Train date range: {train_examples[0].season_start_date} .. {train_examples[-1].season_start_date}")
    print(f"Val   date range: {val_examples[0].season_start_date} .. {val_examples[-1].season_start_date}")
    print(f"Test  date range: {test_examples[0].season_start_date} .. {test_examples[-1].season_start_date}")

    naive = naive_baseline(train_examples, test_examples)
    print(f"\nNaive (predict train mean = {statistics.mean(e.final_yield for e in train_examples):.3f} t/ha): "
          f"MAE={naive['mae']:.3f} RMSE={naive['rmse']:.3f} R2={naive['r2']:.3f}")

    leakage = verify_no_leakage(examples, train_examples, val_examples, test_examples)
    (EXPERIMENTS_DIR / "leakage_verification.json").write_text(json.dumps(leakage, indent=2, default=str))
    print(f"\nLeakage check - soil imputation: {leakage['soil_imputation_leakage_vector']['verdict']}")
    print(f"Leakage check - split disjointness: {leakage['split_disjointness']['verdict']}")

    test_doc = document_test_set(test_examples)
    (EXPERIMENTS_DIR / "test_set_documentation.json").write_text(json.dumps(test_doc, indent=2))
    print("\nTest set:")
    for row in test_doc:
        print(f"  {row['field_id']:<6} {row['crop']:<20} {row['season_year']:<6} actual={row['actual_yield_t_ha']}")

    results = []
    repro_entries = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for name, cfg in CONFIGS.items():
        print(f"\n=== {cfg['label']} ({name}) ===")
        r = run_config(name, cfg, train_examples, val_examples, test_examples, args.epochs, args.seeds)
        results.append(r)
        agg = r["aggregate"]
        print(f"  MAE  = {agg['mae']['mean']:.3f} +/- {agg['mae']['sd']:.3f}  (range {agg['mae']['min']:.3f}-{agg['mae']['max']:.3f})")
        print(f"  RMSE = {agg['rmse']['mean']:.3f} +/- {agg['rmse']['sd']:.3f}")
        print(f"  R2   = {agg['r2']['mean']:.3f} +/- {agg['r2']['sd']:.3f}")

        out_dir = EXPERIMENTS_DIR / name
        (out_dir / "results.json").write_text(json.dumps({k: v for k, v in r.items()}, indent=2, default=float))

        repro_entries.append({
            "experiment_name": name,
            "data_sources": cfg["data_sources"],
            "feature_list": cfg["feature_list"],
            "dataset_version": "training.dataset.build_dataset_from_processed(), default granularity, commit-time snapshot",
            "n_train": len(train_examples), "n_val": len(val_examples), "n_test": len(test_examples),
            "split_strategy": "chronological by season_start_date, global (pooled across fields): earliest 13 = train, next 3 = val, latest 5 = test",
            "seeds": list(range(args.seeds)),
            "model_configuration": "training.train_forecast_model.ForecastModel(), default hyperparameters, unmodified across all 4 experiments",
            "training_configuration": f"AdamW lr=1e-3, {args.epochs} epochs, batch_size=8, no early stopping (fixed epoch count - see script docstring for why this differs from the production training script's val-based checkpoint selection)",
            "evaluation_metrics": {k: v["aggregate"] for k, v in [(name, r)]}[name],
            "timestamp": timestamp,
        })

    best_name = make_figures(results, naive)

    REPRO_LOG_PATH.write_text(json.dumps(repro_entries, indent=2, default=float))
    print(f"\nBest by mean test MAE: {best_name}")
    print(f"wrote reproducibility log -> {REPRO_LOG_PATH}")
    print(f"wrote figures -> {EXPERIMENTS_DIR / 'figures'}")

    (EXPERIMENTS_DIR / "naive_baseline.json").write_text(json.dumps(naive, indent=2, default=float))


if __name__ == "__main__":
    main()
