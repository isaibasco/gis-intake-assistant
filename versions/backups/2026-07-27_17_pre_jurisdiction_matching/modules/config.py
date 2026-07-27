"""Central configuration values for the GIS Intake Assistant."""

APP_TITLE = "GIS Intake Assistant"
APP_TAGLINE = "Find and save property research sources for drafting intake."

SHEET_NAME = "ED GIS Source Database"
GIS_SOURCES_TAB = "GIS Sources"
SEARCH_LOG_TAB = "Search Log"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SOURCE_TYPES = [
    "parcel_gis",
    "zoning_map",
    "assessor",
    "zoning_ordinance",
    "setback_reference",
    "other",
]
