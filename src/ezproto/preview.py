"""Terminal-friendly board previews."""

from __future__ import annotations

from ezproto.models import BoardParameters

MAX_PREVIEW_COLUMNS = 14
MAX_PREVIEW_ROWS = 8


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


def _corner_label(has_rounded_corners: bool, radius_mm: float) -> str:
    if not has_rounded_corners:
        return "square"
    return f"{radius_mm:g} mm"
