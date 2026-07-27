import unittest
from unittest.mock import patch

import pandas as pd

from modules.search import (
    is_bad_result,
    remove_saved_duplicates,
    result_matches_place,
    search_candidates,
)


class FakeDDGS:
    def __init__(self, results):
        self.results = results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def text(self, query, max_results):
        return self.results


class SearchHelperTests(unittest.TestCase):
    def test_blocks_known_low_value_sources(self):
        self.assertTrue(
            is_bad_result({
                "title": "County property discussion",
                "href": "https://www.reddit.com/example",
            })
        )

    def test_result_must_reference_the_place(self):
        result = {
            "title": "Jefferson County GIS",
            "href": "https://example.gov/gis",
            "body": "Official parcel viewer for Tennessee",
        }

        self.assertTrue(result_matches_place(result, "Dandridge", "Jefferson County", "Tennessee"))
        self.assertFalse(result_matches_place(result, "Denver", "Denver County", "Colorado"))

    def test_general_search_keeps_matching_gis_result(self):
        results = [
            {
                "title": "Unrelated page",
                "href": "https://example.com/page",
                "body": "No relevant location",
            },
            {
                "title": "Jefferson County GIS Parcel Viewer",
                "href": "https://jeffersoncountytn.gov/gis",
                "body": "Official Tennessee property map",
            },
        ]

        with patch("modules.search.DDGS", return_value=FakeDDGS(results)):
            candidates = search_candidates(
                "Jefferson County Tennessee official GIS parcel viewer",
                "Dandridge",
                "Jefferson County",
                "Tennessee",
            )

        self.assertEqual(candidates, [results[1]])

    def test_saved_urls_are_removed_from_candidates(self):
        candidates = [
            {"href": "https://example.gov/saved"},
            {"href": "https://example.gov/new"},
        ]
        saved = pd.DataFrame([
            {"source_url": "https://example.gov/saved"},
        ])

        self.assertEqual(
            remove_saved_duplicates(candidates, saved),
            [{"href": "https://example.gov/new"}],
        )


if __name__ == "__main__":
    unittest.main()
