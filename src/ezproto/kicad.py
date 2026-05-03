"""KiCad PCB file generation helpers."""

from __future__ import annotations

from math import sqrt
from pathlib import Path

from ezproto.models import BoardParameters


def render_kicad_pcb(parameters: BoardParameters) -> str:
    """Render a KiCad `.kicad_pcb` document from board parameters."""

    width = _mm(parameters.board_width_mm)
    height = _mm(parameters.board_height_mm)
    label_offset = _mm(max(parameters.edge_margin_mm / 2.0, 2.0))

    lines: list[str] = [
        "(kicad_pcb",
        '  (version 20221018)',
        '  (generator "EZProto")',
        "  (general",
        "    (thickness 1.6)",
        "  )",
        '  (paper "A4")',
        "  (layers",
        '    (0 "F.Cu" signal)',
        '    (31 "B.Cu" signal)',
        '    (32 "B.Adhes" user)',
        '    (33 "F.Adhes" user)',
        '    (34 "B.Paste" user)',
        '    (35 "F.Paste" user)',
        '    (36 "B.SilkS" user)',
        '    (37 "F.SilkS" user)',
        '    (38 "B.Mask" user)',
        '    (39 "F.Mask" user)',
        '    (40 "Dwgs.User" user)',
        '    (41 "Cmts.User" user)',
        '    (42 "Eco1.User" user)',
        '    (43 "Eco2.User" user)',
        '    (44 "Edge.Cuts" user)',
        '    (45 "Margin" user)',
        '    (46 "B.CrtYd" user)',
        '    (47 "F.CrtYd" user)',
        '    (48 "B.Fab" user)',
        '    (49 "F.Fab" user)',
        "  )",
        '  (net 0 "")',
        '  (footprint "EZProto:PROTO_GRID"',
        '    (layer "F.Cu")',
        "    (at 0 0)",
        "    (attr board_only exclude_from_pos_files exclude_from_bom)",
        f'    (fp_text reference "BRD1" (at 0 -{label_offset}) (layer "F.SilkS") hide',
        "      (effects (font (size 1 1) (thickness 0.15)))",
        "    )",
        f'    (fp_text value "{parameters.board_name}" (at 0 0) (layer "F.Fab") hide',
        "      (effects (font (size 1 1) (thickness 0.15)))",
        "    )",
    ]

    lines.extend(_render_pads(parameters))
    lines.append("  )")

    if parameters.mounting_hole_diameter_mm > 0:
        lines.extend(_render_mounting_holes(parameters))

    lines.extend(_render_board_outline(parameters, width=width, height=height))
    lines.append(")")

    return "\n".join(lines) + "\n"


def write_kicad_pcb(destination: Path | str, parameters: BoardParameters) -> Path:
    """Write the rendered board to disk and return the resolved path."""

    output_path = Path(destination).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_kicad_pcb(parameters), encoding="utf-8")
    return output_path.resolve()


def _render_pads(parameters: BoardParameters) -> list[str]:
    pad_size = _mm(parameters.pad_diameter_mm)
    drill_size = _mm(parameters.pth_drill_mm)

    lines: list[str] = []
    for pad_number, (x_pos, y_pos) in enumerate(parameters.iter_pad_positions(), start=1):
        x_value = _mm(x_pos)
        y_value = _mm(y_pos)
        lines.extend(
            [
                f'    (pad "{pad_number}" thru_hole circle',
                f"      (at {x_value} {y_value})",
                f"      (size {pad_size} {pad_size})",
                f"      (drill {drill_size})",
                '      (layers "*.Cu" "*.Mask")',
                "    )",
            ]
        )
    return lines


def _render_mounting_holes(parameters: BoardParameters) -> list[str]:
    diameter = _mm(parameters.mounting_hole_diameter_mm)
    label_offset = _mm(max(parameters.edge_margin_mm / 2.0, 2.0))

    lines: list[str] = []
    for hole_index, (x_pos, y_pos) in enumerate(
        parameters.iter_mounting_hole_positions(),
        start=1,
    ):
        x_value = _mm(x_pos)
        y_value = _mm(y_pos)
        lines.extend(
            [
                '  (footprint "EZProto:MountingHole_NPTH"',
                '    (layer "F.Cu")',
                f"    (at {x_value} {y_value})",
                "    (attr board_only exclude_from_pos_files exclude_from_bom)",
                f'    (fp_text reference "H{hole_index}" (at 0 -{label_offset}) (layer "F.SilkS") hide',
                "      (effects (font (size 1 1) (thickness 0.15)))",
                "    )",
                '    (fp_text value "MountingHole_NPTH" (at 0 0) (layer "F.Fab") hide',
                "      (effects (font (size 1 1) (thickness 0.15)))",
                "    )",
                '    (pad "" np_thru_hole circle',
                "      (at 0 0)",
                f"      (size {diameter} {diameter})",
                f"      (drill {diameter})",
                '      (layers "*.Cu" "*.Mask")',
                "    )",
                "  )",
            ]
        )
    return lines


def _render_board_outline(
    parameters: BoardParameters,
    *,
    width: str,
    height: str,
) -> list[str]:
    return _render_outline(
        width_mm=float(width),
        height_mm=float(height),
        rounded_corner_radius_mm=parameters.rounded_corner_radius_mm,
    )


def _render_outline(
    *,
    width_mm: float,
    height_mm: float,
    rounded_corner_radius_mm: float,
) -> list[str]:
    if rounded_corner_radius_mm <= 0:
        return _render_rect_outline(width_mm=width_mm, height_mm=height_mm)

    radius = rounded_corner_radius_mm
    diagonal_offset = radius / sqrt(2)

    return [
        *_render_line(radius, 0.0, width_mm - radius, 0.0),
        *_render_line(width_mm, radius, width_mm, height_mm - radius),
        *_render_line(width_mm - radius, height_mm, radius, height_mm),
        *_render_line(0.0, height_mm - radius, 0.0, radius),
        *_render_arc(
            0.0,
            radius,
            radius - diagonal_offset,
            radius - diagonal_offset,
            radius,
            0.0,
        ),
        *_render_arc(
            width_mm - radius,
            0.0,
            width_mm - radius + diagonal_offset,
            radius - diagonal_offset,
            width_mm,
            radius,
        ),
        *_render_arc(
            width_mm,
            height_mm - radius,
            width_mm - radius + diagonal_offset,
            height_mm - radius + diagonal_offset,
            width_mm - radius,
            height_mm,
        ),
        *_render_arc(
            radius,
            height_mm,
            radius - diagonal_offset,
            height_mm - radius + diagonal_offset,
            0.0,
            height_mm - radius,
        ),
    ]


def _render_rect_outline(*, width_mm: float, height_mm: float) -> list[str]:
    return [
        "  (gr_rect",
        "    (start 0 0)",
        f"    (end {_mm(width_mm)} {_mm(height_mm)})",
        "    (stroke",
        "      (width 0.1)",
        "      (type default)",
        "    )",
        "    (fill none)",
        '    (layer "Edge.Cuts")',
        "  )",
    ]


def _render_line(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> list[str]:
    return [
        "  (gr_line",
        f"    (start {_mm(start_x)} {_mm(start_y)})",
        f"    (end {_mm(end_x)} {_mm(end_y)})",
        "    (stroke",
        "      (width 0.1)",
        "      (type default)",
        "    )",
        '    (layer "Edge.Cuts")',
        "  )",
    ]


def _render_arc(
    start_x: float,
    start_y: float,
    mid_x: float,
    mid_y: float,
    end_x: float,
    end_y: float,
) -> list[str]:
    return [
        "  (gr_arc",
        f"    (start {_mm(start_x)} {_mm(start_y)})",
        f"    (mid {_mm(mid_x)} {_mm(mid_y)})",
        f"    (end {_mm(end_x)} {_mm(end_y)})",
        "    (stroke",
        "      (width 0.1)",
        "      (type default)",
        "    )",
        '    (layer "Edge.Cuts")',
        "  )",
    ]


def _mm(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _escape_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
