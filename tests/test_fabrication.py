"""Fabrication package tests for EZProto."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.fabrication import write_fabrication_archive, write_fabrication_package
from ezproto.models import BoardParameters


def make_board(**overrides: object) -> BoardParameters:
    values: dict[str, object] = {
        "board_name": "Demo Board",
        "columns": 3,
        "rows": 2,
        "pitch_mm": 2.54,
        "pth_drill_mm": 1.0,
        "pad_diameter_mm": 1.8,
        "mounting_hole_diameter_mm": 3.2,
        "edge_margin_mm": 5.0,
    }
    values.update(overrides)
    return BoardParameters(**values)


class FabricationPackageTests(unittest.TestCase):
    def test_write_fabrication_package_creates_expected_files(self) -> None:
        board = make_board()

        with tempfile.TemporaryDirectory() as temp_dir:
            dfm_directory = Path(temp_dir) / board.output_directory_name / f"{board.output_file_stem}_DFM"
            written_files = write_fabrication_package(dfm_directory, board)

            expected_names = {
                "Demo_Board_F_Cu.gbr",
                "Demo_Board_B_Cu.gbr",
                "Demo_Board_F_Mask.gbr",
                "Demo_Board_B_Mask.gbr",
                "Demo_Board_Edge_Cuts.gbr",
                "Demo_Board.drl",
            }

            self.assertEqual({path.name for path in written_files}, expected_names)
            self.assertTrue(dfm_directory.exists())
            self.assertIn("EZProto F.Cu", (dfm_directory / "Demo_Board_F_Cu.gbr").read_text(encoding="utf-8"))
            self.assertIn("M48", (dfm_directory / "Demo_Board.drl").read_text(encoding="utf-8"))

    def test_write_fabrication_package_can_skip_drill_file(self) -> None:
        board = make_board(mounting_hole_diameter_mm=0.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            dfm_directory = Path(temp_dir) / board.output_directory_name / f"{board.output_file_stem}_DFM"
            written_files = write_fabrication_package(
                dfm_directory,
                board,
                include_drill=False,
            )

            expected_names = {
                "Demo_Board_F_Cu.gbr",
                "Demo_Board_B_Cu.gbr",
                "Demo_Board_F_Mask.gbr",
                "Demo_Board_B_Mask.gbr",
                "Demo_Board_Edge_Cuts.gbr",
            }

            self.assertEqual({path.name for path in written_files}, expected_names)
            self.assertFalse((dfm_directory / "Demo_Board.drl").exists())

    def test_write_fabrication_archive_packages_generated_files(self) -> None:
        board = make_board(mounting_hole_diameter_mm=0.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            dfm_directory = Path(temp_dir) / board.output_directory_name / f"{board.output_file_stem}_DFM"
            written_files = write_fabrication_package(dfm_directory, board)
            archive_path = write_fabrication_archive(
                dfm_directory.with_suffix(".zip"),
                written_files,
                root_directory_name=dfm_directory.name,
            )

            self.assertTrue(archive_path.exists())
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {
                        f"{dfm_directory.name}/Demo_Board_F_Cu.gbr",
                        f"{dfm_directory.name}/Demo_Board_B_Cu.gbr",
                        f"{dfm_directory.name}/Demo_Board_F_Mask.gbr",
                        f"{dfm_directory.name}/Demo_Board_B_Mask.gbr",
                        f"{dfm_directory.name}/Demo_Board_Edge_Cuts.gbr",
                        f"{dfm_directory.name}/Demo_Board.drl",
                    },
                )

    def test_write_fabrication_package_uses_rounded_outline_points(self) -> None:
        board = make_board(
            mounting_hole_diameter_mm=0.0,
            rounded_corner_radius_mm=2.0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            dfm_directory = Path(temp_dir) / board.output_directory_name / f"{board.output_file_stem}_DFM"
            write_fabrication_package(dfm_directory, board)
            outline = (dfm_directory / "Demo_Board_Edge_Cuts.gbr").read_text(encoding="utf-8")

            self.assertIn("D02*", outline)
            self.assertGreater(outline.count("D01*"), 8)

    def test_drill_file_declares_absolute_coordinates(self) -> None:
        board = make_board(mounting_hole_diameter_mm=0.0)

        with tempfile.TemporaryDirectory() as temp_dir:
            dfm_directory = Path(temp_dir) / board.output_directory_name / f"{board.output_file_stem}_DFM"
            write_fabrication_package(dfm_directory, board)
            drill = (dfm_directory / "Demo_Board.drl").read_text(encoding="utf-8")

            self.assertIn("\nFMAT,2\n", drill)
            self.assertIn("\nMETRIC\n", drill)
            self.assertIn("\n%\nG90\nG05\nT01\n", drill)

    def test_fabrication_coordinates_use_kicad_style_y_axis(self) -> None:
        board = make_board(
            columns=10,
            rows=12,
            pitch_mm=2.54,
            pth_drill_mm=1.0,
            pad_diameter_mm=2.0,
            mounting_hole_diameter_mm=0.0,
            edge_margin_mm=2.0,
            rounded_corner_radius_mm=1.0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            dfm_directory = Path(temp_dir) / board.output_directory_name / f"{board.output_file_stem}_DFM"
            write_fabrication_package(dfm_directory, board)
            drill = (dfm_directory / "Demo_Board.drl").read_text(encoding="utf-8")
            front_cu = (dfm_directory / "Demo_Board_F_Cu.gbr").read_text(encoding="utf-8")

            self.assertIn("X2000000Y-2000000D03*", front_cu)
            self.assertIn("\nT01\nX2.0Y-2.0\n", drill)


if __name__ == "__main__":
    unittest.main()
