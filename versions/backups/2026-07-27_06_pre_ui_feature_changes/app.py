import pandas as pd
import streamlit as st

from modules.config import (
    APP_TAGLINE,
    APP_TITLE,
)
from modules.geocoder import lookup_location
from modules.google_sheets import load_gis_portals, log_search
from modules.search import (
    remove_saved_duplicates,
    search_general_sources,
    search_setback_sources,
    search_zoning_sources,
)
from modules.ui import apply_styles, display_candidates, display_saved_sources, render_save_source_form


if "lookup_result" not in st.session_state:
    st.session_state.lookup_result = None


st.set_page_config(page_title="GIS Intake Assistant", layout="wide")
apply_styles()

st.title(APP_TITLE)
st.caption(APP_TAGLINE)

left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("Project Lookup")

    with st.form("lookup_form"):
        project_address = st.text_input("Project Address", placeholder="Example: 123 Main St")
        city = st.text_input("City", placeholder="Example: Grand Junction")
        state = st.text_input("State", placeholder="Example: Colorado")
        lookup_submitted = st.form_submit_button("Find GIS Portal")

    if lookup_submitted:
        full_address = f"{project_address}, {city}, {state}"

        if not project_address or not city or not state:
            st.error("Please enter the project address, city, and state.")
            st.session_state.lookup_result = None
        else:
            try:
                with st.spinner("Searching public location data..."):
                    location_result = lookup_location(full_address, state)

                geocoder_fallback = location_result["used_fallback"]
                confirmed_address = location_result["confirmed_address"]
                detected_county = location_result["county"]
                detected_state = location_result["state"]

                if location_result["warning"]:
                    st.warning(location_result["warning"])

                county_key = detected_county.strip().lower()
                state_key = detected_state.strip().lower()

                gis_df = load_gis_portals()
                if county_key:
                    match = gis_df[
                        (gis_df["county"] == county_key)
                        & (gis_df["state"] == state_key)
                    ]
                else:
                    match = pd.DataFrame(columns=gis_df.columns)

                with st.spinner("Checking saved sources and discovering additional sources..."):
                    general_candidates = search_general_sources(city, detected_county, detected_state)
                    zoning_candidates = search_zoning_sources(city, detected_county, detected_state)
                    setback_candidates = search_setback_sources(city, detected_county, detected_state)

                    general_candidates = remove_saved_duplicates(general_candidates, match)
                    zoning_candidates = remove_saved_duplicates(zoning_candidates, match)
                    setback_candidates = remove_saved_duplicates(setback_candidates, match)

                saved_count = len(match) if not match.empty else 0
                suggested_count = len(general_candidates) + len(zoning_candidates) + len(setback_candidates)

                st.session_state.lookup_result = {
                    "full_address": full_address,
                    "confirmed_address": confirmed_address,
                    "detected_county": detected_county,
                    "detected_state": detected_state,
                    "match": match,
                    "general_candidates": general_candidates,
                    "zoning_candidates": zoning_candidates,
                    "setback_candidates": setback_candidates,
                    "saved_count": saved_count,
                    "suggested_count": suggested_count,
                }

                log_search(
                    entered_address=full_address,
                    confirmed_address=confirmed_address,
                    detected_county=detected_county,
                    detected_state=detected_state,
                    result_type="completed_lookup_city_state_fallback" if geocoder_fallback else "completed_lookup",
                    saved_source_count=saved_count,
                    suggested_results_count=suggested_count,
                )

            except Exception as error:
                st.error(f"Lookup failed: {error}")
                st.session_state.lookup_result = None


result = st.session_state.lookup_result

with left_col:
    if result:
        st.success("Location found.")

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        st.subheader("Address to Copy into GIS")
        st.code(result["full_address"], language=None)
        st.caption("Use the copy button on hover to copy/paste the address into the GIS search bar.")

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        st.subheader("Suggested Additional Sources")
        st.caption("Saved sources appear on the right. These are additional discovery results to review.")

        st.markdown("**GIS / Parcel Sources**")
        if result["general_candidates"]:
            display_candidates(result["general_candidates"])
        else:
            query = f"{result['detected_county']} {result['detected_state']} GIS parcel viewer"
            search_query = query.replace(" ", "+")
            google_search = f"https://www.google.com/search?q={search_query}"
            st.markdown(f"[Fallback GIS Search]({google_search})")

        st.markdown("<div style='margin-top: 1.4rem;'></div>", unsafe_allow_html=True)

        st.markdown("**Zoning Map Sources**")
        if result["zoning_candidates"]:
            display_candidates(result["zoning_candidates"])
        else:
            query = f"{result['detected_county']} {result['detected_state']} zoning map PDF zoning viewer"
            search_query = query.replace(" ", "+")
            google_search = f"https://www.google.com/search?q={search_query}"
            st.markdown(f"[Fallback Zoning Map Search]({google_search})")

        st.markdown("<div style='margin-top: 1.4rem;'></div>", unsafe_allow_html=True)

        st.markdown("**Zoning Ordinance / Setback Sources**")
        if result["setback_candidates"]:
            display_candidates(result["setback_candidates"])
        else:
            query = f"{result['detected_county']} {result['detected_state']} zoning ordinance setbacks"
            search_query = query.replace(" ", "+")
            google_search = f"https://www.google.com/search?q={search_query}"
            st.markdown(f"[Fallback Setback Search]({google_search})")

        render_save_source_form(result["detected_county"], result["detected_state"])


with right_col:
    st.subheader("Detected Area")

    if result:
        st.write(f"County: {result['detected_county']}")
        st.write(f"State: {result['detected_state']}")
    else:
        st.caption("Run a lookup to detect county and state.")

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.subheader("Saved Sources")

    if result:
        match = result["match"]
        if not match.empty:
            displayed_count = display_saved_sources(match)

            if displayed_count == 0:
                st.warning("Saved source rows found, but no valid unique URLs to display.")
        else:
            st.info("No saved sources found for this county/state yet.")
    else:
        st.caption("Saved sources will appear here after lookup.")

    st.markdown("<div class='feedback-button'>FEEDBACK</div>", unsafe_allow_html=True)
