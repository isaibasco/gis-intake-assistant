import unittest
from unittest.mock import patch

from modules.config import APP_TAGLINE
from modules.ui import render_copyable_address


class UiTests(unittest.TestCase):
    def test_tagline_uses_updated_product_description(self):
        self.assertEqual(
            APP_TAGLINE,
            "Find and save property research sources for drafting intake.",
        )

    def test_copy_component_is_visible_and_escapes_address(self):
        address = '123 <Main> St, "Example", Colorado'

        with patch("modules.ui.components.html") as component:
            render_copyable_address(address)

        markup = component.call_args.args[0]
        self.assertIn("123 &lt;Main&gt; St", markup)
        self.assertIn('<button class="copy-button"', markup)
        self.assertIn("navigator.clipboard.writeText(address)", markup)
        self.assertNotIn("<Main>", markup)
        self.assertEqual(component.call_args.kwargs["height"], 54)
        self.assertFalse(component.call_args.kwargs["scrolling"])


if __name__ == "__main__":
    unittest.main()
