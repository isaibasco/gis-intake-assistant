"""Google Sheets persistence for verified sources and search logs."""

from datetime import datetime

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from modules.config import GIS_SOURCES_TAB, SCOPES, SEARCH_LOG_TAB, SHEET_NAME


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
        df["state"] = df["state"].astype(str).str.strip().str.lower()
        df["source_type"] = df["source_type"].astype(str).str.strip().str.lower()
        df["source_name"] = df["source_name"].astype(str).str.strip()
        df["source_url"] = df["source_url"].astype(str).str.strip()
        df["notes"] = df["notes"].astype(str).str.strip()
        df["status"] = df["status"].astype(str).str.strip().str.lower()

        return df

    except Exception as error:
        st.error(f"Could not load GIS source database: {error}")
        return pd.DataFrame(columns=SOURCE_COLUMNS)


def filter_active_sources(source_database):
    return source_database[source_database["status"].isin(["", "active"])]


def _rejection_scope_note(full_address):
    normalized_address = " ".join(full_address.lower().split())
    return f"rejected_address:{normalized_address}"


def rejected_urls_for_address(source_database, full_address):
    scope_note = _rejection_scope_note(full_address)
    if scope_note == "rejected_address:":
        return set()

    rejected = source_database[
        (source_database["notes"] == scope_note)
        & (source_database["status"] == "rejected")
    ]
    return set(rejected["source_url"].astype(str).str.strip())


def load_gis_portals():
    return filter_active_sources(load_source_database())


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

    row = [
        county_key,
        state_key,
        source_type_key,
        source_name.strip(),
        source_url_clean,
        notes.strip(),
        datetime.now().date().isoformat(),
        "local_user",
        "active",
    ]

    try:
        worksheet = get_worksheet(GIS_SOURCES_TAB)
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        return True, "Source saved to Google Sheets. Run lookup again to refresh Saved Sources."
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
