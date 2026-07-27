import pandas as pd
import streamlit as st

from modules.config import (
    APP_TAGLINE,
    APP_TITLE,
    SOURCE_TYPES,
)
from modules.geocoder import lookup_location
from modules.google_sheets import load_gis_portals, log_search, save_verified_source
from modules.search import (
    remove_saved_duplicates,
    search_general_sources,
    search_setback_sources,
    search_zoning_sources,
)


# -----------------------------
# Display helpers
# -----------------------------

def display_saved_sources(match):
    source_labels = {
        "parcel_gis": "Parcel / GIS Map",
        "zoning_map": "Zoning Map",
        "assessor": "Assessor / Property Search",
        "zoning_ordinance": "Zoning Ordinance / Code",
        "setback_reference": "Setback Reference",
        "other": "Other Source",
    }

    displayed_urls = set()
    displayed_count = 0

    for source_type, label in source_labels.items():
        group = match[match["source_type"] == source_type]

        visible_rows = []
        for _, row in group.iterrows():
            url = str(row["source_url"]).strip()

            if not url or url.lower() == "nan":
                continue

            if url in displayed_urls:
                continue

            visible_rows.append(row)
            displayed_urls.add(url)

        if visible_rows:
            st.markdown(f"<div class='source-label'>{label}</div>", unsafe_allow_html=True)
            for _, row in group.iterrows():
                url = str(row["source_url"]).strip()
                if not url or url.lower() == "nan" or url not in displayed_urls:
                    continue
                st.markdown(
                    f"<div class='source-link'>↳ <a href='{row['source_url']}' target='_blank'>{row['source_name']}</a></div>",
                    unsafe_allow_html=True,
                )
                notes = str(row.get("notes", "")).strip()
                if notes and notes.lower() != "nan":
                    st.markdown(
                        f"<div class='source-note'>{notes}</div>",
                        unsafe_allow_html=True,
                    )
                displayed_count += 1
            displayed_urls = set(displayed_urls)

    return displayed_count


def display_candidates(candidates):
    if candidates:
        for i, candidate in enumerate(candidates, 1):
            title = candidate.get("title", "Untitled result")
            href = candidate.get("href", "")
            st.markdown(
                f"<div class='candidate-link'>{i}. <a href='{href}' target='_blank'>{title}</a></div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No high-confidence suggestions found. Use fallback search if needed.")


# -----------------------------
# Save form UI
# -----------------------------

def render_save_source_form(detected_county, detected_state):
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    with st.expander("＋ Save verified source", expanded=False):
        st.caption("Save only after confirming the link is official and useful.")

        with st.form("save_verified_source_form", clear_on_submit=True):
            source_type = st.selectbox(
                "Source Type",
                SOURCE_TYPES,
            )

            source_name = st.text_input(
                "Source Name",
                placeholder="Example: Lexington County GIS Viewer",
            )

            source_url = st.text_input(
                "Source URL",
                placeholder="Paste verified source URL here",
            )

            notes = st.text_input(
                "Notes",
                placeholder="Optional. Example: Official zoning PDF / parcel viewer / assessor search",
            )

            submitted = st.form_submit_button("Save Source")

            if submitted:
                if not source_name or not source_url:
                    st.error("Please enter both source name and source URL.")
                else:
                    saved, message = save_verified_source(
                        county=detected_county,
                        state=detected_state,
                        source_type=source_type,
                        source_name=source_name,
                        source_url=source_url,
                        notes=notes,
                    )

                    if saved:
                        st.success(message)
                    else:
                        st.warning(message)


if "lookup_result" not in st.session_state:
    st.session_state.lookup_result = None


st.set_page_config(page_title="GIS Intake Assistant", layout="wide")

st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

    <style>
    html, body, [data-testid="stAppViewContainer"], h1, h2, h3, h4, h5, h6,
    p, label, div[data-testid="stMarkdownContainer"],
    input, textarea, button, a {
        font-family: 'IBM Plex Mono', monospace !important;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 4rem;
        padding-left: 4rem;
        padding-right: 4rem;
        max-width: none;
    }

    h1 {
        font-size: 2.45rem;
        letter-spacing: -0.04em;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }

    h2 {
        font-size: 1.75rem;
        font-weight: 700;
        letter-spacing: -0.03em;
    }

    h3 {
        font-size: 1.15rem;
        font-weight: 700;
    }

    p, .stCaption {
        font-size: 0.95rem;
    }

    div.stButton > button,
    div.stFormSubmitButton > button {
        border: 1px solid #ff9b42;
        background: #11131a;
        color: #ffffff;
        padding: 0.62rem 1.2rem;
        border-radius: 8px;
        font-weight: 600;
    }

    div.stButton > button:hover,
    div.stFormSubmitButton > button:hover {
        border-color: #ffb86b;
        color: #ffb86b;
    }

    .section-divider {
        border-top: 1px solid rgba(255, 255, 255, 0.16);
        margin: 2rem 0 1.75rem 0;
    }

    .source-label {
        font-weight: 700;
        margin-top: 1rem;
        margin-bottom: 0.35rem;
        color: #ffffff;
        font-size: 1rem;
    }

    .source-link,
    .candidate-link {
        padding: 0.25rem 0;
        font-size: 0.95rem;
        line-height: 1.55;
    }

    .source-note {
        opacity: 0.72;
        font-size: 0.82rem;
        margin-left: 1rem;
        margin-bottom: 0.45rem;
        line-height: 1.45;
    }

    div[data-testid="stExpander"] details {
        border: 1px solid rgba(49, 205, 93, 0.78) !important;
        border-radius: 8px !important;
        background: rgba(255, 255, 255, 0.012);
    }

    div[data-testid="stExpander"] summary {
        font-weight: 600;
    }

    .feedback-button {
        position: fixed;
        right: 2.25rem;
        bottom: 1.75rem;
        z-index: 999;
        border: 1px solid #6ea8ff;
        color: #dce9ff;
        background: #11131a;
        padding: 0.6rem 1.2rem;
        border-radius: 4px;
        text-align: center;
        width: 180px;
        font-size: 0.78rem;
        letter-spacing: 0.08em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
