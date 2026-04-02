"""Preview rendering tests for EZProto."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.breakout import BreakoutConfig, generate_breakout
from ezproto.breakout.footprint_parser import load_footprint
from ezproto.models import BoardParameters
from ezproto.preview import (
    render_board_preview,
    render_breakout_preview,
    render_footprint_preview,
)


def fixture_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "simple_soic6.kicad_mod"


def make_board(**overrides: object) -> BoardParameters:
    values: dict[str, object] = {
        "board_name": "Preview Board",
        "columns": 4,
        "rows": 3,
        "pitch_mm": 2.54,
        "pth_drill_mm": 1.0,
        "pad_diameter_mm": 1.8,
        "mounting_hole_diameter_mm": 0.0,
        "edge_margin_mm": 5.0,
        "rounded_corner_radius_mm": 0.0,
    }
    values.update(overrides)
    return BoardParameters(**values)


def make_breakout(**overrides: object):
    values: dict[str, object] = {
        "board_name": "Preview Breakout",
        "footprint_path": fixture_path(),
        "board_width_mm": 30.0,
        "board_height_mm": 30.0,
        "pitch_mm": 2.54,
        "sides": ("N", "S"),
        "header_offset_mm": 2.5,
        "margin_mm": 2.0,
    }
    values.update(overrides)
    return generate_breakout(BreakoutConfig(**values))


class PreviewRenderTests(unittest.TestCase):
    def test_square_preview_uses_square_corners(self) -> None:
        preview = render_board_preview(make_board())

        self.assertIn("\u250c", preview)
        self.assertIn("4 cols x 3 rows", preview)

    def test_rounded_preview_uses_rounded_corners(self) -> None:
        preview = render_board_preview(make_board(rounded_corner_radius_mm=2.0))

        self.assertIn("\u256d", preview)
        self.assertIn("corners 2 mm", preview)

    def test_footprint_preview_lists_bounds_and_pad_names(self) -> None:
        preview = render_footprint_preview(load_footprint(fixture_path()))

        self.assertIn("SOIC_6_Test", preview)
        self.assertIn("6 logical pads", preview)
        self.assertIn("view fit", preview)
        self.assertIn("Pads: 1, 2, 3, 4, 5, 6", preview)

    def test_breakout_preview_shows_trace_width_and_corner_style(self) -> None:
        preview = render_breakout_preview(make_breakout(rounded_corner_radius_mm=2.0))

        self.assertIn("trace 0.25 mm", preview)
        self.assertIn("corners 2 mm", preview)
        self.assertIn("N:3", preview)
        self.assertIn("S:3", preview)


if __name__ == "__main__":
    unittest.main()
