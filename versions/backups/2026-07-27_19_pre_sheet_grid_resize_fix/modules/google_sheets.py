"""Google Sheets persistence for verified sources and search logs."""

from datetime import datetime

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from modules.config import (
    GIS_SOURCES_TAB,
    JURISDICTION_LEVELS,
    SCOPES,
    SEARCH_LOG_TAB,
    SHEET_NAME,
)


SOURCE_COLUMNS = [
    "county",
    "state",
    "source_type",
    "source_name",
    "source_url",
    "notes",
    "last_verified",
    "verified_by",
    "status",
    "city",
    "jurisdiction_level",
]


def get_google_client():
    service_account_info = dict(st.secrets["gcp_service_account"])

    # Streamlit secrets may store private_key with literal "\\n" characters.
    # Normalize them so Google auth can read the PEM key reliably.
    if "private_key" in service_account_info:
        service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def get_worksheet(tab_name):
    client = get_google_client()
    sheet = client.open(SHEET_NAME)
    return sheet.worksheet(tab_name)


def ensure_source_schema(worksheet):
    """Append optional source columns without reordering existing sheet data."""
    headers = [str(header).strip() for header in worksheet.row_values(1)]
    normalized_headers = [header.lower() for header in headers]

    for column in SOURCE_COLUMNS:
        if column not in normalized_headers:
            worksheet.update_cell(1, len(headers) + 1, column)
            headers.append(column)
            normalized_headers.append(column)

    return headers


def load_source_database():
    """Load and normalize active and rejected source rows."""
    try:
        worksheet = get_worksheet(GIS_SOURCES_TAB)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)

        for column in SOURCE_COLUMNS:
            if column not in df.columns:
                df[column] = ""

        df["county"] = df["county"].astype(str).str.strip().str.lower()
        df["city"] = df["city"].astype(str).str.strip().str.lower()
        df["state"] = df["state"].astype(str).str.strip().str.lower()
        df["source_type"] = df["source_type"].astype(str).str.strip().str.lower()
        df["source_name"] = df["source_name"].astype(str).str.strip()
        df["source_url"] = df["source_url"].astype(str).str.strip()
        df["notes"] = df["notes"].astype(str).str.strip()
        df["status"] = df["status"].astype(str).str.strip().str.lower()
        df["jurisdiction_level"] = (
            df["jurisdiction_level"].astype(str).str.strip().str.lower()
        )

        return df

    except Exception as error:
        st.error(f"Could not load GIS source database: {error}")
        return pd.DataFrame(columns=SOURCE_COLUMNS)


def filter_active_sources(source_database):
    return source_database[source_database["status"].isin(["", "active"])]


def _normalize_source_database(source_database):
    normalized = source_database.copy()
    for column in SOURCE_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    for column in (
        "county",
        "city",
        "state",
        "source_type",
        "status",
        "jurisdiction_level",
    ):
        normalized[column] = (
            normalized[column].astype(str).str.strip().str.lower()
        )
    normalized["source_url"] = normalized["source_url"].astype(str).str.strip()

    inferred_levels = normalized["jurisdiction_level"].copy()
    blank_level = inferred_levels == ""
    inferred_levels.loc[blank_level & (normalized["county"] != "")] = "county"
    inferred_levels.loc[
        blank_level
        & (normalized["county"] == "")
        & (normalized["city"] != "")
    ] = "city"
    inferred_levels.loc[inferred_levels == ""] = "unknown"
    normalized["jurisdiction_level"] = inferred_levels
    return normalized


def match_sources_for_location(source_database, city, county, state):
    """Match verified sources by county, then city, then explicit state scope."""
    normalized = _normalize_source_database(source_database)
    active = filter_active_sources(normalized)

    city_key = city.strip().lower()
    county_key = county.strip().lower()
    state_key = state.strip().lower()
    if not state_key:
        return active.iloc[0:0].copy()

    state_rows = active[active["state"] == state_key]
    matches = []

    if county_key:
        matches.append(
            state_rows[
                (state_rows["jurisdiction_level"] == "county")
                & (state_rows["county"] == county_key)
            ]
        )
    if city_key:
        matches.append(
            state_rows[
                (state_rows["jurisdiction_level"] == "city")
                & (state_rows["city"] == city_key)
            ]
        )

    matches.append(
        state_rows[state_rows["jurisdiction_level"] == "state"]
    )
    combined = pd.concat(matches, ignore_index=False)
    return combined.drop_duplicates(subset=["source_url"], keep="first")


def _rejection_scope_note(full_address):
    normalized_address = " ".join(full_address.lower().split())
    return f"rejected_address:{normalized_address}"


def rejected_sources_for_address(source_database, full_address):
    """Return unique rejected source details for one normalized entered address."""
    scope_note = _rejection_scope_note(full_address)
    if scope_note == "rejected_address:":
        return []

    rejected = source_database[
        (source_database["notes"] == scope_note)
        & (source_database["status"] == "rejected")
    ].copy()
    for column in ("source_type", "source_name"):
        if column not in rejected.columns:
            rejected[column] = ""

    rejected = rejected[rejected["source_url"].astype(str).str.strip() != ""]
    rejected = rejected.drop_duplicates(subset=["source_url"], keep="last")

    return rejected[
        ["source_type", "source_name", "source_url"]
    ].to_dict("records")


def rejected_urls_for_address(source_database, full_address):
    return {
        source["source_url"].strip()
        for source in rejected_sources_for_address(source_database, full_address)
    }


def load_gis_portals():
    return filter_active_sources(load_source_database())


def save_verified_source(
    county,
    state,
    source_type,
    source_name,
    source_url,
    notes="",
    city="",
    jurisdiction_level="",
):
    df = load_gis_portals()

    county_key = county.strip().lower()
    city_key = city.strip().lower()
    state_key = state.strip().lower()
    source_type_key = source_type.strip().lower()
    source_url_clean = source_url.strip()
    jurisdiction_level_key = jurisdiction_level.strip().lower()

    if jurisdiction_level_key not in JURISDICTION_LEVELS:
        if county_key:
            jurisdiction_level_key = "county"
        elif city_key:
            jurisdiction_level_key = "city"
        else:
            jurisdiction_level_key = "unknown"

    location_sources = match_sources_for_location(
        df,
        city=city_key,
        county=county_key,
        state=state_key,
    )
    duplicate = location_sources[
        location_sources["source_url"] == source_url_clean
    ]

    if not duplicate.empty:
        return False, "This exact source URL is already saved for this jurisdiction."

    row_values = {
        "county": county_key,
        "state": state_key,
        "source_type": source_type_key,
        "source_name": source_name.strip(),
        "source_url": source_url_clean,
        "notes": notes.strip(),
        "last_verified": datetime.now().date().isoformat(),
        "verified_by": "local_user",
        "status": "active",
        "city": city_key,
        "jurisdiction_level": jurisdiction_level_key,
    }

    try:
        worksheet = get_worksheet(GIS_SOURCES_TAB)
        headers = ensure_source_schema(worksheet)
        row = [
            row_values.get(str(header).strip().lower(), "")
            for header in headers
        ]
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        return (
            True,
            "Source saved to Google Sheets. Run lookup again to refresh Saved Sources.",
        )
    except Exception as error:
        return False, f"Could not save source: {error}"


def save_rejected_source(
    county,
    state,
    source_type,
    source_name,
    source_url,
    full_address,
):
    """Persist an address-scoped rejected URL using the existing sheet schema."""
    county_key = county.strip().lower()
    state_key = state.strip().lower()
    source_url_clean = source_url.strip()
    scope_note = _rejection_scope_note(full_address)

    if scope_note == "rejected_address:":
        return False, "An entered address is required to persist a rejected source."

    source_database = load_source_database()
    duplicate = source_database[
        (source_database["source_url"] == source_url_clean)
        & (source_database["notes"] == scope_note)
        & (source_database["status"] == "rejected")
    ]
    if not duplicate.empty:
        return True, "This source was already marked not useful for this address."

    row = [
        county_key,
        state_key,
        source_type.strip().lower(),
        source_name.strip(),
        source_url_clean,
        scope_note,
        datetime.now().date().isoformat(),
        "local_user",
        "rejected",
    ]

    try:
        worksheet = get_worksheet(GIS_SOURCES_TAB)
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        return True, "Marked not useful. This URL will stay hidden for this address."
    except Exception as error:
        return False, f"Could not mark this source as not useful: {error}"


def restore_rejected_source(source_url, full_address):
    """Restore one address-scoped rejection without deleting its history row."""
    source_url_clean = source_url.strip()
    scope_note = _rejection_scope_note(full_address)

    if not source_url_clean or scope_note == "rejected_address:":
        return False, "A source URL and entered address are required to restore this source."

    try:
        worksheet = get_worksheet(GIS_SOURCES_TAB)
        records = worksheet.get_all_records()
        headers = worksheet.row_values(1)
        status_column = headers.index("status") + 1

        for sheet_row, record in enumerate(records, start=2):
            if (
                str(record.get("source_url", "")).strip() == source_url_clean
                and str(record.get("notes", "")).strip() == scope_note
                and str(record.get("status", "")).strip().lower() == "rejected"
            ):
                worksheet.update_cell(sheet_row, status_column, "restored")
                return (
                    True,
                    "Restored. This URL can appear again for this address.",
                )

        return False, "This source is no longer marked not useful for this address."
    except Exception as error:
        return False, f"Could not restore this source: {error}"


def log_search(
    entered_address,
    confirmed_address,
    detected_county,
    detected_state,
    result_type,
    saved_source_count,
    suggested_results_count,
):
    row = [
        datetime.now().isoformat(timespec="seconds"),
        entered_address,
        confirmed_address,
        detected_county,
        detected_state,
        result_type,
        saved_source_count,
        suggested_results_count,
    ]

    try:
        worksheet = get_worksheet(SEARCH_LOG_TAB)
        worksheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception as error:
        st.warning(f"Lookup worked, but search log was not saved: {error}")
