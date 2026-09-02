import streamlit as st


def render_explanation_panel(explanation: dict):
    st.markdown("##### Why this recommendation")
    st.info(explanation["summary"])

    col1, col2 = st.columns(2)
    col1.metric("Forecasted rainfall in window", f"{explanation['forecast_mm']} mm")
    col2.metric("Safe threshold", f"{explanation['threshold_mm']} mm")
