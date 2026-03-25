"""Fabrication package tests for EZProto."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.fabrication import write_fabrication_package
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


if __name__ == "__main__":
    unittest.main()
