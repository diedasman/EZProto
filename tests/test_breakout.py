"""Unit tests for breakout-board generation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.breakout import BreakoutConfig, Pad, generate_breakout
from ezproto.breakout.footprint_parser import load_footprint, resolve_footprint_path
from ezproto.breakout.header_generator import generate_headers
from ezproto.breakout.models import HeaderPin
from ezproto.breakout.router import route
from ezproto.kicad import render_breakout_board, write_breakout_board


def fixture_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "simple_soic6.kicad_mod"


class FootprintParserTests(unittest.TestCase):
    def test_load_footprint_extracts_logical_pads_and_bounds(self) -> None:
        footprint = load_footprint(fixture_path())

        self.assertEqual(footprint.name, "SOIC_6_Test")
        self.assertEqual(len(footprint.pads), 6)
        self.assertEqual(footprint.physical_pad_count, 6)
        self.assertEqual([pad.name for pad in footprint.pads], ["1", "2", "3", "4", "5", "6"])
        self.assertAlmostEqual(footprint.bounds.width_mm, 7.5)
        self.assertAlmostEqual(footprint.bounds.height_mm, 5.68)

    def test_resolve_footprint_path_accepts_single_file_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / fixture_path().name
            target.write_text(fixture_path().read_text(encoding="utf-8"), encoding="utf-8")

            resolved = resolve_footprint_path(Path(temp_dir))

        self.assertEqual(resolved, target.resolve())


class HeaderGenerationTests(unittest.TestCase):
    def test_generate_headers_distributes_pins_across_selected_sides(self) -> None:
        config = BreakoutConfig(
            footprint_path=fixture_path(),
            board_width_mm=30.0,
            board_height_mm=24.0,
            pitch_mm=2.54,
            sides=("N", "E"),
        )
        pads = [
            Pad(name=str(index), x=10.0, y=10.0, net=f"PAD_{index}")
            for index in range(1, 7)
        ]

        headers = generate_headers(pads, config)

        self.assertEqual(len(headers), 6)
        self.assertEqual([header.side for header in headers[:3]], ["N", "N", "N"])
        self.assertEqual([header.side for header in headers[3:]], ["E", "E", "E"])
        self.assertAlmostEqual(headers[1].x - headers[0].x, 2.54)
        self.assertAlmostEqual(headers[2].x - headers[1].x, 2.54)
        self.assertAlmostEqual(headers[4].y - headers[3].y, 2.54)
        self.assertAlmostEqual(headers[5].y - headers[4].y, 2.54)


class RouterTests(unittest.TestCase):
    def test_route_creates_expected_manhattan_segments(self) -> None:
        pads = [Pad(name="1", x=10.0, y=10.0, net="PAD_1")]
        headers = [HeaderPin(name="1", x=15.0, y=2.0, net="PAD_1", side="N")]

        traces = route(pads, headers)

        self.assertEqual(
            traces,
            [
                type(traces[0])(start_x=10.0, start_y=10.0, end_x=15.0, end_y=10.0, net="PAD_1"),
                type(traces[1])(start_x=15.0, start_y=10.0, end_x=15.0, end_y=2.0, net="PAD_1"),
            ],
        )


class BreakoutBoardTests(unittest.TestCase):
    def test_render_breakout_board_contains_footprint_headers_and_segments(self) -> None:
        board = generate_breakout(
            BreakoutConfig(
                board_name="Breakout Demo",
                footprint_path=fixture_path(),
                board_width_mm=30.0,
                board_height_mm=30.0,
                pitch_mm=2.54,
                sides=("N", "S"),
                header_offset_mm=2.5,
                margin_mm=2.0,
            )
        )

        rendered = render_breakout_board(board)

        self.assertIn('"SOIC_6_Test"', rendered)
        self.assertNotIn('generator "EZProtoTest"', rendered)
        self.assertEqual(rendered.count('(footprint "EZProto:BreakoutPin"'), 6)
        self.assertEqual(rendered.count("(segment"), len(board.traces))
        self.assertIn('(net 1 "PAD_1")', rendered)
        self.assertIn("(gr_rect", rendered)

    def test_write_breakout_board_creates_output_file(self) -> None:
        board = generate_breakout(
            BreakoutConfig(
                board_name="Breakout Demo",
                footprint_path=fixture_path(),
                board_width_mm=30.0,
                board_height_mm=30.0,
                pitch_mm=2.54,
                sides=("N", "S"),
                header_offset_mm=2.5,
                margin_mm=2.0,
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "exports" / "breakout.kicad_pcb"
            written_path = write_breakout_board(destination, board)

            self.assertTrue(destination.exists())
            self.assertEqual(written_path, destination.resolve())
            self.assertIn("SOIC_6_Test", destination.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
