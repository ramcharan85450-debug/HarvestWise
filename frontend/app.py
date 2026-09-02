import streamlit as st

from components.api_client import is_backend_live
from components.field_selector import render_field_selector

st.set_page_config(page_title="HarvestWise", page_icon="🌾", layout="wide")

st.title("HarvestWise")
st.caption(
    "Multimodal Spatio-Temporal Deep Learning Framework for Climate-Adaptive "
    "Crop Yield Forecasting and Dynamic Harvest Window Optimization"
)

field_id = render_field_selector()

live = is_backend_live()
status_label = "Connected to live backend" if live else "Backend not running — no data will be shown"
status_color = "#2F6E5C" if live else "#B3452C"
st.sidebar.markdown(
    f'<span style="color:{status_color}; font-size:13px;">&#9679; {status_label}</span>',
    unsafe_allow_html=True,
)

st.divider()
st.subheader("Overview")
st.write(
    "Use the pages in the sidebar to explore the yield forecast, the recommended "
    "harvest window, and the climate-robustness benchmark for the selected field."
)

col1, col2, col3 = st.columns(3)
col1.markdown("**1. Yield Forecast**\n\nSeasonal yield prediction with uncertainty bands.")
col2.markdown("**2. Harvest Window**\n\nAdaptive, confidence-scored harvest timing recommendation.")
col3.markdown("**3. Climate Stress Test**\n\nModel robustness across normal vs. anomalous climate years.")

st.info("Select a page from the sidebar to continue.", icon="👈")
