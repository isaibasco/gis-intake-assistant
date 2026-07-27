import unittest
from unittest.mock import patch

from modules.config import APP_TAGLINE
from modules import ui
from modules.ui import render_copyable_address


class UiTests(unittest.TestCase):
    def test_tagline_uses_updated_product_description(self):
        self.assertEqual(
            APP_TAGLINE,
            "Find and save property research sources for drafting intake.",
        )

    def test_copy_component_is_visible_and_escapes_address(self):
        address = '123 <Main> St, "Example", Colorado'

        with patch("modules.ui.st.iframe") as component:
            render_copyable_address(address)

        markup = component.call_args.args[0]
        self.assertIn("123 &lt;Main&gt; St", markup)
        self.assertIn('<button class="copy-button"', markup)
        self.assertIn("navigator.clipboard.writeText(address)", markup)
        self.assertNotIn("<Main>", markup)
        self.assertEqual(component.call_args.kwargs["height"], 54)
        self.assertEqual(component.call_args.kwargs["width"], "stretch")

    def test_not_useful_removes_candidate_after_persistent_save(self):
        state = {
            "lookup_result": {
                "general_candidates": [
                    {"title": "Result", "href": "https://example.gov/result"},
                ],
                "zoning_candidates": [
                    {"title": "Duplicate", "href": "https://example.gov/result"},
                ],
                "setback_candidates": [],
            }
        }

        with (
            patch.object(ui.st, "session_state", state),
            patch.object(
                ui,
                "save_rejected_source",
                return_value=(True, "Marked not useful."),
            ) as save_rejected,
        ):
            ui._mark_candidate_not_useful(
                "https://example.gov/result",
                "Result",
                "Example County",
                "Colorado",
                "parcel_gis",
                "123 Main St, Example, Colorado",
            )

        save_rejected.assert_called_once()
        self.assertEqual(state["lookup_result"]["general_candidates"], [])
        self.assertEqual(state["lookup_result"]["zoning_candidates"], [])
        self.assertEqual(
            state["candidate_feedback"],
            ("success", "Marked not useful."),
        )

    def test_not_useful_persists_by_address_without_county(self):
        state = {
            "lookup_result": {
                "general_candidates": [
                    {"title": "Result", "href": "https://example.gov/result"},
                ],
                "zoning_candidates": [],
                "setback_candidates": [],
            }
        }

        with (
            patch.object(ui.st, "session_state", state),
            patch.object(
                ui,
                "save_rejected_source",
                return_value=(True, "Marked not useful."),
            ) as save_rejected,
        ):
            ui._mark_candidate_not_useful(
                "https://example.gov/result",
                "Result",
                "",
                "Colorado",
                "parcel_gis",
                "123 Main St, Example, Colorado",
            )

        save_rejected.assert_called_once_with(
            county="",
            state="Colorado",
            source_type="parcel_gis",
            source_name="Result",
            source_url="https://example.gov/result",
            full_address="123 Main St, Example, Colorado",
        )
        self.assertEqual(state["lookup_result"]["general_candidates"], [])


if __name__ == "__main__":
    unittest.main()
