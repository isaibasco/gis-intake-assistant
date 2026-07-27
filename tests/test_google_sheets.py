import unittest
from unittest.mock import patch

import pandas as pd

from modules import google_sheets
from modules.config import SCOPES


class FakeWorksheet:
    def __init__(self, records=None):
        self.records = records or []
        self.appended_rows = []

    def get_all_records(self):
        return self.records

    def append_row(self, row, value_input_option):
        self.appended_rows.append((row, value_input_option))


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


if __name__ == "__main__":
    unittest.main()
