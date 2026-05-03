"""Welcome tab tests for EZProto."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from textual.widgets import Button, Checkbox, Input, Select, Static

from ezproto.app import ProtoboardApp
from ezproto.storage import APP_DATA_ENV_VAR_NAME


class WelcomeTabTests(unittest.IsolatedAsyncioTestCase):
    async def test_welcome_view_shows_navigation_frames_without_focusable_widgets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: temp_dir},
                clear=False,
            ):
                app = ProtoboardApp()
                async with app.run_test() as pilot:
                    await pilot.pause()

                    home_button = app.query_one("#nav_home", Button)
                    intro = app.query_one("#welcome_intro", Static)
                    navigation = app.query_one("#welcome_navigation", Static)
                    arrow_navigation = app.query_one("#arrow_navigation", Static)
                    getting_started = app.query_one("#welcome_getting_started", Static)
                    shortcuts = app.query_one("#welcome_shortcuts", Static)

                    self.assertTrue(home_button.has_focus)
                    self.assertIn("keyboard-friendly workspace", str(intro.renderable))
                    self.assertIn("HOME, PROTOBOARD, SETTINGS", str(navigation.renderable))
                    self.assertIn("Use the section buttons above the workspace", str(navigation.renderable))
                    self.assertIn("Tab and Shift+Tab", str(arrow_navigation.renderable))
                    self.assertIn("Enter or Space", str(arrow_navigation.renderable))
                    self.assertIn("Open SETTINGS to review the output folder and theme", str(getting_started.renderable))
                    self.assertIn("Ctrl+G", str(shortcuts.renderable))

                    self.assertEqual(len(list(app.query("#welcome Button"))), 0)
                    self.assertEqual(len(list(app.query("#welcome Input"))), 0)
                    self.assertEqual(len(list(app.query("#welcome Checkbox"))), 0)
                    self.assertEqual(len(list(app.query("#welcome Select"))), 0)

    async def test_settings_view_uses_minimal_workspace_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: temp_dir},
                clear=False,
            ):
                app = ProtoboardApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.click("#nav_settings")
                    await pilot.pause()

                    output_directory = app.query_one("#default_output_directory", Input)
                    theme_select = app.query_one("#theme_select", Select)
                    save_settings = app.query_one("#save_settings", Button)

                    self.assertEqual(output_directory.placeholder, temp_dir)
                    self.assertIsNotNone(theme_select)
                    self.assertEqual(save_settings.label.plain, "Save Settings")
                    self.assertEqual(len(list(app.query("#settings Input"))), 1)
                    self.assertEqual(len(list(app.query("#settings Select"))), 1)
                    self.assertEqual(len(list(app.query("#settings Button"))), 1)

    async def test_settings_save_persists_theme_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: temp_dir},
                clear=False,
            ):
                app = ProtoboardApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.click("#nav_settings")
                    await pilot.pause()

                    theme_select = app.query_one("#theme_select", Select)
                    alternate_theme = next(
                        name
                        for name, _ in app._theme_options()
                        if name != app._default_theme_name()
                    )
                    theme_select.value = alternate_theme

                    await pilot.click("#save_settings")
                    await pilot.pause()

                    self.assertEqual(app.theme, alternate_theme)
                    self.assertIn("Settings saved.", app.query_one("#settings_status", Static).renderable)

    async def test_section_buttons_switch_visible_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: temp_dir},
                clear=False,
            ):
                app = ProtoboardApp()
                async with app.run_test() as pilot:
                    await pilot.pause()

                    welcome = app.query_one("#welcome")
                    protoboard = app.query_one("#protoboard")

                    self.assertFalse(welcome.has_class("hidden"))
                    self.assertTrue(protoboard.has_class("hidden"))

                    await pilot.click("#nav_protoboard")
                    await pilot.pause()

                    self.assertTrue(welcome.has_class("hidden"))
                    self.assertFalse(protoboard.has_class("hidden"))

                    await pilot.click("#nav_settings")
                    await pilot.pause()

                    self.assertTrue(protoboard.has_class("hidden"))
                    self.assertFalse(app.query_one("#settings").has_class("hidden"))


if __name__ == "__main__":
    unittest.main()
