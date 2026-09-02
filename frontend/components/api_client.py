"""
Thin wrapper around the backend API.

Every value rendered by this dashboard comes from the FastAPI backend, which
serves real trained-model output over real ingested data or returns 503 saying
what is missing (see backend/README.md).

There is deliberately no local fallback. This module used to import
`mock_data.py` and silently substitute a simulated forecast, a hand-written
R^2 leaderboard and nine invented harvest-outcome records whenever a request
failed -- including when the backend was running and correctly reporting that
it had no real data. A viewer had no way to tell the two apart, so a demo
given while the backend was down would have shown fabricated results
indistinguishable from real ones. When a call fails now, the page says so and
stops.
"""

import os

import requests
import streamlit as st

BACKEND_URL = os.environ.get("HARVESTWISE_BACKEND_URL", "http://localhost:8000")
TIMEOUT_SECONDS = 10  # real inference is a forward pass, not a lookup


def _get(path: str, params: dict | None = None):
    """Returns the decoded JSON, or renders the failure and halts the page."""
    try:
        resp = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as e:
        st.error(
            f"**Backend unreachable** at `{BACKEND_URL}`.\n\n"
            f"Start it with `uvicorn app.main:app --port 8000` from `backend/`.\n\n"
            f"`{type(e).__name__}: {e}`",
            icon="🔌",
        )
        st.stop()

    if resp.status_code == 503:
        detail = resp.json().get("detail", "no detail given")
        st.warning(
            f"**No real data for this view yet.**\n\n{detail}\n\n"
            "Nothing is shown rather than a simulated stand-in.",
            icon="⚠️",
        )
        st.stop()

    if not resp.ok:
        st.error(f"Backend returned {resp.status_code} for `{path}`:\n\n{resp.text[:500]}", icon="🚨")
        st.stop()

    return resp.json()


def _frame(data):
    import pandas as pd

    return pd.DataFrame(data)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_fields():
    return _get("/fields")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_forecast(field_id: str):
    return _frame(_get(f"/forecast/{field_id}"))


@st.cache_data(ttl=300, show_spinner=False)
def fetch_harvest_window(field_id: str):
    return _get(f"/harvest-window/{field_id}")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_explanation(field_id: str):
    return _get(f"/explain/{field_id}")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_climate_stress_results():
    return _frame(_get("/benchmark/climate-stress"))


@st.cache_data(ttl=300, show_spinner=False)
def fetch_benchmark_leaderboard():
    return _frame(_get("/benchmark/results"))


@st.cache_data(ttl=60, show_spinner=False)
def fetch_scenario(field_id: str, temp_shift_c: float, rainfall_change_pct: float):
    data = _get(
        f"/scenario/{field_id}",
        params={"temp_shift_c": temp_shift_c, "rainfall_change_pct": rainfall_change_pct},
    )
    data["baseline_forecast"] = _frame(data["baseline_forecast"])
    data["scenario_forecast"] = _frame(data["scenario_forecast"])
    return data


@st.cache_data(ttl=300, show_spinner=False)
def fetch_outcomes(field_id: str):
    return _frame(_get(f"/outcomes/{field_id}"))


def is_backend_live() -> bool:
    try:
        return requests.get(f"{BACKEND_URL}/fields", timeout=TIMEOUT_SECONDS).ok
    except requests.RequestException:
        return False
