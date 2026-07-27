import unittest
from unittest.mock import patch

from modules import ui
from modules.source_names import (
    _is_safe_public_url,
    choose_source_name,
    name_from_url,
)


class SourceNameTests(unittest.TestCase):
    def test_gis_domain_produces_readable_name(self):
        self.assertEqual(
            name_from_url("https://gis.mesacounty.us/viewer"),
            "Mesa County GIS",
        )

    def test_municode_path_identifies_jurisdiction_and_code(self):
        self.assertEqual(
            name_from_url(
                "https://library.municode.com/mo/kansas_city/codes/code_of_ordinances"
            ),
            "Kansas City Code of Ordinances",
        )

    def test_html_title_has_priority_over_open_graph_and_url(self):
        self.assertEqual(
            choose_source_name(
                "https://gis.mesacounty.us",
                html_title="Mesa County Mapping Portal",
                open_graph_title="Mesa County GIS",
            ),
            "Mesa County Mapping Portal",
        )

    def test_local_urls_are_not_fetched(self):
        self.assertFalse(_is_safe_public_url("http://127.0.0.1/private"))
        self.assertFalse(_is_safe_public_url("http://localhost/private"))

    def test_url_change_populates_empty_name(self):
        state = {
            "save_source_url": "https://gis.mesacounty.us/viewer",
            "save_source_name": "",
            "last_auto_source_name": "",
        }

        with (
            patch.object(ui.st, "session_state", state),
            patch.object(ui, "suggest_source_name", return_value="Mesa County GIS"),
        ):
            ui._handle_source_url_change()

        self.assertEqual(state["save_source_name"], "Mesa County GIS")
        self.assertEqual(state["last_auto_source_name"], "Mesa County GIS")

    def test_url_change_does_not_overwrite_user_edited_name(self):
        state = {
            "save_source_url": "https://example.gov/new",
            "save_source_name": "My Reviewed Source Name",
            "last_auto_source_name": "Previous Automatic Name",
        }

        with (
            patch.object(ui.st, "session_state", state),
            patch.object(ui, "suggest_source_name") as suggest,
        ):
            ui._handle_source_url_change()

        self.assertEqual(state["save_source_name"], "My Reviewed Source Name")
        suggest.assert_not_called()


if __name__ == "__main__":
    unittest.main()
