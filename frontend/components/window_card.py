from datetime import date

import streamlit as st


def render_window_card(window: dict):
    start = date.fromisoformat(window["window_start"])
    end = date.fromisoformat(window["window_end"])
    confidence_pct = round(window["confidence"] * 100)

    if confidence_pct >= 80:
        badge_color = "#2F6E5C"
    elif confidence_pct >= 60:
        badge_color = "#C88A2E"
    else:
        badge_color = "#B3452C"

    st.markdown(
        f"""
        <div style="border:1px solid #D8DED3; border-radius:10px; padding:20px 24px; background:#FBFBF8;">
            <div style="font-size:13px; letter-spacing:0.05em; text-transform:uppercase; color:#4B5A4E;">
                Recommended harvest window
            </div>
            <div style="font-size:28px; font-weight:600; color:#1E2A22; margin-top:4px;">
                {start.strftime('%b %d')} &ndash; {end.strftime('%b %d, %Y')}
            </div>
            <div style="margin-top:10px; display:flex; gap:10px; align-items:center;">
                <span style="background:{badge_color}; color:white; padding:3px 10px; border-radius:999px; font-size:13px;">
                    {confidence_pct}% confidence
                </span>
                <span style="color:#4B5A4E; font-size:13px;">via {window['recommended_by']}</span>
            </div>
            <div style="margin-top:12px; color:#1E2A22; font-size:14px;">
                Expected yield at recommended window: <b>{window['expected_yield_t_ha']} t/ha</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
