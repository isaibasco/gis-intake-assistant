"""Local-only visual QA surface for reusable Streamlit UI components."""

import streamlit as st

from modules import ui
from modules.config import APP_TAGLINE, APP_TITLE
from modules.ui import (
    apply_styles,
    display_candidate_feedback,
    display_candidates,
    render_copyable_address,
    render_manual_county_form,
    render_rejected_sources,
    render_save_source_form,
)


def preview_save_source(**source):
    """Simulate saving so the preview can never write to Google Sheets."""
    return True, f"Preview only: {source['source_name']} was not saved."


def preview_restore_source(**source):
    """Simulate restoring so the preview can never write to Google Sheets."""
    return True, "Preview only: the source was restored without writing data."


ui.save_verified_source = preview_save_source
ui.save_rejected_source = preview_save_source
ui.restore_rejected_source = preview_restore_source

if "lookup_result" not in st.session_state:
    st.session_state.lookup_result = {
        "general_candidates": [
            {
                "title": "Example County GIS Result",
                "href": "https://example.gov/gis-result",
            },
        ],
        "zoning_candidates": [],
        "setback_candidates": [],
        "rejected_sources": [
            {
                "source_type": "zoning_map",
                "source_name": "Example hidden zoning result",
                "source_url": "https://example.gov/hidden-zoning",
            },
        ],
    }

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
    st.subheader("Suggested Result Controls")
    display_candidate_feedback()
    display_candidates(
        st.session_state.lookup_result["general_candidates"],
        "Example County",
        "Colorado",
        "parcel_gis",
        "123 Main St, Example, Colorado",
    )
    render_rejected_sources(
        st.session_state.lookup_result["rejected_sources"],
        "123 Main St, Example, Colorado",
    )

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.subheader("Save Verified Source")
    st.caption("Preview mode: Save Source is simulated and does not write data.")
    render_save_source_form("Example County", "Colorado")
