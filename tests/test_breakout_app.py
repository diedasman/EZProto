"""Integration tests for breakout generation through the Textual app."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from textual.containers import Horizontal
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


def _kicad_cli_available() -> bool:
    if shutil.which("kicad-cli") or shutil.which("kicad-cli.exe"):
        return True
    program_files = os.environ.get("ProgramFiles", "").strip()
    if not program_files:
        return False
    return any((Path(program_files) / "KiCad").glob("*/bin/kicad-cli.exe"))


class BreakoutAppGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_breakout_dfm_checkboxes_toggle_with_generate_gerbers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: temp_dir},
                clear=False,
            ):
                app = ProtoboardApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    generate_gerbers = app.query_one("#breakout_generate_gerbers", Checkbox)
                    include_drill = app.query_one("#breakout_include_drill", Checkbox)
                    zip_output = app.query_one("#breakout_zip_output", Checkbox)
                    dfm_options = app.query_one("#breakout_dfm_options", Horizontal)

                    self.assertEqual(include_drill.parent, dfm_options)
                    self.assertEqual(zip_output.parent, dfm_options)
                    self.assertFalse(generate_gerbers.value)
                    self.assertTrue(include_drill.value)
                    self.assertTrue(include_drill.disabled)
                    self.assertTrue(zip_output.disabled)

                    generate_gerbers.value = True
                    for _ in range(3):
                        await pilot.pause()

                    self.assertFalse(include_drill.disabled)
                    self.assertFalse(zip_output.disabled)

                    zip_output.value = True
                    generate_gerbers.value = False
                    for _ in range(3):
                        await pilot.pause()

                    self.assertTrue(include_drill.disabled)
                    self.assertTrue(zip_output.disabled)
                    self.assertTrue(zip_output.value)

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
                    app.query_one("#breakout_trace_width", Input).value = "0.30"
                    app.query_one("#breakout_header_offset", Input).value = "2.5"
                    app.query_one("#breakout_margin", Input).value = "2"
                    app.query_one("#breakout_mount_hole", Input).value = "3.2"
                    app.query_one("#breakout_side_n", Checkbox).value = True
                    app.query_one("#breakout_side_s", Checkbox).value = True

                    for _ in range(3):
                        await pilot.pause()

                    footprint_preview = app.query_one("#breakout_footprint_preview", Static)
                    self.assertIn("SOIC_6_Test", str(footprint_preview.renderable))

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
                self.assertIn("MountingHole_NPTH", pcb_contents)
                self.assertIn("(segment", pcb_contents)

                saved_profile = load_user_profile("user")
                self.assertIsNotNone(saved_profile)
                assert saved_profile is not None
                board_details = saved_profile.boards["Breakout Test"]
                self.assertEqual(board_details["board_type"], "breakout")
                self.assertEqual(board_details["logical_pad_count"], 6)
                self.assertEqual(board_details["header_count"], 6)
                self.assertEqual(board_details["mounting_hole_diameter_mm"], 3.2)
                self.assertEqual(board_details["mounting_hole_count"], 4)
                self.assertEqual(board_details["trace_width_mm"], 0.30)
                self.assertEqual(board_details["output_file"], str(pcb_path))

    @unittest.skipUnless(_kicad_cli_available(), "KiCad CLI is required for breakout DFM tests.")
    async def test_app_generates_breakout_gerbers_and_archive(self) -> None:
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

                    app.query_one("#breakout_board_name", Input).value = "Breakout DFM"
                    app.query_one("#breakout_footprint_path", Input).value = str(fixture_path())
                    app.query_one("#breakout_board_width", Input).value = "30"
                    app.query_one("#breakout_board_height", Input).value = "30"
                    app.query_one("#breakout_pitch", Input).value = "2.54"
                    app.query_one("#breakout_header_offset", Input).value = "2.5"
                    app.query_one("#breakout_margin", Input).value = "2"
                    app.query_one("#breakout_generate_gerbers", Checkbox).value = True
                    for _ in range(3):
                        await pilot.pause()
                    app.query_one("#breakout_zip_output", Checkbox).value = True

                    await pilot.pause()
                    app.action_generate_breakout()
                    await pilot.pause()

                    status = app.query_one("#breakout_status", Static)
                    self.assertIn("DFM files written to", str(status.renderable))
                    self.assertIn("ZIP archive written to", str(status.renderable))

                board_directory = output_root / "Breakout DFM"
                dfm_directory = board_directory / "Breakout_DFM_DFM"
                archive_path = board_directory / "Breakout_DFM_DFM.zip"

                self.assertTrue(dfm_directory.exists())
                self.assertTrue(archive_path.exists())
                self.assertTrue((dfm_directory / "Breakout_DFM_F_Cu.gbr").exists())
                self.assertTrue((dfm_directory / "Breakout_DFM.drl").exists())

                with zipfile.ZipFile(archive_path) as archive:
                    archived_names = set(archive.namelist())
                    self.assertIn(
                        f"{dfm_directory.name}/Breakout_DFM_F_Cu.gbr",
                        archived_names,
                    )
                    self.assertIn(
                        f"{dfm_directory.name}/Breakout_DFM.drl",
                        archived_names,
                    )

                saved_profile = load_user_profile("user")
                self.assertIsNotNone(saved_profile)
                assert saved_profile is not None
                board_details = saved_profile.boards["Breakout DFM"]
                self.assertTrue(board_details["gerbers_generated"])
                self.assertTrue(board_details["zip_generated"])
                self.assertEqual(board_details["dfm_directory"], str(dfm_directory))


if __name__ == "__main__":
    unittest.main()
