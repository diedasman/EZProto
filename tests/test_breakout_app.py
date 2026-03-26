"""Integration tests for breakout generation through the Textual app."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from textual.widgets import Checkbox, Input, Static

from ezproto.app import ProtoboardApp
from ezproto.storage import (
    APP_DATA_ENV_VAR_NAME,
    DEFAULT_THEME_NAME,
    UserProfile,
    load_user_profile,
    save_user_profile,
)


def fixture_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "simple_soic6.kicad_mod"


class BreakoutAppGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_app_generates_breakout_board_for_active_user(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir) / "data"
            output_root = Path(temp_dir) / "output"

            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: str(data_root)},
                clear=False,
            ):
                profile = UserProfile(
                    name="user",
                    default_output_directory=str(output_root),
                    theme=DEFAULT_THEME_NAME,
                )
                save_user_profile(profile)

                app = ProtoboardApp()
                async with app.run_test() as pilot:
                    app._activate_user(profile)

                    app.query_one("#breakout_board_name", Input).value = "Breakout Test"
                    app.query_one("#breakout_footprint_path", Input).value = str(fixture_path())
                    app.query_one("#breakout_board_width", Input).value = "30"
                    app.query_one("#breakout_board_height", Input).value = "30"
                    app.query_one("#breakout_pitch", Input).value = "2.54"
                    app.query_one("#breakout_header_offset", Input).value = "2.5"
                    app.query_one("#breakout_margin", Input).value = "2"
                    app.query_one("#breakout_side_n", Checkbox).value = True
                    app.query_one("#breakout_side_s", Checkbox).value = True

                    await pilot.pause()
                    app.action_generate_breakout()
                    await pilot.pause()

                    status = app.query_one("#breakout_status", Static)
                    self.assertIn("PCB written to", str(status.renderable))

                board_directory = output_root / "Breakout Test"
                pcb_path = board_directory / "Breakout_Test.kicad_pcb"

                self.assertTrue(board_directory.exists())
                self.assertTrue(pcb_path.exists())
                pcb_contents = pcb_path.read_text(encoding="utf-8")
                self.assertIn("SOIC_6_Test", pcb_contents)
                self.assertIn("EZProto:BreakoutPin", pcb_contents)
                self.assertIn("(segment", pcb_contents)

                saved_profile = load_user_profile("user")
                self.assertIsNotNone(saved_profile)
                assert saved_profile is not None
                board_details = saved_profile.boards["Breakout Test"]
                self.assertEqual(board_details["board_type"], "breakout")
                self.assertEqual(board_details["logical_pad_count"], 6)
                self.assertEqual(board_details["header_count"], 6)
                self.assertEqual(board_details["output_file"], str(pcb_path))


if __name__ == "__main__":
    unittest.main()
