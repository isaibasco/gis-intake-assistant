import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from ddgs import DDGS
from datetime import datetime


# -----------------------------
# Load saved GIS / zoning sources
# -----------------------------

def load_gis_portals():
    try:
        df = pd.read_csv("gis_portals.csv")

        required_columns = [
            "county",
            "state",
            "source_type",
            "source_name",
            "source_url",
            "notes",
            "last_verified",
        ]

        for column in required_columns:
            if column not in df.columns:
                df[column] = ""

        df["county"] = df["county"].astype(str).str.strip().str.lower()
        df["state"] = df["state"].astype(str).str.strip().str.lower()
        df["source_type"] = df["source_type"].astype(str).str.strip().str.lower()
        df["source_url"] = df["source_url"].astype(str).str.strip()

        return df

    except FileNotFoundError:
        return pd.DataFrame(
            columns=[
                "county",
                "state",
                "source_type",
                "source_name",
                "source_url",
                "notes",
                "last_verified",
            ]
        )


# -----------------------------
# Save verified source
# -----------------------------

def save_verified_source(county, state, source_type, source_name, source_url, notes=""):
    df = load_gis_portals()

    county_key = county.strip().lower()
    state_key = state.strip().lower()
    source_type_key = source_type.strip().lower()
    source_url_clean = source_url.strip()

    duplicate = df[
        (df["county"] == county_key)
        & (df["state"] == state_key)
        & (df["source_url"] == source_url_clean)
    ]

    if not duplicate.empty:
        return False, "This exact source URL is already saved for this county/state."

    new_row = {
        "county": county_key,
        "state": state_key,
        "source_type": source_type_key,
        "source_name": source_name.strip(),
        "source_url": source_url_clean,
        "notes": notes.strip(),
        "last_verified": datetime.now().date().isoformat(),
    }

    updated_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    updated_df.to_csv("gis_portals.csv", index=False)

    return True, "Source saved. Run the lookup again to see it under Saved Sources."


# -----------------------------
# Search helpers
# -----------------------------

def is_bad_result(result):
    href = result.get("href", "").lower()
    title = result.get("title", "").lower()

    blocked_terms = [
        "wikipedia",
        "wikidata",
        "facebook",
        "reddit",
        "linkedin",
        "youtube",
        "zillow",
        "realtor.com",
        "redfin",
        "homes.com",
    ]

    combined = f"{title} {href}"
    return any(term in combined for term in blocked_terms)


def result_matches_place(result, city, county, state):
    title = result.get("title", "").lower()
    href = result.get("href", "").lower()
    body = result.get("body", "").lower()
    combined_text = f"{title} {href} {body}"

    city_key = city.strip().lower()
    county_key = county.strip().lower()
    state_key = state.strip().lower()

    county_short = county_key.replace(" county", "")

    place_terms = [
        city_key,
        county_key,
        county_short,
        state_key,
    ]

    place_terms = [term for term in place_terms if term]

    return any(term in combined_text for term in place_terms)


def search_candidates(query, city, county, state, max_results=3, mode="general"):
    results = []

    try:
        with DDGS() as ddgs:
            search_results = ddgs.text(query, max_results=15)

            for result in search_results:
                if is_bad_result(result):
                    continue

                if not result_matches_place(result, city, county, state):
                    continue

                title = result.get("title", "").lower()
                href = result.get("href", "").lower()
                body = result.get("body", "").lower()
                combined_text = f"{title} {href} {body}"

                if mode == "zoning":
                    must_have_zoning = any(
                        term in combined_text
                        for term in [
                            "zoning",
                            "zone district",
                            "zoning map",
                            "zoning viewer",
                            "zoning ordinance",
                            "land use",
                        ]
                    )
                    must_be_map_or_official = any(
                        term in combined_text
                        for term in [
                            "map",
                            "maps",
                            "viewer",
                            "pdf",
                            "arcgis",
                            "municode",
                            ".gov",
                            "planning",
                        ]
                    )

                    if not (must_have_zoning and must_be_map_or_official):
                        continue

                else:
                    allowed_keywords = [
                        "gis",
                        "parcel",
                        "assessor",
                        "property",
                        "map",
                        "maps",
                        "viewer",
                        "arcgis",
                    ]
                    if not any(keyword in combined_text for keyword in allowed_keywords):
                        continue

                results.append(result)

                if len(results) == max_results:
                    break

    except Exception:
        pass

    return results


def search_general_sources(city, county, state):
    query = f"{county} {state} official GIS parcel viewer"
    return search_candidates(query, city, county, state, max_results=3, mode="general")


def search_zoning_sources(city, county, state):
    queries = [
        f"{city} {state} official zoning map",
        f"{county} {state} official zoning map PDF",
        f"{city} {state} zoning viewer",
        f"{county} {state} zoning ordinance map",
    ]

    results = []
    seen_urls = set()

    for query in queries:
        candidates = search_candidates(query, city, county, state, max_results=3, mode="zoning")
        for candidate in candidates:
            href = candidate.get("href", "")
            if href and href not in seen_urls:
                results.append(candidate)
                seen_urls.add(href)

            if len(results) == 3:
                return results

    return results


# -----------------------------
# Log searches locally
# -----------------------------

def log_search(
    entered_address,
    confirmed_address,
    detected_county,
    detected_state,
    result_type,
    saved_source_count,
    suggested_results_count,
):
    log_row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "entered_address": entered_address,
        "confirmed_address": confirmed_address,
        "detected_county": detected_county,
        "detected_state": detected_state,
        "result_type": result_type,
        "saved_source_count": saved_source_count,
        "suggested_results_count": suggested_results_count,
    }

    try:
        existing_log = pd.read_csv("search_log.csv")
        updated_log = pd.concat([existing_log, pd.DataFrame([log_row])], ignore_index=True)
    except FileNotFoundError:
        updated_log = pd.DataFrame([log_row])

    updated_log.to_csv("search_log.csv", index=False)


# -----------------------------
# Display saved sources by type
# -----------------------------

def display_saved_sources(match):
    source_labels = {
        "parcel_gis": "Parcel / GIS Map",
        "zoning_map": "Zoning Map",
        "assessor": "Assessor / Property Search",
        "zoning_ordinance": "Zoning Ordinance / Code",
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
            st.markdown(f"**{label}**")
            for row in visible_rows:
                st.markdown(f"- [{row['source_name']}]({row['source_url']})")
                displayed_count += 1

    return displayed_count


def has_source_type(match, source_type):
    return not match[match["source_type"] == source_type].empty


# -----------------------------
# Save form UI
# -----------------------------

def render_save_source_form(detected_county, detected_state):
    with st.expander("Save verified source"):
        st.caption("Use this only after you confirm the link is the correct official source.")

        source_type = st.selectbox(
            "Source Type",
            [
                "parcel_gis",
                "zoning_map",
                "assessor",
                "zoning_ordinance",
                "other",
            ],
            key="save_source_type",
        )

        source_name = st.text_input(
            "Source Name",
            placeholder="Example: Lexington County GIS Viewer",
            key="save_source_name",
        )

        source_url = st.text_input(
            "Source URL",
            placeholder="Paste verified source URL here",
            key="save_source_url",
        )

        notes = st.text_input(
            "Notes",
            placeholder="Optional. Example: Official zoning PDF / parcel viewer / assessor search",
            key="save_source_notes",
        )

        if st.button("Save Verified Source", key="save_verified_source_button"):
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


# -----------------------------
# Session state setup
# -----------------------------

if "lookup_result" not in st.session_state:
    st.session_state.lookup_result = None


# -----------------------------
# App UI
# -----------------------------

st.set_page_config(page_title="GIS Intake Assistant", layout="wide")

st.title("GIS Intake Assistant")
st.write("Enter a project address to find the likely GIS / parcel research source.")

project_address = st.text_input("Project Address", placeholder="Example: 123 Main St")
city = st.text_input("City", placeholder="Example: Grand Junction")
state = st.text_input("State", placeholder="Example: Colorado")

full_address = f"{project_address}, {city}, {state}"

if st.button("Find GIS Portal"):
    if not project_address or not city or not state:
        st.error("Please enter the project address, city, and state.")
        st.session_state.lookup_result = None
    else:
        geolocator = Nominatim(user_agent="gis_intake_assistant")

        try:
            location = geolocator.geocode(full_address, addressdetails=True, timeout=10)

            if location:
                confirmed_address = location.address
                address_data = location.raw.get("address", {})
                detected_county = address_data.get("county", "")
                detected_state = address_data.get("state", "")

                county_key = detected_county.strip().lower()
                state_key = detected_state.strip().lower()

                gis_df = load_gis_portals()
                match = gis_df[
                    (gis_df["county"] == county_key)
                    & (gis_df["state"] == state_key)
                ]

                saved_count = 0
                suggested_count = 0
                general_candidates = []
                zoning_candidates = []

                if not match.empty:
                    saved_count = len(match)
                else:
                    general_candidates = search_general_sources(city, detected_county, detected_state)
                    suggested_count += len(general_candidates)

                if match.empty or not has_source_type(match, "zoning_map"):
                    zoning_candidates = search_zoning_sources(city, detected_county, detected_state)
                    suggested_count += len(zoning_candidates)

                st.session_state.lookup_result = {
                    "full_address": full_address,
                    "confirmed_address": confirmed_address,
                    "detected_county": detected_county,
                    "detected_state": detected_state,
                    "match": match,
                    "general_candidates": general_candidates,
                    "zoning_candidates": zoning_candidates,
                    "saved_count": saved_count,
                    "suggested_count": suggested_count,
                }

                log_search(
                    entered_address=full_address,
                    confirmed_address=confirmed_address,
                    detected_county=detected_county,
                    detected_state=detected_state,
                    result_type="completed_lookup",
                    saved_source_count=saved_count,
                    suggested_results_count=suggested_count,
                )

            else:
                st.warning("No address result found. Try simplifying the address.")
                st.session_state.lookup_result = None

        except (GeocoderTimedOut, GeocoderUnavailable):
            st.error("The address lookup service timed out. Try again.")
            st.session_state.lookup_result = None


# -----------------------------
# Render stored lookup result
# -----------------------------

result = st.session_state.lookup_result

if result:
    st.success("Location found.")

    st.subheader("Address to Copy into GIS")
    st.code(result["full_address"])

    st.subheader("Detected Area")
    st.write(f"County: {result['detected_county']}")
    st.write(f"State: {result['detected_state']}")

    st.subheader("Saved Sources")

    match = result["match"]
    if not match.empty:
        displayed_count = display_saved_sources(match)

        if displayed_count == 0:
            st.warning("Saved source rows found, but no valid unique URLs to display.")
    else:
        st.info("No saved sources found for this county/state yet.")

    if match.empty:
        st.subheader("Suggested GIS / Parcel Sources")
        if result["general_candidates"]:
            for i, candidate in enumerate(result["general_candidates"], 1):
                title = candidate.get("title", "Untitled result")
                href = candidate.get("href", "")
                st.markdown(f"**{i}. [{title}]({href})**")
        else:
            query = f"{result['detected_county']} {result['detected_state']} GIS parcel viewer"
            search_query = query.replace(" ", "+")
            google_search = f"https://www.google.com/search?q={search_query}"
            st.markdown(f"[Fallback GIS Search]({google_search})")

    if match.empty or not has_source_type(match, "zoning_map"):
        st.subheader("Suggested Zoning Map Sources")
        if result["zoning_candidates"]:
            for i, candidate in enumerate(result["zoning_candidates"], 1):
                title = candidate.get("title", "Untitled result")
                href = candidate.get("href", "")
                st.markdown(f"**{i}. [{title}]({href})**")
        else:
            query = f"{result['detected_county']} {result['detected_state']} zoning map PDF zoning viewer"
            search_query = query.replace(" ", "+")
            google_search = f"https://www.google.com/search?q={search_query}"
            st.markdown(f"[Fallback Zoning Map Search]({google_search})")

    render_save_source_form(result["detected_county"], result["detected_state"])