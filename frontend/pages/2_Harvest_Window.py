import streamlit as st

from components.api_client import fetch_explanation, fetch_harvest_window
from components.explanation_panel import render_explanation_panel
from components.field_selector import render_field_selector
from components.window_card import render_window_card

st.set_page_config(page_title="Harvest Window - HarvestWise", page_icon="🌾", layout="wide")

st.title("Dynamic Harvest Window")
field_id = render_field_selector()

window = fetch_harvest_window(field_id)
explanation = fetch_explanation(field_id)

render_window_card(window)

st.write("")
render_explanation_panel(explanation)
