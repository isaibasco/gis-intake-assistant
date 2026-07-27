import unittest
from unittest.mock import patch

from modules import conditions


class FakeDDGS:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.queries = []

    def text(self, query, max_results):
        self.queries.append((query, max_results))
        if self.error:
            raise self.error
        return self.results

    def close(self):
        return None


class ConditionDiscoveryTests(unittest.TestCase):
    def test_national_screening_sources_remain_when_search_is_unavailable(self):
        with patch.object(
            conditions,
            "DDGS",
            return_value=FakeDDGS(error=RuntimeError("offline")),
        ):
            result = conditions._discover_condition_sources(
                "Grand Junction",
                "Mesa County",
                "Colorado",
            )

        self.assertEqual(len(result), len(conditions.CONDITION_SPECS))
        flood = next(item for item in result if item["key"] == "flood")
        self.assertEqual(
            flood["sources"][0]["source_name"],
            "FEMA Flood Map Service Center",
        )
        self.assertEqual(
            flood["sources"][0]["status"],
            "Needs verification",
        )
        overlay = next(item for item in result if item["key"] == "overlay")
        self.assertEqual(overlay["sources"], [])

    def test_only_matching_government_result_is_added_as_local_source(self):
        results = [
            {
                "title": "Mesa County Floodplain Map",
                "href": "https://gis.mesacounty.us/floodplain",
                "body": "Official flood map for Mesa County",
            },
            {
                "title": "Mesa County flood advice",
                "href": "https://commercial.example.com/flood",
                "body": "Mesa County flood information",
            },
            {
                "title": "Denver Floodplain Map",
                "href": "https://denvergov.org/floodplain",
                "body": "Official flood map for Denver",
            },
        ]

        with patch.object(
            conditions,
            "DDGS",
            return_value=FakeDDGS(results=results),
        ):
            result = conditions._discover_condition_sources(
                "Grand Junction",
                "Mesa County",
                "Colorado",
            )

        flood = next(item for item in result if item["key"] == "flood")
        self.assertEqual(
            flood["sources"][0]["source_url"],
            "https://gis.mesacounty.us/floodplain",
        )
        self.assertEqual(flood["sources"][0]["status"], "Source found")
        self.assertEqual(len(flood["sources"]), 2)


if __name__ == "__main__":
    unittest.main()
