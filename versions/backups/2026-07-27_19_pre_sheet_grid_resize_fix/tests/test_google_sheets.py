import unittest
from unittest.mock import patch

import pandas as pd

from modules import google_sheets
from modules.config import SCOPES


class FakeWorksheet:
    def __init__(self, records=None, headers=None):
        self.records = records or []
        self.headers = headers or list(google_sheets.SOURCE_COLUMNS)
        self.appended_rows = []
        self.updated_cells = []

    def get_all_records(self):
        return self.records

    def append_row(self, row, value_input_option):
        self.appended_rows.append((row, value_input_option))

    def row_values(self, row_number):
        return self.headers

    def update_cell(self, row, column, value):
        self.updated_cell = (row, column, value)
        self.updated_cells.append((row, column, value))
        if row == 1 and column == len(self.headers) + 1:
            self.headers.append(value)


class GoogleSheetsTests(unittest.TestCase):
    def test_google_client_normalizes_literal_private_key_newlines(self):
        secrets = {
            "gcp_service_account": {
                "private_key": "first line\\nsecond line",
            }
        }

        with (
            patch.object(google_sheets.st, "secrets", secrets),
            patch.object(google_sheets.Credentials, "from_service_account_info") as credentials,
            patch.object(google_sheets.gspread, "authorize", return_value="client") as authorize,
        ):
            credentials.return_value = "credentials"
            client = google_sheets.get_google_client()

        service_account_info = credentials.call_args.args[0]
        self.assertEqual(service_account_info["private_key"], "first line\nsecond line")
        self.assertEqual(credentials.call_args.kwargs["scopes"], SCOPES)
        authorize.assert_called_once_with("credentials")
        self.assertEqual(client, "client")

    def test_load_normalizes_rows_and_filters_inactive_sources(self):
        worksheet = FakeWorksheet(records=[
            {
                "county": " Jefferson County ",
                "state": " Tennessee ",
                "source_type": " Parcel_GIS ",
                "source_name": " County GIS ",
                "source_url": " https://example.gov/gis ",
                "status": " Active ",
            },
            {
                "county": "Jefferson County",
                "state": "Tennessee",
                "source_type": "other",
                "source_name": "Old source",
                "source_url": "https://example.gov/old",
                "status": "inactive",
            },
        ])

        with patch.object(google_sheets, "get_worksheet", return_value=worksheet):
            result = google_sheets.load_gis_portals()

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["county"], "jefferson county")
        self.assertEqual(result.iloc[0]["state"], "tennessee")
        self.assertEqual(result.iloc[0]["source_type"], "parcel_gis")
        self.assertEqual(result.iloc[0]["source_name"], "County GIS")
        self.assertIn("notes", result.columns)
        self.assertIn("city", result.columns)
        self.assertIn("jurisdiction_level", result.columns)

    def test_duplicate_source_is_rejected_without_writing(self):
        saved = pd.DataFrame([
            {
                "county": "jefferson county",
                "state": "tennessee",
                "source_url": "https://example.gov/gis",
            }
        ])

        with (
            patch.object(google_sheets, "load_gis_portals", return_value=saved),
            patch.object(google_sheets, "get_worksheet") as get_worksheet,
        ):
            success, message = google_sheets.save_verified_source(
                county="Jefferson County",
                state="Tennessee",
                source_type="parcel_gis",
                source_name="County GIS",
                source_url="https://example.gov/gis",
            )

        self.assertFalse(success)
        self.assertIn("already saved", message)
        get_worksheet.assert_not_called()

    def test_matching_hierarchy_includes_exact_county_city_and_state(self):
        source_database = pd.DataFrame([
            {
                "county": "mesa county",
                "city": "",
                "state": "colorado",
                "source_url": "https://example.gov/county",
                "status": "active",
                "jurisdiction_level": "",
            },
            {
                "county": "",
                "city": "grand junction",
                "state": "colorado",
                "source_url": "https://example.gov/city",
                "status": "active",
                "jurisdiction_level": "city",
            },
            {
                "county": "",
                "city": "",
                "state": "colorado",
                "source_url": "https://example.gov/state",
                "status": "active",
                "jurisdiction_level": "state",
            },
            {
                "county": "",
                "city": "",
                "state": "colorado",
                "source_url": "https://example.gov/unscoped",
                "status": "active",
                "jurisdiction_level": "",
            },
            {
                "county": "denver county",
                "city": "",
                "state": "colorado",
                "source_url": "https://example.gov/unrelated",
                "status": "active",
                "jurisdiction_level": "county",
            },
        ])

        result = google_sheets.match_sources_for_location(
            source_database,
            city="Grand Junction",
            county="Mesa County",
            state="Colorado",
        )

        self.assertEqual(
            result["source_url"].tolist(),
            [
                "https://example.gov/county",
                "https://example.gov/city",
                "https://example.gov/state",
            ],
        )

    def test_city_source_matches_when_county_is_unavailable(self):
        source_database = pd.DataFrame([{
            "county": "",
            "city": "dandridge",
            "state": "tennessee",
            "source_url": "https://example.gov/city",
            "status": "active",
            "jurisdiction_level": "city",
        }])

        result = google_sheets.match_sources_for_location(
            source_database,
            city="Dandridge",
            county="",
            state="Tennessee",
        )

        self.assertEqual(
            result["source_url"].tolist(),
            ["https://example.gov/city"],
        )

    def test_rejected_urls_are_scoped_to_entered_address(self):
        source_database = pd.DataFrame([
            {
                "county": "jefferson county",
                "state": "tennessee",
                "source_url": "https://example.gov/not-useful",
                "notes": "rejected_address:123 main st, dandridge, tennessee",
                "status": "rejected",
            },
            {
                "county": "jefferson county",
                "state": "tennessee",
                "source_url": "https://example.gov/useful-elsewhere",
                "notes": "rejected_address:456 main st, dandridge, tennessee",
                "status": "rejected",
            },
        ])

        rejected = google_sheets.rejected_urls_for_address(
            source_database,
            " 123 MAIN ST, Dandridge, Tennessee ",
        )

        self.assertEqual(rejected, {"https://example.gov/not-useful"})
        self.assertEqual(
            google_sheets.rejected_urls_for_address(
                source_database,
                "",
            ),
            set(),
        )
        self.assertEqual(
            google_sheets.rejected_sources_for_address(
                source_database,
                "123 Main St, Dandridge, Tennessee",
            ),
            [{
                "source_type": "",
                "source_name": "",
                "source_url": "https://example.gov/not-useful",
            }],
        )

    def test_marking_source_not_useful_appends_rejected_row(self):
        worksheet = FakeWorksheet()
        empty_database = pd.DataFrame(columns=google_sheets.SOURCE_COLUMNS)

        with (
            patch.object(
                google_sheets,
                "load_source_database",
                return_value=empty_database,
            ),
            patch.object(
                google_sheets,
                "get_worksheet",
                return_value=worksheet,
            ),
        ):
            success, message = google_sheets.save_rejected_source(
                county="Jefferson County",
                state="Tennessee",
                source_type="parcel_gis",
                source_name="Unhelpful result",
                source_url="https://example.gov/not-useful",
                full_address="123 Main St, Dandridge, Tennessee",
            )

        self.assertTrue(success)
        self.assertIn("stay hidden", message)
        row, value_input_option = worksheet.appended_rows[0]
        self.assertEqual(row[0], "jefferson county")
        self.assertEqual(row[1], "tennessee")
        self.assertEqual(row[4], "https://example.gov/not-useful")
        self.assertEqual(
            row[5],
            "rejected_address:123 main st, dandridge, tennessee",
        )
        self.assertEqual(row[-1], "rejected")
        self.assertEqual(value_input_option, "USER_ENTERED")

    def test_saving_source_appends_optional_schema_columns(self):
        legacy_headers = google_sheets.SOURCE_COLUMNS[:-2]
        worksheet = FakeWorksheet(headers=list(legacy_headers))
        empty_database = pd.DataFrame(columns=google_sheets.SOURCE_COLUMNS)

        with (
            patch.object(
                google_sheets,
                "load_gis_portals",
                return_value=empty_database,
            ),
            patch.object(
                google_sheets,
                "get_worksheet",
                return_value=worksheet,
            ),
        ):
            success, _ = google_sheets.save_verified_source(
                county="Mesa County",
                city="Grand Junction",
                state="Colorado",
                source_type="parcel_gis",
                source_name="Mesa County GIS",
                source_url="https://example.gov/gis",
                jurisdiction_level="county",
            )

        self.assertTrue(success)
        self.assertEqual(
            worksheet.headers,
            google_sheets.SOURCE_COLUMNS,
        )
        row, _ = worksheet.appended_rows[0]
        self.assertEqual(
            row[worksheet.headers.index("city")],
            "grand junction",
        )
        self.assertEqual(
            row[worksheet.headers.index("jurisdiction_level")],
            "county",
        )

    def test_restoring_source_updates_only_matching_rejection_status(self):
        worksheet = FakeWorksheet(records=[
            {
                "source_url": "https://example.gov/other",
                "notes": "rejected_address:123 main st, dandridge, tennessee",
                "status": "rejected",
            },
            {
                "source_url": "https://example.gov/not-useful",
                "notes": "rejected_address:123 main st, dandridge, tennessee",
                "status": "rejected",
            },
        ])

        with patch.object(
            google_sheets,
            "get_worksheet",
            return_value=worksheet,
        ):
            success, message = google_sheets.restore_rejected_source(
                source_url="https://example.gov/not-useful",
                full_address=" 123 MAIN ST, Dandridge, Tennessee ",
            )

        self.assertTrue(success)
        self.assertIn("appear again", message)
        self.assertEqual(
            worksheet.updated_cell,
            (3, google_sheets.SOURCE_COLUMNS.index("status") + 1, "restored"),
        )


if __name__ == "__main__":
    unittest.main()
