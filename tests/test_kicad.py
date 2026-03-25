"""Generator tests for EZProto."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.kicad import render_kicad_pcb, write_kicad_pcb
from ezproto.models import BoardParameters


def make_board(**overrides: object) -> BoardParameters:
    values: dict[str, object] = {
        "board_name": "Protoboard",
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


class BoardParameterTests(unittest.TestCase):
    def test_invalid_margin_rejected_when_mounting_holes_would_overlap(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Edge margin is too small",
        ):
            make_board(
                pad_diameter_mm=2.4,
                mounting_hole_diameter_mm=3.6,
                edge_margin_mm=4.0,
                columns=1,
                rows=1,
            )

    def test_output_path_uses_board_name_folder_and_underscored_file_name(self) -> None:
        board = make_board(
            board_name="Demo Board",
            columns=1,
            rows=1,
            mounting_hole_diameter_mm=0,
        )

        self.assertEqual(board.output_directory_name, "Demo Board")
        self.assertEqual(board.output_file_name, "Demo_Board.kicad_pcb")
        self.assertEqual(board.output_path, Path("Demo Board") / "Demo_Board.kicad_pcb")
        self.assertEqual(
            board.output_path_for("C:/Exports"),
            Path("C:/Exports") / "Demo Board" / "Demo_Board.kicad_pcb",
        )

    def test_rounded_corners_validate_against_mounting_holes(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Rounded corners clip the mounting hole",
        ):
            make_board(
                rounded_corner_radius_mm=5.0,
                mounting_hole_diameter_mm=3.2,
                edge_margin_mm=5.0,
            )


class KiCadRenderTests(unittest.TestCase):
    def test_render_contains_expected_sections_and_counts(self) -> None:
        board = make_board(columns=3, rows=2)

        rendered = render_kicad_pcb(board)

        self.assertIn('(generator "EZProto")', rendered)
        self.assertIn('(footprint "EZProto:PROTO_GRID"', rendered)
        self.assertIn('(end 15.08 12.54)', rendered)
        self.assertEqual(len(re.findall(r'\(pad "\d+" thru_hole circle', rendered)), 6)
        self.assertEqual(len(re.findall(r'\(pad "" np_thru_hole circle', rendered)), 4)

    def test_render_omits_mounting_holes_when_disabled(self) -> None:
        board = make_board(columns=2, rows=2, mounting_hole_diameter_mm=0)

        rendered = render_kicad_pcb(board)

        self.assertNotIn("MountingHole_NPTH", rendered)
        self.assertEqual(rendered.count("np_thru_hole circle"), 0)

    def test_render_uses_arcs_for_rounded_corners(self) -> None:
        board = make_board(
            mounting_hole_diameter_mm=0,
            rounded_corner_radius_mm=2.0,
        )

        rendered = render_kicad_pcb(board)

        self.assertEqual(rendered.count("(gr_arc"), 4)
        self.assertEqual(rendered.count("(gr_line"), 4)
        self.assertNotIn("(gr_rect", rendered)

    def test_write_kicad_pcb_creates_parent_directories(self) -> None:
        board = make_board(columns=4, rows=4)

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "exports" / "proto.kicad_pcb"
            written_path = write_kicad_pcb(destination, board)

            self.assertTrue(destination.exists())
            self.assertEqual(written_path, destination.resolve())
            self.assertIn("PROTO_GRID", destination.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
