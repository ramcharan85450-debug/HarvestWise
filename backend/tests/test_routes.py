from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_fields():
    resp = client.get("/fields")
    assert resp.status_code == 200
    fields = resp.json()
    assert len(fields) >= 1
    assert "field_id" in fields[0]


def test_forecast_known_field():
    field_id = client.get("/fields").json()[0]["field_id"]
    resp = client.get(f"/forecast/{field_id}")
    assert resp.status_code == 200
    points = resp.json()
    assert len(points) > 0
    assert points[0]["yield_low"] <= points[0]["yield_median"] <= points[0]["yield_high"]


def test_forecast_unknown_field():
    resp = client.get("/forecast/DOES_NOT_EXIST")
    assert resp.status_code == 404


def test_harvest_window_known_field():
    field_id = client.get("/fields").json()[0]["field_id"]
    resp = client.get(f"/harvest-window/{field_id}")
    assert resp.status_code == 200
    window = resp.json()
    assert 0 <= window["confidence"] <= 1
    assert window["window_start"] < window["window_end"]


def test_explanation_known_field():
    field_id = client.get("/fields").json()[0]["field_id"]
    resp = client.get(f"/explain/{field_id}")
    assert resp.status_code == 200
    assert "summary" in resp.json()


def test_benchmark_climate_stress():
    resp = client.get("/benchmark/climate-stress")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_benchmark_leaderboard():
    resp = client.get("/benchmark/results")
    assert resp.status_code == 200
    leaderboard = resp.json()
    assert any(entry["model"].startswith("HarvestWise") for entry in leaderboard)


def test_scenario_no_shift_matches_baseline():
    field_id = client.get("/fields").json()[0]["field_id"]
    resp = client.get(f"/scenario/{field_id}", params={"temp_shift_c": 0, "rainfall_change_pct": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_forecast"][-1]["yield_median"] == data["baseline_forecast"][-1]["yield_median"]


def test_scenario_warming_reduces_yield_and_confidence():
    field_id = client.get("/fields").json()[0]["field_id"]
    baseline = client.get(f"/scenario/{field_id}", params={"temp_shift_c": 0, "rainfall_change_pct": 0}).json()
    stressed = client.get(f"/scenario/{field_id}", params={"temp_shift_c": 3, "rainfall_change_pct": -30}).json()
    assert stressed["scenario_forecast"][-1]["yield_median"] < baseline["scenario_forecast"][-1]["yield_median"]
    assert stressed["scenario_confidence"] < baseline["scenario_confidence"]


def test_scenario_rejects_out_of_range_values():
    field_id = client.get("/fields").json()[0]["field_id"]
    resp = client.get(f"/scenario/{field_id}", params={"temp_shift_c": 10, "rainfall_change_pct": 0})
    assert resp.status_code == 422


def test_outcomes_reflect_real_files_only():
    """Outcomes come from data/raw/harvest_outcomes/*.csv or not at all.

    This asserted `len(outcomes) >= 1` while the service returned nine
    hand-written seasons, so it actively locked the fabrication in place. The
    honest contract is: a field with no real outcome CSV returns an empty
    list, and any row that IS returned came from a file on disk.
    """
    from app.config import HARVEST_OUTCOMES_DIR

    field_id = client.get("/fields").json()[0]["field_id"]
    resp = client.get(f"/outcomes/{field_id}")
    assert resp.status_code == 200
    outcomes = resp.json()

    if not (HARVEST_OUTCOMES_DIR / f"{field_id}_outcomes.csv").exists():
        assert outcomes == []
    else:
        assert outcomes and outcomes[0]["actual_yield_t_ha"] > 0


def test_leaderboard_matches_evaluation_output():
    """Every leaderboard number must be traceable to a real evaluation run,
    not hardcoded in the service."""
    import json

    from app.config import CLIMATE_SHOCK_RESULTS

    served = client.get("/benchmark/results").json()
    on_disk = json.loads(CLIMATE_SHOCK_RESULTS.read_text())["mae_t_ha"]

    assert {e["model"] for e in served} == set(on_disk)
    for entry in served:
        assert entry["mae_shock_t_ha"] == round(float(on_disk[entry["model"]]), 4)
        # Sample size travels with the score so it can't be quoted without it.
        assert entry["n_test_seasons"] > 0


def test_forecast_bounds_are_predicted_quantiles():
    """The low/high bounds must be the model's own 0.1/0.9 quantiles, not the
    median rescaled by a fixed factor the way the placeholder produced them
    (yield_low = median * 0.85, yield_high = median * 1.15)."""
    field_id = client.get("/fields").json()[0]["field_id"]
    points = client.get(f"/forecast/{field_id}").json()
    ratios = {round(p["yield_low"] / p["yield_median"], 3) for p in points if p["yield_median"] > 0}
    assert len(ratios) > 1, f"low/median ratio is constant ({ratios}) - bounds look synthetic"


def test_outcomes_unknown_field():
    resp = client.get("/outcomes/DOES_NOT_EXIST")
    assert resp.status_code == 404


def test_forecast_deterministic_for_same_field():
    field_id = client.get("/fields").json()[0]["field_id"]
    first = client.get(f"/forecast/{field_id}").json()
    second = client.get(f"/forecast/{field_id}").json()
    assert first == second
