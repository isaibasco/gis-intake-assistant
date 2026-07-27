"""Address lookup and fallback behavior for the GIS Intake Assistant."""

from geopy.exc import (
    GeocoderRateLimited,
    GeocoderServiceError,
    GeocoderTimedOut,
    GeocoderUnavailable,
)
from geopy.geocoders import Nominatim


RATE_LIMIT_WARNING = (
    "The public address lookup service is rate-limiting requests. "
    "Continuing with city/state only."
)

SERVICE_UNAVAILABLE_WARNING = (
    "The public address lookup service is temporarily unavailable. "
    "Continuing with city/state only."
)


def lookup_location(full_address, entered_state, geolocator=None):
    """Look up an address while preserving the existing city/state fallback."""
    geolocator = geolocator or Nominatim(user_agent="gis_intake_assistant")

    try:
        location = geolocator.geocode(full_address, addressdetails=True, timeout=10)
    except GeocoderRateLimited:
        return {
            "confirmed_address": full_address,
            "county": "",
            "state": entered_state,
            "used_fallback": True,
            "warning": RATE_LIMIT_WARNING,
        }
    except (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError):
        return {
            "confirmed_address": full_address,
            "county": "",
            "state": entered_state,
            "used_fallback": True,
            "warning": SERVICE_UNAVAILABLE_WARNING,
        }

    if location:
        address_data = location.raw.get("address", {})
        return {
            "confirmed_address": location.address,
            "county": address_data.get("county", ""),
            "state": address_data.get("state", entered_state),
            "used_fallback": False,
            "warning": "",
        }

    return {
        "confirmed_address": full_address,
        "county": "",
        "state": entered_state,
        "used_fallback": True,
        "warning": "",
    }
