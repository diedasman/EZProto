"""Terminal-friendly board previews."""

from __future__ import annotations

from ezproto.breakout.models import BreakoutBoard, ParsedFootprint
from ezproto.models import BoardParameters

MAX_PREVIEW_COLUMNS = 14
MAX_PREVIEW_ROWS = 8
FOOTPRINT_PREVIEW_WIDTH = 22
FOOTPRINT_PREVIEW_HEIGHT = 7


def render_board_preview(parameters: BoardParameters) -> str:
    """Render a small textual approximation of the board."""

    top_left = "\u256d" if parameters.has_rounded_corners else "\u250c"
    top_right = "\u256e" if parameters.has_rounded_corners else "\u2510"
    bottom_left = "\u2570" if parameters.has_rounded_corners else "\u2514"
    bottom_right = "\u256f" if parameters.has_rounded_corners else "\u2518"
    horizontal = "\u2500"
    vertical = "\u2502"

    row_pattern = _render_row_pattern(parameters.columns)
    inner_width = len(row_pattern)

    lines = [
        f"{top_left}{horizontal * (inner_width + 2)}{top_right}",
        *_render_rows(parameters.rows, row_pattern, inner_width, vertical=vertical),
        f"{bottom_left}{horizontal * (inner_width + 2)}{bottom_right}",
        (
            f"{parameters.columns} cols x {parameters.rows} rows"
            f" | pitch {parameters.pitch_mm:g} mm"
            f" | corners {_corner_label(parameters.has_rounded_corners, parameters.rounded_corner_radius_mm)}"
        ),
    ]
    return "\n".join(lines)


def render_footprint_preview(footprint: ParsedFootprint) -> str:
    """Render a simplified fit-to-view footprint preview."""

    width = FOOTPRINT_PREVIEW_WIDTH
    height = FOOTPRINT_PREVIEW_HEIGHT
    canvas = [[" " for _ in range(width)] for _ in range(height)]

    _draw_box(canvas)

    bounds = footprint.bounds
    span_x = bounds.width_mm or 1.0
    span_y = bounds.height_mm or 1.0
    marker_map: dict[tuple[int, int], str] = {}

    for pad in footprint.pads:
        col = 1 + round(((pad.x - bounds.min_x) / span_x) * (width - 3))
        row = 1 + round(((pad.y - bounds.min_y) / span_y) * (height - 3))
        marker_map[(row, col)] = _pad_marker(pad.name, marker_map.get((row, col), "o"))

    for (row, col), marker in marker_map.items():
        canvas[row][col] = marker

    pad_names = ", ".join(pad.name for pad in footprint.pads[:10])
    if len(footprint.pads) > 10:
        pad_names += ", ..."

    lines = [
        footprint.name,
        (
            f"{len(footprint.pads)} logical pads"
            f" | {footprint.physical_pad_count} physical pads"
            f" | view fit"
        ),
        f"{bounds.width_mm:.2f} mm x {bounds.height_mm:.2f} mm",
        *("".join(row) for row in canvas),
        f"Pads: {pad_names}",
    ]
    return "\n".join(lines)


def render_breakout_preview(board: BreakoutBoard) -> str:
    """Render a small textual breakout-board summary."""

    side_counts = {side: 0 for side in ("N", "E", "S", "W")}
    for header in board.headers:
        side_counts[header.side] += 1

    top_left = "\u256d" if board.config.has_rounded_corners else "\u250c"
    top_right = "\u256e" if board.config.has_rounded_corners else "\u2510"
    bottom_left = "\u2570" if board.config.has_rounded_corners else "\u2514"
    bottom_right = "\u256f" if board.config.has_rounded_corners else "\u2518"
    horizontal = "\u2500"
    vertical = "\u2502"
    inner_width = 22

    title = _trim_text(board.footprint.name, inner_width).center(inner_width)
    detail = _trim_text(
        f"{len(board.headers)} headers | {len(board.traces)} traces",
        inner_width,
    ).center(inner_width)
    trace_detail = _trim_text(
        f"trace {board.config.trace_width_mm:g} mm | {board.config.pitch_mm:g} mm pitch",
        inner_width,
    ).center(inner_width)

    lines = [
        f"      N:{side_counts['N']}",
        f"   {top_left}{horizontal * (inner_width + 2)}{top_right}",
        f"W:{side_counts['W']:<2} {vertical} {title} {vertical} E:{side_counts['E']:>2}",
        f"   {vertical} {detail} {vertical}",
        f"   {vertical} {trace_detail} {vertical}",
        f"   {bottom_left}{horizontal * (inner_width + 2)}{bottom_right}",
        f"      S:{side_counts['S']}",
        (
            f"{len(board.pads)} pads"
            f" | {board.config.board_width_mm:g} x {board.config.board_height_mm:g} mm"
            f" | corners {_corner_label(board.config.has_rounded_corners, board.config.rounded_corner_radius_mm)}"
        ),
    ]
    return "\n".join(lines)


def _render_rows(
    rows: int,
    row_pattern: str,
    inner_width: int,
    *,
    vertical: str,
) -> list[str]:
    if rows <= MAX_PREVIEW_ROWS:
        return [f"{vertical} {row_pattern.ljust(inner_width)} {vertical}" for _ in range(rows)]

    visible_top = 3
    visible_bottom = 3
    lines = [f"{vertical} {row_pattern.ljust(inner_width)} {vertical}" for _ in range(visible_top)]
    lines.append(f"{vertical} {'\u22ee'.center(inner_width)} {vertical}")
    lines.extend(
        f"{vertical} {row_pattern.ljust(inner_width)} {vertical}"
        for _ in range(visible_bottom)
    )
    return lines


def _render_row_pattern(columns: int) -> str:
    if columns <= MAX_PREVIEW_COLUMNS:
        return " ".join("o" for _ in range(columns))

    leading = ["o"] * 6
    trailing = ["o"] * 6
    return " ".join([*leading, "\u2026", *trailing])


def _draw_box(canvas: list[list[str]]) -> None:
    width = len(canvas[0])
    height = len(canvas)
    top = 0
    bottom = height - 1
    left = 0
    right = width - 1

    canvas[top][left] = "\u250c"
    canvas[top][right] = "\u2510"
    canvas[bottom][left] = "\u2514"
    canvas[bottom][right] = "\u2518"

    for col in range(left + 1, right):
        canvas[top][col] = "\u2500"
        canvas[bottom][col] = "\u2500"
    for row in range(top + 1, bottom):
        canvas[row][left] = "\u2502"
        canvas[row][right] = "\u2502"


def _pad_marker(name: str, fallback: str) -> str:
    if len(name) == 1:
        return name
    if name.isdigit():
        return str(int(name) % 10)
    return name[0].upper() if name else fallback


def _trim_text(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: max(width - 1, 0)] + "\u2026"


def _corner_label(has_rounded_corners: bool, radius_mm: float) -> str:
    if not has_rounded_corners:
        return "square"
    return f"{radius_mm:g} mm"
