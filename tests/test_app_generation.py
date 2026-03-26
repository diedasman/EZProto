"""Integration tests for generating boards through the Textual app."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from textual.containers import Horizontal
from textual.widgets import Checkbox, Input, Select, Static

from ezproto.app import ProtoboardApp
from ezproto.storage import APP_DATA_ENV_VAR_NAME, DEFAULT_THEME_NAME, UserProfile, load_user_profile, save_user_profile


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _output_root() -> Path:
    root = _project_root() / "output"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _next_test_board_name(output_root: Path) -> str:
    highest_index = 0
    for path in output_root.iterdir():
        if not path.is_dir():
            continue
        match = re.fullmatch(r"test(\d+)", path.name)
        if match is None:
            continue
        highest_index = max(highest_index, int(match.group(1)))
    return f"test{highest_index + 1}"


class ProtoboardAppGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_dfm_option_checkboxes_toggle_with_generate_gerbers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: temp_dir},
                clear=False,
            ):
                app = ProtoboardApp()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    generate_gerbers = app.query_one("#generate_gerbers", Checkbox)
                    include_drill = app.query_one("#include_drill", Checkbox)
                    zip_output = app.query_one("#zip_output", Checkbox)
                    dfm_options = app.query_one("#dfm_options", Horizontal)

                    self.assertEqual(include_drill.parent, dfm_options)
                    self.assertEqual(zip_output.parent, dfm_options)
                    self.assertFalse(generate_gerbers.value)
                    self.assertTrue(include_drill.value)
                    self.assertTrue(include_drill.disabled)
                    self.assertTrue(zip_output.disabled)

                    generate_gerbers.value = True
                    await pilot.pause()

                    self.assertTrue(generate_gerbers.value)
                    self.assertFalse(include_drill.disabled)
                    self.assertFalse(zip_output.disabled)

                    zip_output.value = True
                    generate_gerbers.value = False
                    await pilot.pause()

                    self.assertTrue(include_drill.disabled)
                    self.assertTrue(zip_output.disabled)
                    self.assertTrue(zip_output.value)

    async def test_app_generates_pcb_and_gerbers_for_project_output_user(self) -> None:
        output_root = _output_root()
        board_name = _next_test_board_name(output_root)

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(
                "os.environ",
                {APP_DATA_ENV_VAR_NAME: temp_dir},
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

                    app.query_one("#board_name", Input).value = board_name
                    app.query_one("#columns", Input).value = "10"
                    app.query_one("#rows", Input).value = "12"
                    app.query_one("#pitch", Input).value = "2.54"
                    app.query_one("#pth_drill", Input).value = "1"
                    app.query_one("#pad_diameter", Input).value = "2"
                    app.query_one("#mount_hole", Input).value = "0"
                    app.query_one("#edge_margin", Input).value = "2"
                    app.query_one("#rounded_corners", Select).value = "1"
                    app.query_one("#generate_gerbers", Checkbox).value = True
                    app.query_one("#zip_output", Checkbox).value = True

                    await pilot.pause()
                    app.action_generate()
                    await pilot.pause()

                    status = app.query_one("#proto_status", Static)
                    self.assertIn("PCB written to", str(status.renderable))
                    self.assertIn("DFM files written to", str(status.renderable))
                    self.assertIn("ZIP archive written to", str(status.renderable))

                board_directory = output_root / board_name
                dfm_directory = board_directory / f"{board_name}_DFM"
                archive_path = board_directory / f"{board_name}_DFM.zip"
                pcb_path = board_directory / f"{board_name}.kicad_pcb"

                expected_dfm_files = {
                    f"{board_name}_F_Cu.gbr",
                    f"{board_name}_B_Cu.gbr",
                    f"{board_name}_F_Mask.gbr",
                    f"{board_name}_B_Mask.gbr",
                    f"{board_name}_F_Paste.gbr",
                    f"{board_name}_B_Paste.gbr",
                    f"{board_name}_F_Silkscreen.gbr",
                    f"{board_name}_B_Silkscreen.gbr",
                    f"{board_name}_Edge_Cuts.gbr",
                    f"{board_name}.drl",
                }

                self.assertTrue(board_directory.exists())
                self.assertTrue(pcb_path.exists())
                self.assertTrue(dfm_directory.exists())
                self.assertTrue(archive_path.exists())
                self.assertEqual({path.name for path in dfm_directory.iterdir()}, expected_dfm_files)

                pcb_contents = pcb_path.read_text(encoding="utf-8")
                self.assertEqual(pcb_contents.count("(gr_arc"), 4)
                self.assertNotIn("(gr_rect", pcb_contents)

                with zipfile.ZipFile(archive_path) as archive:
                    archived_names = set(archive.namelist())
                    self.assertIn(
                        f"{dfm_directory.name}/{board_name}_F_Cu.gbr",
                        archived_names,
                    )
                    self.assertIn(
                        f"{dfm_directory.name}/{board_name}_F_Silkscreen.gbr",
                        archived_names,
                    )

                saved_profile = load_user_profile("user")
                self.assertIsNotNone(saved_profile)
                assert saved_profile is not None
                self.assertEqual(saved_profile.default_output_directory, str(output_root))
                self.assertIn(board_name, saved_profile.boards)
                self.assertTrue(saved_profile.boards[board_name]["zip_generated"])
                self.assertEqual(saved_profile.boards[board_name]["zip_archive"], str(archive_path))

    async def test_app_respects_drill_and_zip_export_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir) / "data"
            output_root = Path(temp_dir) / "output"
            board_name = "zip-options-test"

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

                    app.query_one("#board_name", Input).value = board_name
                    app.query_one("#columns", Input).value = "10"
                    app.query_one("#rows", Input).value = "12"
                    app.query_one("#pitch", Input).value = "2.54"
                    app.query_one("#pth_drill", Input).value = "1"
                    app.query_one("#pad_diameter", Input).value = "2"
                    app.query_one("#mount_hole", Input).value = "0"
                    app.query_one("#edge_margin", Input).value = "2"
                    app.query_one("#rounded_corners", Select).value = "1"
                    app.query_one("#generate_gerbers", Checkbox).value = True
                    await pilot.pause()
                    app.query_one("#include_drill", Checkbox).value = False
                    app.query_one("#zip_output", Checkbox).value = True

                    await pilot.pause()
                    app.action_generate()
                    await pilot.pause()

                    status = app.query_one("#proto_status", Static)
                    self.assertIn("DFM files written to", str(status.renderable))
                    self.assertIn("ZIP archive written to", str(status.renderable))

                board_directory = output_root / board_name
                dfm_directory = board_directory / f"{board_name}_DFM"
                archive_path = board_directory / f"{board_name}_DFM.zip"

                self.assertTrue(dfm_directory.exists())
                self.assertTrue(archive_path.exists())
                self.assertFalse((dfm_directory / f"{board_name}.drl").exists())

                with zipfile.ZipFile(archive_path) as archive:
                    archived_names = set(archive.namelist())
                    self.assertNotIn(f"{dfm_directory.name}/{board_name}.drl", archived_names)
                    self.assertIn(
                        f"{dfm_directory.name}/{board_name}_F_Cu.gbr",
                        archived_names,
                    )
                    self.assertIn(
                        f"{dfm_directory.name}/{board_name}_F_Silkscreen.gbr",
                        archived_names,
                    )

                saved_profile = load_user_profile("user")
                self.assertIsNotNone(saved_profile)
                assert saved_profile is not None
                board_details = saved_profile.boards[board_name]
                self.assertFalse(board_details["drill_included"])
                self.assertTrue(board_details["zip_requested"])
                self.assertTrue(board_details["zip_generated"])
                self.assertEqual(board_details["zip_archive"], str(archive_path))


if __name__ == "__main__":
    unittest.main()
