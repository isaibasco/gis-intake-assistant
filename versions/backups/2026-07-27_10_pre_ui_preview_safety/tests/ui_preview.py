"""Local-only visual QA surface for reusable Streamlit UI components."""

import streamlit as st

from modules.config import APP_TAGLINE, APP_TITLE
from modules.ui import (
    apply_styles,
    render_copyable_address,
    render_manual_county_form,
    render_save_source_form,
)


st.set_page_config(page_title=f"{APP_TITLE} UI Preview", layout="wide")
apply_styles()

st.title(APP_TITLE)
st.caption(APP_TAGLINE)
st.caption("Local UI preview — no property lookup is performed.")

left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("Address to Copy into GIS")
    render_copyable_address("123 Main St, Example, Colorado")
    st.caption("Use the visible copy button to copy/paste the address into the GIS search bar.")

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.subheader("County Fallback")
    render_manual_county_form({
        "full_address": "123 Main St, Example, Colorado",
    })

with right_col:
    st.subheader("Save Verified Source")
    render_save_source_form("Example County", "Colorado")
