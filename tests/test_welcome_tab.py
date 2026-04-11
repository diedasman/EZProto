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
    async def test_welcome_tab_shows_navigation_frames_without_focusable_widgets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: temp_dir},
                clear=False,
            ):
                app = ProtoboardApp()
                async with app.run_test() as pilot:
                    await pilot.pause()

                    intro = app.query_one("#welcome_intro", Static)
                    navigation = app.query_one("#welcome_navigation", Static)
                    arrow_navigation = app.query_one("#arrow_navigation", Static)
                    getting_started = app.query_one("#welcome_getting_started", Static)
                    shortcuts = app.query_one("#welcome_shortcuts", Static)

                    self.assertIn("keyboard-friendly workspace", str(intro.renderable))
                    self.assertIn("+---------------+", str(navigation.renderable))
                    self.assertIn("+-------+   +-------+", str(arrow_navigation.renderable))
                    self.assertIn("Left and Right arrow keys", str(arrow_navigation.renderable))
                    self.assertIn("Open SETTINGS first", str(getting_started.renderable))
                    self.assertIn("Ctrl+G", str(shortcuts.renderable))

                    self.assertEqual(len(list(app.query("#welcome Button"))), 0)
                    self.assertEqual(len(list(app.query("#welcome Input"))), 0)
                    self.assertEqual(len(list(app.query("#welcome Checkbox"))), 0)
                    self.assertEqual(len(list(app.query("#welcome Select"))), 0)


if __name__ == "__main__":
    unittest.main()
