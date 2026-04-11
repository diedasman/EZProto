"""KiCad PCB file generation helpers."""

from __future__ import annotations

from copy import deepcopy
from math import sqrt
from pathlib import Path
from typing import Any

from ezproto.breakout.footprint_parser import Atom, atom, serialize_sexpr
from ezproto.breakout.models import BreakoutBoard
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


def render_breakout_board(board: BreakoutBoard) -> str:
    """Render a breakout board into a KiCad `.kicad_pcb` document."""

    net_numbers = {net_name: index for index, net_name in enumerate(board.net_names, start=1)}
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
    ]
    for net_name, number in net_numbers.items():
        lines.append(f'  (net {number} "{_escape_text(net_name)}")')

    lines.extend(_render_imported_footprint(board, net_numbers))
    if board.config.mounting_hole_diameter_mm > 0:
        lines.extend(_render_breakout_mounting_holes(board))
    lines.extend(_render_breakout_headers(board, net_numbers))
    lines.extend(_render_breakout_segments(board, net_numbers))
    lines.extend(
        _render_outline(
            width_mm=board.config.board_width_mm,
            height_mm=board.config.board_height_mm,
            rounded_corner_radius_mm=board.config.rounded_corner_radius_mm,
        )
    )
    lines.append(")")
    return "\n".join(lines) + "\n"


def write_breakout_board(destination: Path | str, board: BreakoutBoard) -> Path:
    """Write a rendered breakout board to disk."""

    output_path = Path(destination).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_breakout_board(board), encoding="utf-8")
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


def _render_imported_footprint(
    board: BreakoutBoard,
    net_numbers: dict[str, int],
) -> list[str]:
    footprint_node = deepcopy(board.footprint.tree)
    _remove_children(footprint_node, {"version", "generator", "generator_version"})
    _upsert_footprint_at(
        footprint_node,
        x_pos=board.footprint_origin_x,
        y_pos=board.footprint_origin_y,
    )

    pad_net_map = {
        pad.name: pad.net
        for pad in board.pads
        if pad.net is not None
    }
    for child in footprint_node:
        if _node_head(child) != "pad":
            continue
        pad_name = _atom_value(child[1]) if len(child) > 1 and isinstance(child[1], Atom) else ""
        net_name = pad_net_map.get(pad_name)
        if net_name is None:
            continue
        _upsert_pad_net(child, net_number=net_numbers[net_name], net_name=net_name)

    return serialize_sexpr(footprint_node, indent=2).splitlines()


def _render_breakout_headers(
    board: BreakoutBoard,
    net_numbers: dict[str, int],
) -> list[str]:
    label_offset = _mm(max(board.config.header_offset_mm / 2.0, 2.0))
    drill_size = _mm(board.config.header_drill_mm)
    pad_size = _mm(board.config.header_pad_diameter_mm)

    lines: list[str] = []
    for index, header in enumerate(board.headers, start=1):
        net_number = net_numbers[header.net]
        lines.extend(
            [
                '  (footprint "EZProto:BreakoutPin"',
                '    (layer "F.Cu")',
                f"    (at {_mm(header.x)} {_mm(header.y)})",
                "    (attr board_only exclude_from_pos_files exclude_from_bom)",
                f'    (fp_text reference "J{index}" (at 0 -{label_offset}) (layer "F.SilkS") hide',
                "      (effects (font (size 1 1) (thickness 0.15)))",
                "    )",
                f'    (fp_text value "{_escape_text(header.name)}" (at 0 0) (layer "F.Fab") hide',
                "      (effects (font (size 1 1) (thickness 0.15)))",
                "    )",
                '    (pad "1" thru_hole circle',
                "      (at 0 0)",
                f"      (size {pad_size} {pad_size})",
                f"      (drill {drill_size})",
                '      (layers "*.Cu" "*.Mask")',
                f'      (net {net_number} "{_escape_text(header.net)}")',
                "    )",
                "  )",
            ]
        )
    return lines


def _render_breakout_mounting_holes(board: BreakoutBoard) -> list[str]:
    diameter = _mm(board.config.mounting_hole_diameter_mm)
    label_offset = _mm(max(board.config.header_offset_mm / 2.0, 2.0))

    lines: list[str] = []
    for hole_index, (x_pos, y_pos) in enumerate(
        board.config.iter_mounting_hole_positions(),
        start=1,
    ):
        lines.extend(
            [
                '  (footprint "EZProto:MountingHole_NPTH"',
                '    (layer "F.Cu")',
                f"    (at {_mm(x_pos)} {_mm(y_pos)})",
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


def _render_breakout_segments(
    board: BreakoutBoard,
    net_numbers: dict[str, int],
) -> list[str]:
    width = _mm(board.config.trace_width_mm)
    lines: list[str] = []
    for segment in board.traces:
        lines.extend(
            [
                "  (segment",
                f"    (start {_mm(segment.start_x)} {_mm(segment.start_y)})",
                f"    (end {_mm(segment.end_x)} {_mm(segment.end_y)})",
                f"    (width {width})",
                '    (layer "F.Cu")',
                f"    (net {net_numbers[segment.net]})",
                "  )",
            ]
        )
    return lines


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


def _remove_children(node: list[Any], heads: set[str]) -> None:
    node[:] = [
        child
        for child in node
        if not (isinstance(child, list) and _node_head(child) in heads)
    ]


def _upsert_footprint_at(node: list[Any], *, x_pos: float, y_pos: float) -> None:
    replacement = [atom("at"), atom(_mm(x_pos)), atom(_mm(y_pos))]
    existing = _find_child(node, "at")
    if existing is not None:
        existing[:] = replacement
        return
    insert_index = 2 if len(node) >= 2 else len(node)
    node.insert(insert_index, replacement)


def _upsert_pad_net(node: list[Any], *, net_number: int, net_name: str) -> None:
    replacement = [atom("net"), atom(str(net_number)), atom(net_name, quoted=True)]
    existing = _find_child(node, "net")
    if existing is not None:
        existing[:] = replacement
        return
    node.append(replacement)


def _find_child(node: list[Any], head: str) -> list[Any] | None:
    for child in node:
        if isinstance(child, list) and _node_head(child) == head:
            return child
    return None


def _node_head(node: Any) -> str:
    if not isinstance(node, list) or not node:
        return ""
    value = node[0]
    return value.value if isinstance(value, Atom) else ""


def _atom_value(node: Any) -> str:
    if not isinstance(node, Atom):
        raise TypeError("Expected a KiCad S-expression atom.")
    return node.value


def _mm(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _escape_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
