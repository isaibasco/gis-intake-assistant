import unittest

from geopy.exc import GeocoderRateLimited, GeocoderTimedOut

from modules.geocoder import (
    RATE_LIMIT_WARNING,
    SERVICE_UNAVAILABLE_WARNING,
    lookup_location,
)


class FakeLocation:
    address = "2355 Wild Pear Trail, Dandridge, Tennessee"
    raw = {
        "address": {
            "county": "Jefferson County",
            "state": "Tennessee",
        }
    }


class FakeGeolocator:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def geocode(self, full_address, addressdetails, timeout):
        if self.error:
            raise self.error
        return self.result


class LookupLocationTests(unittest.TestCase):
    def test_successful_lookup_returns_detected_location(self):
        result = lookup_location(
            "2355 Wild Pear Trail, Dandridge, Tennessee",
            "Tennessee",
            geolocator=FakeGeolocator(result=FakeLocation()),
        )

        self.assertEqual(result["confirmed_address"], FakeLocation.address)
        self.assertEqual(result["county"], "Jefferson County")
        self.assertEqual(result["state"], "Tennessee")
        self.assertFalse(result["used_fallback"])
        self.assertEqual(result["warning"], "")

    def test_rate_limit_preserves_city_state_fallback(self):
        full_address = "2355 Wild Pear Trail, Dandridge, Tennessee"
        result = lookup_location(
            full_address,
            "Tennessee",
            geolocator=FakeGeolocator(error=GeocoderRateLimited("rate limited")),
        )

        self.assertEqual(result["confirmed_address"], full_address)
        self.assertEqual(result["county"], "")
        self.assertEqual(result["state"], "Tennessee")
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["warning"], RATE_LIMIT_WARNING)

    def test_service_error_preserves_city_state_fallback(self):
        result = lookup_location(
            "123 Main St, Example, Colorado",
            "Colorado",
            geolocator=FakeGeolocator(error=GeocoderTimedOut("timed out")),
        )

        self.assertEqual(result["county"], "")
        self.assertEqual(result["state"], "Colorado")
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["warning"], SERVICE_UNAVAILABLE_WARNING)

    def test_no_result_uses_silent_existing_fallback(self):
        result = lookup_location(
            "123 Main St, Example, Colorado",
            "Colorado",
            geolocator=FakeGeolocator(result=None),
        )

        self.assertEqual(result["county"], "")
        self.assertEqual(result["state"], "Colorado")
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["warning"], "")


if __name__ == "__main__":
    unittest.main()
