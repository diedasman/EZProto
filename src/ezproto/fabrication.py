"""Simple Gerber and drill generation for EZProto boards."""

from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path
import zipfile

from ezproto.models import BoardParameters

GERBER_FORMAT_SCALE = 1000000
GERBER_COORD_WIDTH = 10
OUTLINE_STROKE_MM = 0.15
MASK_EXPANSION_MM = 0.1


def write_fabrication_package(
    destination_directory: Path | str,
    parameters: BoardParameters,
    *,
    include_drill: bool = True,
) -> list[Path]:
    """Write a minimal Gerber/drill package for the generated board."""

    output_directory = Path(destination_directory).expanduser()
    output_directory.mkdir(parents=True, exist_ok=True)

    stem = parameters.output_file_stem
    file_contents = {
        f"{stem}_F_Cu.gbr": _render_flash_layer(
            parameters,
            layer_name="F.Cu",
            aperture_diameter_mm=parameters.pad_diameter_mm,
        ),
        f"{stem}_B_Cu.gbr": _render_flash_layer(
            parameters,
            layer_name="B.Cu",
            aperture_diameter_mm=parameters.pad_diameter_mm,
        ),
        f"{stem}_F_Mask.gbr": _render_flash_layer(
            parameters,
            layer_name="F.Mask",
            aperture_diameter_mm=parameters.pad_diameter_mm + MASK_EXPANSION_MM,
        ),
        f"{stem}_B_Mask.gbr": _render_flash_layer(
            parameters,
            layer_name="B.Mask",
            aperture_diameter_mm=parameters.pad_diameter_mm + MASK_EXPANSION_MM,
        ),
        f"{stem}_F_Paste.gbr": _render_empty_layer("F.Paste"),
        f"{stem}_B_Paste.gbr": _render_empty_layer("B.Paste"),
        f"{stem}_F_Silkscreen.gbr": _render_empty_layer("F.Silkscreen"),
        f"{stem}_B_Silkscreen.gbr": _render_empty_layer("B.Silkscreen"),
        f"{stem}_Edge_Cuts.gbr": _render_outline_layer(parameters),
    }
    if include_drill:
        file_contents[f"{stem}.drl"] = _render_drill_file(parameters)

    written_files: list[Path] = []
    for file_name, contents in file_contents.items():
        path = output_directory / file_name
        path.write_text(contents, encoding="utf-8")
        written_files.append(path.resolve())

    return written_files


def write_fabrication_archive(
    destination_archive: Path | str,
    fabrication_files: list[Path],
    *,
    root_directory_name: str,
) -> Path:
    """Write a ZIP archive for a fabrication package."""

    archive_path = Path(destination_archive).expanduser()
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for file_path in fabrication_files:
            archive.write(
                file_path,
                arcname=str(Path(root_directory_name) / file_path.name),
            )

    return archive_path.resolve()


def _render_flash_layer(
    parameters: BoardParameters,
    *,
    layer_name: str,
    aperture_diameter_mm: float,
) -> str:
    lines = _gerber_header(
        layer_name,
        file_function=_layer_file_function(layer_name),
    )
    lines.extend(
        [
            f"%ADD10C,{aperture_diameter_mm:.4f}*%",
            "D10*",
        ]
    )

    for x_pos, y_pos in parameters.iter_pad_positions():
        lines.append(f"X{_gerber_coord(x_pos)}Y{_gerber_coord(_fabrication_y(y_pos))}D03*")

    lines.append("M02*")
    return "\n".join(lines) + "\n"


def _render_outline_layer(parameters: BoardParameters) -> str:
    points = _outline_points(parameters)
    lines = _gerber_header(
        "Edge.Cuts",
        file_function=_layer_file_function("Edge.Cuts"),
    )
    lines.extend(
        [
            f"%ADD10C,{OUTLINE_STROKE_MM:.4f}*%",
            "D10*",
        ]
    )

    start_x, start_y = points[0]
    lines.append(
        f"X{_gerber_coord(start_x)}Y{_gerber_coord(_fabrication_y(start_y))}D02*"
    )
    for point_x, point_y in points[1:]:
        lines.append(
            f"X{_gerber_coord(point_x)}Y{_gerber_coord(_fabrication_y(point_y))}D01*"
        )

    lines.append("M02*")
    return "\n".join(lines) + "\n"


def _render_empty_layer(layer_name: str) -> str:
    lines = _gerber_header(
        layer_name,
        file_function=_layer_file_function(layer_name),
    )
    lines.append("M02*")
    return "\n".join(lines) + "\n"


def _render_drill_file(parameters: BoardParameters) -> str:
    tool_map: dict[str, list[tuple[float, float]]] = {
        "T01": list(parameters.iter_pad_positions()),
    }
    tool_sizes = {
        "T01": parameters.pth_drill_mm,
    }

    if parameters.mounting_hole_diameter_mm > 0:
        tool_map["T02"] = list(parameters.iter_mounting_hole_positions())
        tool_sizes["T02"] = parameters.mounting_hole_diameter_mm

    lines = [
        "M48",
        "; EZProto drill file",
        "; FORMAT={absolute / metric / decimal}",
        "FMAT,2",
        "METRIC,TZ",
    ]
    for tool_name, diameter in tool_sizes.items():
        lines.append(f"{tool_name}C{diameter:.4f}")
    lines.extend(
        [
            "%",
            # Excellon consumers do not always default to absolute coordinates.
            # Declaring this explicitly keeps drill hits aligned with the copper flashes.
            "G90",
            "G05",
        ]
    )

    for tool_name, positions in tool_map.items():
        lines.append(tool_name)
        for x_pos, y_pos in positions:
            lines.append(
                f"X{_drill_coord(x_pos)}Y{_drill_coord(_fabrication_y(y_pos))}"
            )

    lines.append("M30")
    return "\n".join(lines) + "\n"


def _gerber_header(layer_name: str, *, file_function: str) -> list[str]:
    return [
        f"G04 EZProto {layer_name}*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        f"%TF.FileFunction,{file_function}*%",
        "%TF.FilePolarity,Positive*%",
        "%LPD*%",
    ]


def _layer_file_function(layer_name: str) -> str:
    file_functions = {
        "F.Cu": "Copper,L1,Top",
        "B.Cu": "Copper,L2,Bottom",
        "F.Mask": "Soldermask,Top",
        "B.Mask": "Soldermask,Bottom",
        "F.Paste": "Paste,Top",
        "B.Paste": "Paste,Bottom",
        "F.Silkscreen": "Legend,Top",
        "B.Silkscreen": "Legend,Bottom",
        "Edge.Cuts": "Profile,NP",
    }
    return file_functions[layer_name]


def _outline_points(parameters: BoardParameters) -> list[tuple[float, float]]:
    width = parameters.board_width_mm
    height = parameters.board_height_mm
    radius = parameters.rounded_corner_radius_mm

    if radius <= 0:
        return [
            (0.0, 0.0),
            (width, 0.0),
            (width, height),
            (0.0, height),
            (0.0, 0.0),
        ]

    points: list[tuple[float, float]] = [
        (radius, 0.0),
        (width - radius, 0.0),
        *_arc_points(width - radius, radius, radius, -90.0, 0.0),
        (width, height - radius),
        *_arc_points(width - radius, height - radius, radius, 0.0, 90.0),
        (radius, height),
        *_arc_points(radius, height - radius, radius, 90.0, 180.0),
        (0.0, radius),
        *_arc_points(radius, radius, radius, 180.0, 270.0),
        (radius, 0.0),
    ]
    return points


def _arc_points(
    center_x: float,
    center_y: float,
    radius: float,
    start_degrees: float,
    end_degrees: float,
    *,
    steps: int = 8,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for step in range(1, steps + 1):
        fraction = step / steps
        angle = start_degrees + ((end_degrees - start_degrees) * fraction)
        radians = (angle * pi) / 180.0
        points.append(
            (
                center_x + (cos(radians) * radius),
                center_y + (sin(radians) * radius),
            )
        )
    return points


def _fabrication_y(value_mm: float) -> float:
    return value_mm


def _gerber_coord(value_mm: float) -> str:
    return f"{int(round(value_mm * GERBER_FORMAT_SCALE)):0{GERBER_COORD_WIDTH}d}"


def _drill_coord(value_mm: float) -> str:
    text = f"{value_mm:.4f}".rstrip("0").rstrip(".")
    if "." not in text:
        return f"{text}.0"
    return text
