import streamlit as st

from components.api_client import fetch_harvest_window, fetch_scenario
from components.field_selector import render_field_selector
from components.scenario_chart import render_scenario_chart

st.set_page_config(page_title="Climate Scenario - HarvestWise", page_icon="🌾", layout="wide")

st.title("Climate Scenario — What If?")
field_id = render_field_selector()

st.write(
    "Perturb the weather input the forecast conditions on to see how the yield forecast, "
    "harvest window, and confidence respond under climate stress — the same counterfactual "
    "mechanism used to build the Climate-Shock Benchmark."
)

col_controls, col_chart = st.columns([1, 2])

with col_controls:
    temp_shift = st.slider("Temperature shift (°C)", min_value=0.0, max_value=4.0, value=0.0, step=0.5)
    rainfall_change = st.slider("Rainfall change (%)", min_value=-40, max_value=20, value=0, step=5)
    if st.button("Reset to forecast"):
        st.rerun()

scenario = fetch_scenario(field_id, temp_shift, rainfall_change)
baseline_window = fetch_harvest_window(field_id)

with col_chart:
    render_scenario_chart(scenario["baseline_forecast"], scenario["scenario_forecast"])

scenario_last = scenario["scenario_forecast"].iloc[-1]
baseline_last = scenario["baseline_forecast"].iloc[-1]
yield_delta = scenario_last["yield_median"] - baseline_last["yield_median"]

col1, col2, col3 = st.columns(3)
col1.metric("Scenario yield", f"{scenario_last['yield_median']:.2f} t/ha", delta=f"{yield_delta:+.2f} t/ha")
col2.metric(
    "Scenario window shift",
    f"+{scenario['scenario_window_shift_days']} day(s)" if scenario["scenario_window_shift_days"] > 0 else "No shift",
)
col3.metric(
    "Scenario confidence",
    f"{scenario['scenario_confidence'] * 100:.0f}%",
    delta=f"{(scenario['scenario_confidence'] - baseline_window['confidence']) * 100:+.0f} pts",
)

if temp_shift == 0 and rainfall_change == 0:
    st.info("Move the sliders to simulate a warmer or drier season and watch the forecast respond.", icon="🎚️")
elif scenario["scenario_confidence"] < 0.6:
    st.warning("Under this scenario, confidence has dropped below 60% — the recommendation should be treated cautiously.", icon="⚠️")
