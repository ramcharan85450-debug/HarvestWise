import streamlit as st

from components.api_client import fetch_benchmark_leaderboard

st.set_page_config(page_title="Benchmark Leaderboard - HarvestWise", page_icon="🌾", layout="wide")

st.title("Benchmark Leaderboard")
st.caption(
    "HarvestWise against baselines on the Climate-Shock Benchmark. Every row is read from "
    "`evaluation/climate_shock_benchmark/results.json` — the output of an actual evaluation "
    "run, reproducible with `python -m evaluation.climate_shock_benchmark.run_climate_shock`."
)

leaderboard = fetch_benchmark_leaderboard()
ranked = leaderboard.sort_values("mae_shock_t_ha").reset_index(drop=True)

n_test = int(ranked["n_test_seasons"].iloc[0])
n_train = int(ranked["n_train_seasons"].iloc[0])

st.dataframe(
    ranked.style.format({"mae_shock_t_ha": "{:.3f}"}).highlight_min(
        subset=["mae_shock_t_ha"], color="#DDEDE6"
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    f"`mae_shock_t_ha`: mean absolute error in t/ha on {n_test} held-out real climate-shock "
    f"seasons, after fitting on {n_train} real normal seasons plus synthetic pretraining. "
    "**Lower is better.** The sample size is carried on every row on purpose — at this n "
    "the ranking should not be quoted without it."
)
