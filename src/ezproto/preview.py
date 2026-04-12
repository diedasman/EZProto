"""Terminal-friendly board previews."""

from __future__ import annotations

from ezproto.breakout.models import BreakoutBoard, ParsedFootprint
from ezproto.models import BoardParameters

MAX_PREVIEW_COLUMNS = 14
MAX_PREVIEW_ROWS = 8
FOOTPRINT_PREVIEW_WIDTH = 22
FOOTPRINT_PREVIEW_HEIGHT = 7
BREAKOUT_PREVIEW_WIDTH = 22
BREAKOUT_PREVIEW_HEIGHT = 7


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
    """Render a small textual breakout-board preview with routed traces."""

    side_counts = {side: 0 for side in ("N", "E", "S", "W")}
    for header in board.headers:
        side_counts[header.side] += 1

    top_left = "\u256d" if board.config.has_rounded_corners else "\u250c"
    top_right = "\u256e" if board.config.has_rounded_corners else "\u2510"
    bottom_left = "\u2570" if board.config.has_rounded_corners else "\u2514"
    bottom_right = "\u256f" if board.config.has_rounded_corners else "\u2518"
    horizontal = "\u2500"
    vertical = "\u2502"
    inner_width = BREAKOUT_PREVIEW_WIDTH
    canvas = [[" " for _ in range(inner_width)] for _ in range(BREAKOUT_PREVIEW_HEIGHT)]

    _draw_breakout_bounds(canvas, board)
    for trace in board.traces:
        _draw_breakout_trace(canvas, board, trace.start_x, trace.start_y, trace.end_x, trace.end_y)
    for hole_x, hole_y in board.config.iter_mounting_hole_positions() or ():
        row, col = _breakout_canvas_position(board, hole_x, hole_y, width=inner_width, height=BREAKOUT_PREVIEW_HEIGHT)
        canvas[row][col] = "O"
    for pad in board.pads:
        row, col = _breakout_canvas_position(board, pad.x, pad.y, width=inner_width, height=BREAKOUT_PREVIEW_HEIGHT)
        canvas[row][col] = _pad_marker(pad.name, "o")
    for header in board.headers:
        row, col = _breakout_canvas_position(board, header.x, header.y, width=inner_width, height=BREAKOUT_PREVIEW_HEIGHT)
        canvas[row][col] = header.side

    routing_detail = (
        f"routing {len(board.routing_warnings)} fallback"
        if board.routing_warnings
        else "routing clean"
    )
    hole_detail = (
        f"holes {board.config.mounting_hole_count} x {board.config.mounting_hole_diameter_mm:g} mm"
        if board.config.mounting_hole_count
        else "holes disabled"
    )

    lines = [
        f"      N:{side_counts['N']}",
        f"   {top_left}{horizontal * (inner_width + 2)}{top_right}",
        *[
            (
                f"W:{side_counts['W']:<2} {vertical} {''.join(canvas[row])} {vertical} E:{side_counts['E']:>2}"
                if row == BREAKOUT_PREVIEW_HEIGHT // 2
                else f"   {vertical} {''.join(canvas[row])} {vertical}"
            )
            for row in range(BREAKOUT_PREVIEW_HEIGHT)
        ],
        f"   {bottom_left}{horizontal * (inner_width + 2)}{bottom_right}",
        f"      S:{side_counts['S']}",
        _trim_text(board.footprint.name, inner_width + 10),
        (
            f"{len(board.pads)} pads"
            f" | {len(board.headers)} headers"
            f" | {len(board.traces)} traces"
        ),
        (
            f"{board.config.board_width_mm:g} x {board.config.board_height_mm:g} mm"
            f" | trace {board.config.trace_width_mm:g} mm"
            f" | {routing_detail}"
        ),
        f"{hole_detail} | corners {_corner_label(board.config.has_rounded_corners, board.config.rounded_corner_radius_mm)}",
    ]
    return "\n".join(lines)


def _draw_breakout_bounds(canvas: list[list[str]], board: BreakoutBoard) -> None:
    corners = (
        (board.footprint_origin_x + board.footprint.bounds.min_x, board.footprint_origin_y + board.footprint.bounds.min_y),
        (board.footprint_origin_x + board.footprint.bounds.max_x, board.footprint_origin_y + board.footprint.bounds.min_y),
        (board.footprint_origin_x + board.footprint.bounds.max_x, board.footprint_origin_y + board.footprint.bounds.max_y),
        (board.footprint_origin_x + board.footprint.bounds.min_x, board.footprint_origin_y + board.footprint.bounds.max_y),
    )
    for (start_x, start_y), (end_x, end_y) in zip(corners, corners[1:] + corners[:1]):
        _draw_breakout_trace(canvas, board, start_x, start_y, end_x, end_y, marker=".")


def _draw_breakout_trace(
    canvas: list[list[str]],
    board: BreakoutBoard,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    *,
    marker: str | None = None,
) -> None:
    start_row, start_col = _breakout_canvas_position(
        board,
        start_x,
        start_y,
        width=len(canvas[0]),
        height=len(canvas),
    )
    end_row, end_col = _breakout_canvas_position(
        board,
        end_x,
        end_y,
        width=len(canvas[0]),
        height=len(canvas),
    )
    steps = max(abs(end_col - start_col), abs(end_row - start_row), 1)
    trace_marker = marker or _breakout_segment_marker(start_col, start_row, end_col, end_row)
    for step in range(steps + 1):
        fraction = step / steps
        row = round(start_row + ((end_row - start_row) * fraction))
        col = round(start_col + ((end_col - start_col) * fraction))
        existing = canvas[row][col]
        if existing == " " or existing == "." or existing == trace_marker:
            canvas[row][col] = trace_marker
        elif existing != trace_marker:
            canvas[row][col] = "+"


def _breakout_canvas_position(
    board: BreakoutBoard,
    x_pos: float,
    y_pos: float,
    *,
    width: int,
    height: int,
) -> tuple[int, int]:
    max_col = max(width - 1, 1)
    max_row = max(height - 1, 1)
    col = round((x_pos / max(board.config.board_width_mm, 1.0)) * max_col)
    row = round((y_pos / max(board.config.board_height_mm, 1.0)) * max_row)
    return max(0, min(max_row, row)), max(0, min(max_col, col))


def _breakout_segment_marker(start_col: int, start_row: int, end_col: int, end_row: int) -> str:
    delta_col = end_col - start_col
    delta_row = end_row - start_row
    if delta_col == 0:
        return "|"
    if delta_row == 0:
        return "-"
    return "\\" if (delta_col > 0) == (delta_row > 0) else "/"


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
