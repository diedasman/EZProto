"""Preview rendering tests for EZProto."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.models import BoardParameters
from ezproto.preview import render_board_preview


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


class PreviewRenderTests(unittest.TestCase):
    def test_square_preview_uses_square_corners(self) -> None:
        preview = render_board_preview(make_board())

        self.assertIn("┌", preview)
        self.assertIn("4 cols x 3 rows", preview)

    def test_rounded_preview_uses_rounded_corners(self) -> None:
        preview = render_board_preview(make_board(rounded_corner_radius_mm=2.0))

        self.assertIn("╭", preview)
        self.assertIn("corners 2 mm", preview)


if __name__ == "__main__":
    unittest.main()
