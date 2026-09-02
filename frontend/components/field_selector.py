import streamlit as st

from components.api_client import fetch_fields


def render_field_selector() -> str:
    """Renders the field picker in the sidebar and returns the selected field_id."""
    fields = fetch_fields()
    labels = [f"{f['name']}  ({f['region']})" for f in fields]
    ids = [f["field_id"] for f in fields]

    if "selected_field_id" not in st.session_state:
        st.session_state.selected_field_id = ids[0]

    default_index = ids.index(st.session_state.selected_field_id) if st.session_state.selected_field_id in ids else 0

    st.sidebar.subheader("Field")
    choice = st.sidebar.selectbox("Select a field", options=labels, index=default_index)
    selected_id = ids[labels.index(choice)]
    st.session_state.selected_field_id = selected_id

    field = fields[ids.index(selected_id)]
    st.sidebar.caption(f"Crop: {field['crop']}  |  Area: {field['area_ha']} ha")

    return selected_id
