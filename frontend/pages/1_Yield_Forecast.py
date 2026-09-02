import streamlit as st

from components.api_client import fetch_forecast
from components.field_selector import render_field_selector
from components.forecast_chart import render_forecast_chart

st.set_page_config(page_title="Yield Forecast - HarvestWise", page_icon="🌾", layout="wide")

st.title("Yield Forecast")
field_id = render_field_selector()

forecast_df = fetch_forecast(field_id)

st.write("Median weekly yield forecast for the current season, with the 10th-90th percentile uncertainty band.")
render_forecast_chart(forecast_df)

latest = forecast_df.iloc[-1]
col1, col2, col3 = st.columns(3)
col1.metric("Latest median forecast", f"{latest['yield_median']:.2f} t/ha")
col2.metric("Low estimate (10th pct.)", f"{latest['yield_low']:.2f} t/ha")
col3.metric("High estimate (90th pct.)", f"{latest['yield_high']:.2f} t/ha")

with st.expander("Raw forecast data"):
    st.dataframe(forecast_df, use_container_width=True)
