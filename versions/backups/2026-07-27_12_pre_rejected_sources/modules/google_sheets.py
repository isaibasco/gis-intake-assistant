"""Google Sheets persistence for verified sources and search logs."""

from datetime import datetime

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from modules.config import GIS_SOURCES_TAB, SCOPES, SEARCH_LOG_TAB, SHEET_NAME


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


def load_gis_portals():
    try:
        worksheet = get_worksheet(GIS_SOURCES_TAB)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)

        required_columns = [
            "county", "state", "source_type", "source_name", "source_url",
            "notes", "last_verified", "verified_by", "status",
        ]

        for column in required_columns:
            if column not in df.columns:
                df[column] = ""

        df["county"] = df["county"].astype(str).str.strip().str.lower()
        df["state"] = df["state"].astype(str).str.strip().str.lower()
        df["source_type"] = df["source_type"].astype(str).str.strip().str.lower()
        df["source_name"] = df["source_name"].astype(str).str.strip()
        df["source_url"] = df["source_url"].astype(str).str.strip()
        df["notes"] = df["notes"].astype(str).str.strip()
        df["status"] = df["status"].astype(str).str.strip().str.lower()

        return df[df["status"].isin(["", "active"])]

    except Exception as error:
        st.error(f"Could not load GIS source database: {error}")
        return pd.DataFrame(columns=[
            "county", "state", "source_type", "source_name", "source_url",
            "notes", "last_verified", "verified_by", "status",
        ])


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
