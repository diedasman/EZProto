"""Data models for breakout-board generation."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, pi, sin, sqrt
from pathlib import Path
import re
from typing import Any, Iterable, Iterator

# The order in which sides are processed and rendered, if selected.
SIDE_ORDER = ("N", "E", "S", "W")


@dataclass(frozen=True, slots=True)
class BreakoutConfig:
    """User-defined breakout board dimensions and placement rules."""

    footprint_path: Path
    board_width_mm: float
    board_height_mm: float
    pitch_mm: float
    sides: tuple[str, ...]
    header_offset_mm: float = 2.0
    margin_mm: float = 2.0
    mounting_hole_diameter_mm: float = 0.0
    board_name: str = ""
    header_drill_mm: float = 1.0
    header_pad_diameter_mm: float = 1.8
    trace_width_mm: float = 0.25
    rounded_corner_radius_mm: float = 0.0
    debug_routing: bool = False
    routing_debug_output_path: Path | None = None

    def __post_init__(self) -> None:
        footprint_path = Path(_normalize_path_text(self.footprint_path)).expanduser()
        object.__setattr__(self, "footprint_path", footprint_path)
        if self.routing_debug_output_path is not None:
            object.__setattr__(
                self,
                "routing_debug_output_path",
                Path(_normalize_path_text(self.routing_debug_output_path)).expanduser(),
            )
        object.__setattr__(
            self,
            "board_name",
            self._clean_board_name(self.board_name, footprint_path),
        )
        object.__setattr__(self, "sides", self._clean_sides(self.sides))
        self.validate()

    @staticmethod
    def _clean_board_name(name: str, footprint_path: Path) -> str:
        cleaned = (name or "").strip().replace('"', "'")
        if cleaned:
            return cleaned
        source_name = _default_name_from_footprint_path(footprint_path)
        source_name = source_name.replace("_", " ").strip()
        return source_name or "Breakout Board"

    @staticmethod
    def _clean_sides(sides: Iterable[str]) -> tuple[str, ...]:
        normalized: list[str] = []
        for side in sides:
            value = str(side).strip().upper()
            if value in SIDE_ORDER and value not in normalized:
                normalized.append(value)
        ordered = [side for side in SIDE_ORDER if side in normalized]
        return tuple(ordered)

    @property
    def output_directory_name(self) -> str:
        return self.board_name

    @property
    def output_file_stem(self) -> str:
        return self.board_name.replace(" ", "_")

    @property
    def output_file_name(self) -> str:
        return f"{self.output_file_stem}.kicad_pcb"

    @property
    def output_path(self) -> Path:
        return Path(self.output_directory_name) / self.output_file_name

    def output_path_for(self, base_directory: Path | str) -> Path:
        return Path(base_directory).expanduser() / self.output_path

    @property
    def has_rounded_corners(self) -> bool:
        return self.rounded_corner_radius_mm > 0

    @property
    def trace_clearance_mm(self) -> float:
        return max(0.2, self.trace_width_mm * 0.75)

    @property
    def route_spacing_mm(self) -> float:
        return self.trace_width_mm + self.trace_clearance_mm

    @property
    def mounting_hole_count(self) -> int:
        return 4 if self.mounting_hole_diameter_mm > 0 else 0

    @property
    def mounting_hole_inset_mm(self) -> float:
        return self.header_offset_mm

    def iter_mounting_hole_positions(self) -> Iterator[tuple[float, float]]:
        if self.mounting_hole_diameter_mm <= 0:
            return

        inset = self.mounting_hole_inset_mm
        max_x = self.board_width_mm - inset
        max_y = self.board_height_mm - inset

        yield inset, inset
        yield max_x, inset
        yield inset, max_y
        yield max_x, max_y

    def header_position_limits(self, side: str) -> tuple[float, float]:
        axis_limit = self.board_width_mm if side in {"N", "S"} else self.board_height_mm
        minimum = self.margin_mm
        maximum = axis_limit - self.margin_mm

        if self.mounting_hole_diameter_mm <= 0:
            return minimum, maximum

        hole_clearance = self._header_mounting_hole_axis_clearance_mm()
        inset = self.mounting_hole_inset_mm
        return (
            max(minimum, inset + hole_clearance),
            min(maximum, axis_limit - inset - hole_clearance),
        )

    def point_is_inside_outline(self, point_x: float, point_y: float) -> bool:
        if point_x < 0 or point_y < 0:
            return False
        if point_x > self.board_width_mm or point_y > self.board_height_mm:
            return False

        radius = self.rounded_corner_radius_mm
        if radius <= 0:
            return True

        width = self.board_width_mm
        height = self.board_height_mm

        if point_x < radius and point_y < radius:
            return hypot(point_x - radius, point_y - radius) <= radius
        if point_x > width - radius and point_y < radius:
            return hypot(point_x - (width - radius), point_y - radius) <= radius
        if point_x < radius and point_y > height - radius:
            return hypot(point_x - radius, point_y - (height - radius)) <= radius
        if point_x > width - radius and point_y > height - radius:
            return hypot(point_x - (width - radius), point_y - (height - radius)) <= radius
        return True

    def validate(self) -> None:
        if self.board_width_mm <= 0:
            raise ValueError("Board width must be greater than 0 mm.")
        if self.board_height_mm <= 0:
            raise ValueError("Board height must be greater than 0 mm.")
        if self.pitch_mm <= 0:
            raise ValueError("Pitch must be greater than 0 mm.")
        if not self.sides:
            raise ValueError("Select at least one header side.")
        if self.header_offset_mm <= 0:
            raise ValueError("Header offset must be greater than 0 mm.")
        if self.margin_mm < 0:
            raise ValueError("Margin cannot be negative.")
        if self.mounting_hole_diameter_mm < 0:
            raise ValueError("Mounting hole diameter cannot be negative.")
        if self.header_drill_mm <= 0:
            raise ValueError("Header drill must be greater than 0 mm.")
        if self.header_pad_diameter_mm <= self.header_drill_mm:
            raise ValueError("Header pad diameter must be larger than the drill size.")
        if self.trace_width_mm <= 0:
            raise ValueError("Trace width must be greater than 0 mm.")
        if self.rounded_corner_radius_mm < 0:
            raise ValueError("Rounded corner radius cannot be negative.")
        if self.board_width_mm <= 2 * self.header_offset_mm:
            raise ValueError("Board width must leave room for the header offset.")
        if self.board_height_mm <= 2 * self.header_offset_mm:
            raise ValueError("Board height must leave room for the header offset.")
        if self.board_width_mm <= 2 * self.margin_mm:
            raise ValueError("Board width must leave room for the side margin.")
        if self.board_height_mm <= 2 * self.margin_mm:
            raise ValueError("Board height must leave room for the side margin.")
        if self.header_offset_mm <= self.header_pad_diameter_mm / 2.0:
            raise ValueError(
                "Header offset must be large enough to keep the header holes on the board."
            )
        if self.rounded_corner_radius_mm > min(self.board_width_mm, self.board_height_mm) / 2.0:
            raise ValueError("Rounded corner radius is too large for the board size.")
        if self.mounting_hole_diameter_mm == 0:
            return

        if self.mounting_hole_diameter_mm > 2.0 * self.mounting_hole_inset_mm:
            raise ValueError("Mounting hole diameter must fit inside the header offset.")
        if self.board_width_mm < (2.0 * self.mounting_hole_inset_mm) + self.mounting_hole_diameter_mm:
            raise ValueError("Board width must leave room for the corner mounting holes.")
        if self.board_height_mm < (2.0 * self.mounting_hole_inset_mm) + self.mounting_hole_diameter_mm:
            raise ValueError("Board height must leave room for the corner mounting holes.")
        if self.rounded_corner_radius_mm > 0:
            clearance = 0.2
            feature_radius = (self.mounting_hole_diameter_mm / 2.0) + clearance
            for center_x, center_y in self.iter_mounting_hole_positions():
                self._validate_feature_against_outline(
                    center_x=center_x,
                    center_y=center_y,
                    feature_radius=feature_radius,
                    feature_name="mounting hole",
                )

    def _header_mounting_hole_axis_clearance_mm(self) -> float:
        required_distance = (
            (self.mounting_hole_diameter_mm / 2.0)
            + (self.header_pad_diameter_mm / 2.0)
            + 0.2
        )
        orthogonal_delta = abs(self.header_offset_mm - self.mounting_hole_inset_mm)
        if orthogonal_delta >= required_distance:
            return 0.0
        return sqrt((required_distance**2) - (orthogonal_delta**2))

    def _validate_feature_against_outline(
        self,
        *,
        center_x: float,
        center_y: float,
        feature_radius: float,
        feature_name: str,
    ) -> None:
        for point_x, point_y in _sample_circle(center_x, center_y, feature_radius):
            if not self.point_is_inside_outline(point_x, point_y):
                raise ValueError(
                    f"Rounded corners clip the {feature_name}; reduce the corner radius "
                    "or increase the clearances."
                )


@dataclass(frozen=True, slots=True)
class Pad:
    """A logical pad used for routing and header generation."""

    name: str
    x: float
    y: float
    net: str | None
    width_mm: float = 0.0
    height_mm: float = 0.0


@dataclass(frozen=True, slots=True)
class HeaderPin:
    """A generated breakout header pin."""

    name: str
    x: float
    y: float
    net: str
    side: str


@dataclass(frozen=True, slots=True)
class TraceSegment:
    """A simple routed copper segment."""

    start_x: float
    start_y: float
    end_x: float
    end_y: float
    net: str


@dataclass(frozen=True, slots=True)
class Bounds:
    """Axis-aligned bounds for the imported footprint."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width_mm(self) -> float:
        return self.max_x - self.min_x

    @property
    def height_mm(self) -> float:
        return self.max_y - self.min_y


@dataclass(frozen=True, slots=True)
class ParsedFootprint:
    """The parsed KiCad footprint definition and its logical pads."""

    path: Path
    name: str
    library_link: str
    tree: Any
    pads: tuple[Pad, ...]
    bounds: Bounds
    physical_pad_count: int
    npth_pad_count: int = 0


@dataclass(frozen=True, slots=True)
class BreakoutBoard:
    """A generated breakout board ready to render into KiCad."""

    config: BreakoutConfig
    footprint: ParsedFootprint
    footprint_origin_x: float
    footprint_origin_y: float
    pads: tuple[Pad, ...]
    headers: tuple[HeaderPin, ...]
    traces: tuple[TraceSegment, ...]
    routing_warnings: tuple[str, ...] = ()
    routing_debug_svg: str | None = None

    @property
    def net_names(self) -> tuple[str, ...]:
        seen: list[str] = []
        for pad in self.pads:
            if pad.net and pad.net not in seen:
                seen.append(pad.net)
        return tuple(seen)


def _normalize_path_text(path: Path | str) -> str:
    value = str(path).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value


def _default_name_from_footprint_path(path: Path | str) -> str:
    raw_value = _normalize_path_text(path)
    kicad_mod_match = re.search(r"([^\\/:\"]+?)(?:\.kicad_mod)$", raw_value, flags=re.IGNORECASE)
    if kicad_mod_match:
        return kicad_mod_match.group(1)

    pretty_match = re.search(
        r"\.pretty(?:(?::|[\\/]))([^\\/:\"]+?)(?:\.kicad_mod)?$",
        raw_value,
        flags=re.IGNORECASE,
    )
    if pretty_match:
        return pretty_match.group(1)

    footprint_path = Path(raw_value)
    if footprint_path.suffix.lower() == ".pretty":
        return footprint_path.stem
    if footprint_path.suffix.lower() == ".kicad_mod":
        return footprint_path.stem
    return footprint_path.name


def _sample_circle(
    center_x: float,
    center_y: float,
    radius: float,
    *,
    steps: int = 32,
) -> Iterator[tuple[float, float]]:
    for step in range(steps):
        angle = (2 * pi * step) / steps
        yield center_x + (cos(angle) * radius), center_y + (sin(angle) * radius)
