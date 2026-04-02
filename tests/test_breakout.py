"""Unit tests for breakout-board generation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.breakout import BreakoutConfig, Pad, TraceSegment, generate_breakout
from ezproto.breakout.footprint_parser import load_footprint, resolve_footprint_path
from ezproto.breakout.header_generator import generate_headers
from ezproto.breakout.models import HeaderPin
from ezproto.breakout.router import route
from ezproto.kicad import render_breakout_board, write_breakout_board


def fixture_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "simple_soic6.kicad_mod"


def npth_fixture_text() -> str:
    return """(footprint "NPTH_Test"
  (version 20221018)
  (generator "EZProtoTest")
  (layer "F.Cu")
  (pad "1" smd rect (at -1 0) (size 1.2 0.8) (layers "F.Cu" "F.Paste" "F.Mask"))
  (pad "" np_thru_hole circle (at 0 0) (size 2 2) (drill 2) (layers "*.Cu" "*.Mask"))
  (pad "2" smd rect (at 1 0) (size 1.2 0.8) (layers "F.Cu" "F.Paste" "F.Mask"))
)"""


def make_config(**overrides: object) -> BreakoutConfig:
    values: dict[str, object] = {
        "board_name": "Breakout Demo",
        "footprint_path": fixture_path(),
        "board_width_mm": 30.0,
        "board_height_mm": 30.0,
        "pitch_mm": 2.54,
        "sides": ("N", "S"),
        "header_offset_mm": 2.5,
        "margin_mm": 2.0,
    }
    values.update(overrides)
    return BreakoutConfig(**values)


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

    def test_resolve_footprint_path_accepts_quoted_file_inside_pretty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pretty_directory = Path(temp_dir) / "Test.pretty"
            pretty_directory.mkdir()
            target = pretty_directory / fixture_path().name
            target.write_text(fixture_path().read_text(encoding="utf-8"), encoding="utf-8")

            resolved = resolve_footprint_path(f'"{target}"')

        self.assertEqual(resolved, target.resolve())

    def test_load_footprint_ignores_npth_pads_for_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "NPTH_Test.kicad_mod"
            target.write_text(npth_fixture_text(), encoding="utf-8")

            footprint = load_footprint(target)

        self.assertEqual([pad.name for pad in footprint.pads], ["1", "2"])
        self.assertEqual(footprint.physical_pad_count, 3)
        self.assertEqual(footprint.npth_pad_count, 1)


class HeaderGenerationTests(unittest.TestCase):
    def test_generate_headers_distributes_pins_across_selected_sides(self) -> None:
        config = make_config(board_height_mm=24.0, sides=("N", "E"))
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

    def test_generate_headers_prefers_pads_nearest_the_selected_edge(self) -> None:
        config = make_config(board_height_mm=32.0, sides=("N", "S"))
        pads = [
            Pad(name="1", x=10.0, y=7.0, net="PAD_1"),
            Pad(name="2", x=12.0, y=9.0, net="PAD_2"),
            Pad(name="3", x=14.0, y=11.0, net="PAD_3"),
            Pad(name="4", x=10.0, y=19.0, net="PAD_4"),
            Pad(name="5", x=12.0, y=21.0, net="PAD_5"),
            Pad(name="6", x=14.0, y=23.0, net="PAD_6"),
        ]

        headers = generate_headers(pads, config)

        north_nets = [header.net for header in headers if header.side == "N"]
        south_nets = [header.net for header in headers if header.side == "S"]
        self.assertEqual(north_nets, ["PAD_1", "PAD_2", "PAD_3"])
        self.assertEqual(south_nets, ["PAD_4", "PAD_5", "PAD_6"])


class RouterTests(unittest.TestCase):
    def test_route_uses_only_45_and_90_degree_segments(self) -> None:
        config = make_config(board_width_mm=20.0, board_height_mm=20.0, sides=("N",))
        pads = [Pad(name="1", x=10.0, y=12.0, net="PAD_1", width_mm=1.5, height_mm=0.6)]
        headers = [HeaderPin(name="1", x=15.0, y=2.5, net="PAD_1", side="N")]

        traces = route(pads, headers, config=config)

        self.assertGreaterEqual(len(traces), 2)
        self.assertEqual((traces[0].start_x, traces[0].start_y), (10.0, 12.0))
        self.assertEqual((traces[-1].end_x, traces[-1].end_y), (15.0, 2.5))
        for trace in traces:
            dx = abs(trace.end_x - trace.start_x)
            dy = abs(trace.end_y - trace.start_y)
            self.assertTrue(dx == 0 or dy == 0 or abs(dx - dy) < 1e-9)

    def test_generated_breakout_routes_do_not_intersect(self) -> None:
        board = generate_breakout(make_config())

        for first, second in combinations(board.traces, 2):
            if first.net == second.net:
                continue
            self.assertFalse(_segments_intersect(first, second))


class BreakoutBoardTests(unittest.TestCase):
    def test_render_breakout_board_contains_footprint_headers_and_segments(self) -> None:
        board = generate_breakout(make_config())

        rendered = render_breakout_board(board)

        self.assertIn('"SOIC_6_Test"', rendered)
        self.assertNotIn('generator "EZProtoTest"', rendered)
        self.assertEqual(rendered.count('(footprint "EZProto:BreakoutPin"'), 6)
        self.assertEqual(rendered.count("(segment"), len(board.traces))
        self.assertIn('(net 1 "PAD_1")', rendered)
        self.assertIn("(gr_rect", rendered)

    def test_render_breakout_board_uses_rounded_outline_when_requested(self) -> None:
        board = generate_breakout(make_config(rounded_corner_radius_mm=2.0))

        rendered = render_breakout_board(board)

        self.assertEqual(rendered.count("(gr_arc"), 4)
        self.assertEqual(rendered.count("(gr_line"), 4)
        self.assertNotIn("(gr_rect", rendered)

    def test_write_breakout_board_creates_output_file(self) -> None:
        board = generate_breakout(make_config())

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "exports" / "breakout.kicad_pcb"
            written_path = write_breakout_board(destination, board)

            self.assertTrue(destination.exists())
            self.assertEqual(written_path, destination.resolve())
            self.assertIn("SOIC_6_Test", destination.read_text(encoding="utf-8"))


def _segments_intersect(first: TraceSegment, second: TraceSegment) -> bool:
    points_a = ((first.start_x, first.start_y), (first.end_x, first.end_y))
    points_b = ((second.start_x, second.start_y), (second.end_x, second.end_y))
    if any(point_a == point_b for point_a in points_a for point_b in points_b):
        return False
    return _raw_segments_intersect(points_a[0], points_a[1], points_b[0], points_b[1])


def _raw_segments_intersect(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    orientation_1 = _orientation(first_start, first_end, second_start)
    orientation_2 = _orientation(first_start, first_end, second_end)
    orientation_3 = _orientation(second_start, second_end, first_start)
    orientation_4 = _orientation(second_start, second_end, first_end)

    if orientation_1 == 0 and _point_on_segment(second_start, first_start, first_end):
        return True
    if orientation_2 == 0 and _point_on_segment(second_end, first_start, first_end):
        return True
    if orientation_3 == 0 and _point_on_segment(first_start, second_start, second_end):
        return True
    if orientation_4 == 0 and _point_on_segment(first_end, second_start, second_end):
        return True

    return orientation_1 != orientation_2 and orientation_3 != orientation_4


def _orientation(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> int:
    value = (
        (second[1] - first[1]) * (third[0] - second[0])
        - (second[0] - first[0]) * (third[1] - second[1])
    )
    if abs(value) < 1e-9:
        return 0
    return 1 if value > 0 else 2


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    return (
        min(start[0], end[0]) - 1e-9 <= point[0] <= max(start[0], end[0]) + 1e-9
        and min(start[1], end[1]) - 1e-9 <= point[1] <= max(start[1], end[1]) + 1e-9
    )


if __name__ == "__main__":
    unittest.main()
