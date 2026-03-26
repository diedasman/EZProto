"""Terminal-friendly board previews."""

from __future__ import annotations

from ezproto.breakout.models import BreakoutBoard
from ezproto.models import BoardParameters

MAX_PREVIEW_COLUMNS = 14
MAX_PREVIEW_ROWS = 8


def render_board_preview(parameters: BoardParameters) -> str:
    """Render a small textual approximation of the board."""

    top_left = "╭" if parameters.has_rounded_corners else "┌"
    top_right = "╮" if parameters.has_rounded_corners else "┐"
    bottom_left = "╰" if parameters.has_rounded_corners else "└"
    bottom_right = "╯" if parameters.has_rounded_corners else "┘"

    row_pattern = _render_row_pattern(parameters.columns)
    inner_width = len(row_pattern)

    lines = [
        f"{top_left}{'─' * (inner_width + 2)}{top_right}",
        *_render_rows(parameters.rows, row_pattern, inner_width),
        f"{bottom_left}{'─' * (inner_width + 2)}{bottom_right}",
        (
            f"{parameters.columns} cols x {parameters.rows} rows"
            f" | pitch {parameters.pitch_mm:g} mm"
            f" | corners {_corner_label(parameters)}"
        ),
    ]
    return "\n".join(lines)


def render_breakout_preview(board: BreakoutBoard) -> str:
    """Render a small textual breakout-board summary."""

    side_counts = {side: 0 for side in ("N", "E", "S", "W")}
    for header in board.headers:
        side_counts[header.side] += 1

    inner = "footprint".center(18)
    lines = [
        f"      N:{side_counts['N']}",
        "   +" + ("-" * 20) + "+",
        f"W:{side_counts['W']:<2} | {inner} | E:{side_counts['E']:>2}",
        "   +" + ("-" * 20) + "+",
        f"      S:{side_counts['S']}",
        (
            f"{len(board.pads)} pads"
            f" | {board.config.board_width_mm:g} x {board.config.board_height_mm:g} mm"
            f" | pitch {board.config.pitch_mm:g} mm"
        ),
    ]
    return "\n".join(lines)


def _render_rows(rows: int, row_pattern: str, inner_width: int) -> list[str]:
    if rows <= MAX_PREVIEW_ROWS:
        return [f"│ {row_pattern.ljust(inner_width)} │" for _ in range(rows)]

    visible_top = 3
    visible_bottom = 3
    lines = [f"│ {row_pattern.ljust(inner_width)} │" for _ in range(visible_top)]
    lines.append(f"│ {'⋮'.center(inner_width)} │")
    lines.extend(f"│ {row_pattern.ljust(inner_width)} │" for _ in range(visible_bottom))
    return lines


def _render_row_pattern(columns: int) -> str:
    if columns <= MAX_PREVIEW_COLUMNS:
        return " ".join("o" for _ in range(columns))

    leading = ["o"] * 6
    trailing = ["o"] * 6
    return " ".join([*leading, "…", *trailing])


def _corner_label(parameters: BoardParameters) -> str:
    if not parameters.has_rounded_corners:
        return "square"
    return f"{parameters.rounded_corner_radius_mm:g} mm"
