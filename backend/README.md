# HarvestWise Backend

FastAPI service that serves yield forecasts, harvest-window recommendations,
explanations, and benchmark results to the `frontend/` Streamlit dashboard.

It serves **real model output**. Every endpoint runs the trained checkpoints in
`backend/checkpoints/` over the real ingested data in `data/processed/`, or
returns 503 saying what is missing. Nothing here simulates a result.

That is a deliberate, load-bearing property. The services previously returned
per-field seeded placeholder values - a smooth forecast curve, a hand-written
R^2 leaderboard, nine invented harvest-outcome records - which the dashboard
rendered identically to real output, with no way for a viewer to tell them
apart. Any endpoint that cannot answer for real now raises
`app.services.errors.RealDataUnavailable` and `app/main.py` turns it into a
503 with the reason attached.

## Where each number comes from

| Endpoint | Real source |
|---|---|
| `/fields` | `ingestion/config.py` FIELDS; area computed from the actual polygon |
| `/forecast/{id}` | trained `fusion_backbone.pt` + `yield_head.pt` over `data/processed/{id}_aligned.csv` |
| `/harvest-window/{id}` | trained PPO policy (`rl_harvest_policy.zip`), falling back to `models/heads/static_harvest_optimizer.py` |
| `/explain/{id}` | `evaluation/explainability/counterfactual_explainer.py` against the real recommendation |
| `/scenario/{id}` | the real weather tensor, perturbed, re-run through the model |
| `/benchmark/*` | `evaluation/climate_shock_benchmark/results.json` |
| `/outcomes/{id}` | `data/raw/harvest_outcomes/{id}_outcomes.csv` - **currently empty, so this returns `[]`** |

The empty outcomes response is the project's real state, not a bug: no grower
or cooperative harvest records have been secured yet. See
`evaluation/outcome_validation/backtest_real_outcomes.py` for the columns
needed to populate it.

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

API docs (auto-generated): http://localhost:8000/docs
Health check: http://localhost:8000/health

## Run tests

```bash
pytest
```

## Refreshing the served models

The training scripts write straight into `backend/checkpoints/`, so there is
nothing to copy:

```bash
python -m training.train_forecast_model            # fusion_backbone.pt + yield_head.pt
python -m models.heads.rl_harvest_policy.train_rl  # rl_harvest_policy.zip
```

`/health` reports `models_live: true` once the two required forecast
checkpoints are present. The RL policy is optional - without it
`/harvest-window` uses the static optimizer and says so in `recommended_by`.

Restart the API after retraining: `model_loader.py` caches the loaded models
for the process lifetime.

## Structure

- `app/main.py` - FastAPI app, mounts all routers, CORS, `/health`
- `app/api/` - one router per resource (fields, forecast, harvest, explain, benchmark)
- `app/services/` - business logic; this is where real model inference will plug in
- `app/schemas/` - pydantic response models (the API contract)
- `app/models_registry/` - checkpoint discovery/loading seam for trained models
- `app/config.py` - environment-driven settings
- `tests/` - endpoint tests (pytest + FastAPI TestClient)
