import plotly.graph_objects as go
import streamlit as st

from components.api_client import fetch_benchmark_leaderboard, fetch_climate_stress_results

st.set_page_config(page_title="Climate Stress Test - HarvestWise", page_icon="🌾", layout="wide")

st.title("Climate-Shock Benchmark")
st.caption(
    "Models are trained on real NORMAL field-seasons and scored on real climate-SHOCK "
    "seasons they never saw. Shock labels are derived from ERA5 growing-season anomalies "
    "(see evaluation/climate_shock_benchmark/derive_labels.py), not assigned by hand."
)

leaderboard = fetch_benchmark_leaderboard()
seasons = fetch_climate_stress_results()

n_test = int(leaderboard["n_test_seasons"].iloc[0])
n_train = int(leaderboard["n_train_seasons"].iloc[0])

st.warning(
    f"**Small sample: {n_test} held-out shock seasons** (trained on {n_train} normal seasons). "
    "The ordering below is indicative, not statistically powered. Widening the ERA5 date "
    "range in `ingestion/config.py` and re-running the pull is what makes this "
    "publication-strength.",
    icon="⚠️",
)

# Lower MAE is better, so the bar chart is sorted ascending and the winner is
# whichever model is furthest left - stated explicitly because the previous
# version of this page charted R^2, where the convention is the opposite.
ranked = leaderboard.sort_values("mae_shock_t_ha").reset_index(drop=True)
colors = ["#2F6E5C" if m.startswith("HarvestWise") else "#8A8F98" for m in ranked["model"]]

fig = go.Figure(
    go.Bar(
        x=ranked["model"],
        y=ranked["mae_shock_t_ha"],
        marker_color=colors,
        text=[f"{v:.3f}" for v in ranked["mae_shock_t_ha"]],
        textposition="outside",
    )
)
fig.update_layout(
    yaxis_title="MAE on shock seasons (t/ha) — lower is better",
    template="plotly_white",
    height=420,
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig, use_container_width=True)

best = ranked.iloc[0]
hw = ranked[ranked["model"].str.startswith("HarvestWise")]
if not hw.empty and hw.iloc[0]["model"] != best["model"]:
    st.error(
        f"**The multimodal model does not currently win this benchmark.** "
        f"`{best['model']}` reaches MAE {best['mae_shock_t_ha']:.3f} t/ha versus "
        f"{hw.iloc[0]['mae_shock_t_ha']:.3f} t/ha for `{hw.iloc[0]['model']}`. "
        f"Tree ensembles are hard to beat at this sample size; this is reported as-is.",
        icon="📉",
    )

st.subheader("Held-out shock seasons")
st.caption("The real field-seasons in the test set, with the ERA5-derived anomaly that qualified each one.")
st.dataframe(seasons, use_container_width=True, hide_index=True)
